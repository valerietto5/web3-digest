from __future__ import annotations
from fastapi.responses import HTMLResponse

from .ui_page import build_ui_html
from fastapi import FastAPI, HTTPException, Query
from pathlib import Path
import json
from datetime import datetime, timezone
import inspect
import portfolio
import db
import traceback
import sys
import subprocess
import time
import os
import urllib.parse
import urllib.request
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

app = FastAPI(title="Web3 Digest API", version="0.1.0")


def _write_portfolio_snapshot(account: str, currency: str = "usd") -> None:
    """
    Compute latest report and store a portfolio snapshot (totals) into SQLite.
    Keeps /portfolio/history alive automatically.
    """
    acct = get_account_or_404(account)
    assets_list = acct.get("default_assets") or acct.get("assets") or []
    if not assets_list:
        return

    report = call_with_supported_kwargs(
        portfolio.compute_portfolio_report,
        account=account,
        account_id=account,
        assets=assets_list,
        currency=currency,
    )

    enc = jsonable_encoder(report)
    total_value = enc.get("total_value", 0)
    ts = enc.get("generated_at") or datetime.now(timezone.utc).isoformat()

    call_with_supported_kwargs(
        db.insert_portfolio_snapshot,
        ts=ts,               # required
        account=account,
        account_id=account,  # fallback name
        currency=currency,
        total_value=total_value,
        value=total_value,   # fallback name
        source="computed",
    )

def display_asset(asset: str) -> str:
    # Known simple assets
    if asset in {"sol", "usdc", "btc", "eth"}:
        return asset.upper()

    # SPL mint format: spl:<mint>
    if asset.startswith("spl:"):
        mint = asset.split(":", 1)[1]

        # Try token_registry lookup (best effort, no hard dependency)
        try:
            import token_registry  # your project file
            # common patterns: token_registry.get(mint) or token_registry.REGISTRY[mint], etc.
            for attr in ("get_by_mint", "token_for_mint", "lookup_mint", "get"):
                fn = getattr(token_registry, attr, None)
                if callable(fn):
                    info = fn(mint)
                    if isinstance(info, dict):
                        return info.get("symbol") or info.get("name") or asset
            # common dicts:
            for attr in ("TOKEN_REGISTRY", "REGISTRY", "TOKENS"):
                d = getattr(token_registry, attr, None)
                if isinstance(d, dict):
                    info = d.get(mint)
                    if isinstance(info, dict):
                        return info.get("symbol") or info.get("name") or asset
        except Exception:
            pass

        # Fallback: readable short mint
        return f"SPL {mint[:4]}…{mint[-4:]}"

    # default
    return asset

def call_with_supported_kwargs(fn, **kwargs):
    """
    Calls fn(**kwargs) but silently drops kwargs that fn doesn't accept.
    This makes our API wiring resilient to small signature differences.
    """
    sig = inspect.signature(fn)
    supported = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return fn(**supported)

MIN_BALANCE_REFRESH_SECONDS = 120  # 2 minutes for now (dev-friendly)
MIN_PRICE_REFRESH_SECONDS = 120  # 2 minutes for now (dev-friendly)

_last_refresh: dict[str, float] = {}  # key -> unix timestamp


def _cooldown_ok(key: str, min_seconds: int, force: bool) -> bool:
    if force:
        return True
    now = time.time()
    last = _last_refresh.get(key)
    return (last is None) or ((now - last) >= min_seconds)


def _mark_refreshed(key: str) -> None:
    _last_refresh[key] = time.time()


def _run_cmd(cmd: list[str], timeout: int = 90) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {
        "cmd": " ".join(cmd),
        "returncode": p.returncode,
        "stdout": (p.stdout or "")[-2000:],  # last 2000 chars
        "stderr": (p.stderr or "")[-2000:],
    }

@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    # DEV ONLY: return useful error info instead of plain "Internal Server Error"
    return JSONResponse(
        status_code=500,
        content={
            "error_type": exc.__class__.__name__,
            "error": str(exc),
            "traceback": traceback.format_exc().splitlines()[-35:],  # last lines
        },
    )

def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def accounts_path() -> Path:
    return project_root() / "accounts.json"


def load_accounts() -> dict:
    p = accounts_path()
    if not p.exists():
        return {"accounts": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def get_account_or_404(account_name: str) -> dict:
    data = load_accounts()
    accounts = data.get("accounts") or data
    acct = accounts.get(account_name)
    if not acct:
        raise HTTPException(status_code=404, detail=f"Unknown account: {account_name}")
    return acct


@app.get("/health")
def health():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/accounts")
def accounts():
    data = load_accounts()
    accounts = data.get("accounts") or data
    out = []
    for name, a in accounts.items():
        out.append(
            {
                "name": name,
                "chain": a.get("chain"),
                "address": a.get("address"),
                "default_assets": a.get("default_assets") or a.get("assets") or [],
            }
        )
    return {"accounts": out}


JUP_API_KEY = os.environ.get("JUP_API_KEY", "").strip()

TOKEN_META = {
    "SOL": {
        "mint": "So11111111111111111111111111111111111111112",
        "decimals": 9,
    },
    "USDC": {
        "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "decimals": 6,
    },
}


def to_raw_amount(amount: float, decimals: int) -> int:
    raw = round(amount * (10 ** decimals))
    if raw <= 0:
        raise HTTPException(status_code=400, detail="amount is too small after decimal conversion")
    return raw


@app.get("/swap/quote")
def swap_quote(from_token: str, to_token: str, amount: float, network: str = "solana"):
    from_token = from_token.upper().strip()
    to_token = to_token.upper().strip()

    if network != "solana":
        raise HTTPException(status_code=400, detail="only solana is supported for now")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    if from_token == to_token:
        raise HTTPException(status_code=400, detail="from_token and to_token must be different")

    if from_token not in TOKEN_META or to_token not in TOKEN_META:
        raise HTTPException(status_code=400, detail="unsupported token for now")

    
        

    input_meta = TOKEN_META[from_token]
    output_meta = TOKEN_META[to_token]

    raw_amount = to_raw_amount(amount, input_meta["decimals"])

    params = {
        "inputMint": input_meta["mint"],
        "outputMint": output_meta["mint"],
        "amount": str(raw_amount),
        "slippageBps": "50",
        "restrictIntermediateTokens": "true",
        "instructionVersion": "V2",
    }

    url = "https://lite-api.jup.ag/swap/v1/quote?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=e.code, detail=f"Jupiter HTTP error: {body}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jupiter request failed: {e}")

    route_plan = data.get("routePlan", [])
    first_leg = route_plan[0]["swapInfo"] if route_plan else {}

    out_amount_raw = data.get("outAmount")
    out_amount_ui = None
    if out_amount_raw is not None:
        out_amount_ui = int(out_amount_raw) / (10 ** output_meta["decimals"])

    return {
        "ok": True,
        "network": network,
        "provider": "jupiter-metis",
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": amount,
        "input_amount_raw": raw_amount,
        "estimated_output": out_amount_ui,
        "estimated_output_raw": out_amount_raw,
        "route_label": first_leg.get("label"),
        "price_impact_pct": data.get("priceImpactPct"),
        "slippage_bps": data.get("slippageBps"),
        "route_plan": route_plan,
        "raw_quote": data,
    }



@app.get("/portfolio/latest")
def portfolio_latest(
    account: str = Query(...),
    currency: str = Query("usd"),
    assets: str | None = Query(
        None,
        description="Comma-separated asset keys, e.g. sol,usdc,spl:<mint>. If omitted, uses account default_assets.",
    ),
    show_unpriced: bool = Query(False),
):
    acct = get_account_or_404(account)
    default_assets = acct.get("default_assets") or acct.get("assets") or []

    if assets:
        requested_assets = [a.strip() for a in assets.split(",") if a.strip()]
        if not requested_assets:
            raise HTTPException(status_code=400, detail="assets parameter was provided but empty after parsing")
        assets_list = requested_assets
    else:
        assets_list = default_assets

    if not assets_list:
        raise HTTPException(status_code=400, detail=f"Account '{account}' has no default assets configured")

    # Adjust only if your portfolio.compute_report signature differs.
    report = call_with_supported_kwargs(
        portfolio.compute_portfolio_report,
        account=account,
        account_id=account,          # in case your engine uses account_id in the future
        assets=assets_list,
        currency=currency,
        show_unpriced=show_unpriced, # will be ignored if not supported
        include_unpriced=show_unpriced,  # common alternative name; ignored if not supported
)

    encoded = jsonable_encoder(report)

    # Add display labels to each position
    positions = encoded.get("positions") or {}
    for k, p in positions.items():
        # p is a dict
        p["display"] = display_asset(p.get("asset") or k)

    return {"account": account, "currency": currency, "report": encoded}


@app.get("/portfolio/history")
def portfolio_history(
    account: str = Query(...),
    currency: str = Query("usd"),
    limit: int = Query(30, ge=1, le=365),
):
    rows = call_with_supported_kwargs(
        db.get_portfolio_snapshot_history,
        account=account,
        account_id=account,   # fallback name
        currency=currency,
        limit=limit,
)
    return {"account": account, "currency": currency, "limit": limit, "history": jsonable_encoder(rows)}

@app.get("/")
def root():
    return {"name": "Web3 Digest API", "docs": "/docs", "health": "/health"}


@app.post("/refresh/balances")
def refresh_balances(
    account: str | None = Query(None, description="If provided, refresh only this account"),
    force: bool = Query(False),
):
    data = load_accounts()
    accounts_map = data.get("accounts") or data

    targets = []
    for name, a in accounts_map.items():
        if account and name != account:
            continue
        if (a.get("chain") or "").lower() != "solana":
            continue
        addr = a.get("address")
        if not addr:
            continue
        targets.append((name, addr))

    if not targets:
        raise HTTPException(status_code=400, detail="No solana accounts with addresses found to refresh")

    refreshed = []
    skipped = []

    for name, addr in targets:
        key = f"balances:{name}"
        if not _cooldown_ok(key, MIN_BALANCE_REFRESH_SECONDS, force):
            skipped.append({"account": name, "reason": "cooldown"})
            continue

        cmd = [
            sys.executable, "run_balances_to_db.py",
            "--source", "solana",
            "--address", addr,
            "--account", name,
            "--no-report",
        ]
        r = _run_cmd(cmd)
        refreshed.append({"account": name, **r})

        if r["returncode"] == 0:
            _mark_refreshed(key)
            _write_portfolio_snapshot(name, currency="usd")

    return {"refreshed": refreshed, "skipped": skipped}

@app.post("/refresh/prices")
def refresh_prices(
    account: str | None = Query(None, description="If provided, use this account's default_assets"),
    currency: str = Query("usd"),
    assets: str | None = Query(None, description="Comma-separated asset keys override, e.g. sol,usdc"),
    source: str = Query("coingecko"),
    force: bool = Query(False),
    use_dex: bool = Query(True, description="Enable DexScreener fallback for allowlisted SPL (USD only)"),
    min_liquidity_usd: float = Query(5000.0, ge=0, description="Min liquidity for DexScreener fallback"),
):
    # Resolve assets_list
    if assets:
        assets_list = [a.strip() for a in assets.split(",") if a.strip()]
    elif account:
        acct = get_account_or_404(account)
        assets_list = acct.get("default_assets") or acct.get("assets") or []
    else:
        # Union of all default assets across accounts
        data = load_accounts()
        accounts_map = data.get("accounts") or data
        aset = set()
        for _name, a in accounts_map.items():
            for x in (a.get("default_assets") or a.get("assets") or []):
                aset.add(x)
        assets_list = sorted(aset)

    if not assets_list:
        raise HTTPException(status_code=400, detail="No assets resolved for price refresh")

    key = f"prices:{currency}:{source}:{','.join(sorted(assets_list))}"
    if not _cooldown_ok(key, MIN_PRICE_REFRESH_SECONDS, force):
        return {"refreshed": [], "skipped": [{"reason": "cooldown", "key": key}]}

    cmd = [
        sys.executable, "run_prices_to_db.py",
        "--currency", currency,
        "--source", source,
        "--assets", *assets_list,
    ]

    if use_dex and currency.lower() == "usd":
        cmd += ["--dex", "--min-liquidity-usd", str(min_liquidity_usd)]

    r = _run_cmd(cmd)
    if r["returncode"] == 0:
        _mark_refreshed(key)
        if account:
            _write_portfolio_snapshot(account, currency=currency)

    return {"currency": currency, "source": source, "assets": assets_list, "result": r}


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return HTMLResponse(build_ui_html())
