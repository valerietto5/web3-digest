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
from fastapi import Body

import requests
from datetime import datetime, timezone
from token_registry import default_swap_token_meta_by_symbol, get_token_meta_by_symbol

app = FastAPI(title="Web3 Digest API", version="0.1.0")




TOKEN_META = default_swap_token_meta_by_symbol()


def _resolve_swap_token_meta(token_symbol: str) -> dict | None:
    meta = get_token_meta_by_symbol(token_symbol)
    if not meta:
        return None

    mint = (meta.get("mint") or "").strip()
    decimals = meta.get("decimals")
    if not mint or decimals is None:
        return None

    return dict(meta)


def _coingecko_id_for_quote_token(token_symbol: str) -> str | None:
    meta = _resolve_swap_token_meta(token_symbol)
    if meta and meta.get("coingecko_id"):
        return meta.get("coingecko_id")
    return None


def _fetch_jupiter_price_v3_reference_prices_usd(tokens: list[str]) -> dict:
    token_to_mint = {}
    for token in tokens:
        token = (token or "").strip().upper()
        meta = _resolve_swap_token_meta(token) or {}
        mint = (meta.get("mint") or "").strip()
        if mint:
            token_to_mint[token] = mint

    if not token_to_mint:
        return {}

    url = "https://lite-api.jup.ag/price/v3?" + urllib.parse.urlencode(
        {"ids": ",".join(sorted(set(token_to_mint.values())))}
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": "web3-digest/0.1",
    }

    jup_api_key = os.getenv("JUP_API_KEY")
    if jup_api_key:
        headers["x-api-key"] = jup_api_key

    req = urllib.request.Request(
        url,
        headers=headers,
        method="GET",
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    out = {}
    for token, mint in token_to_mint.items():
        row = data.get(mint) or {}
        usd = row.get("usdPrice")
        if usd is None:
            continue

        pricing_ts = row.get("createdAt")
        block_id = row.get("blockId")
        if not pricing_ts and block_id is not None:
            pricing_ts = str(block_id)

        out[token] = {
            "usd": float(usd),
            "pricing_source": "jupiter_price_v3",
            "pricing_ts": pricing_ts,
            "pricing_source_detail": {
                "mint": mint,
                "block_id": block_id,
                "created_at": row.get("createdAt"),
                "decimals": row.get("decimals"),
                "price_change_24h": row.get("priceChange24h"),
            },
        }

    return out

def _fetch_coingecko_reference_prices_usd(tokens: list[str]) -> dict:
    """
    Fetch fresh USD reference prices from CoinGecko for quote-time comparison.
    Returns:
        {
            "SOL": {
                "usd": 93.12,
                "coingecko_id": "solana",
                "last_updated_at": 1711788300,
                "last_updated_iso": "2026-03-30T06:45:00+00:00",
            },
            ...
        }
    """
    token_to_cg = {}
    for token in tokens:
        token = (token or "").strip().upper()
        cg_id = _coingecko_id_for_quote_token(token)
        if not cg_id:
            continue
        token_to_cg[token] = cg_id

    if not token_to_cg:
        return {}

    ids = ",".join(sorted(set(token_to_cg.values())))

    resp = requests.get(
        "https://api.coingecko.com/api/v3/simple/price",
        params={
            "ids": ids,
            "vs_currencies": "usd",
            "include_last_updated_at": "true",
        },
        timeout=10,
        headers={"accept": "application/json"},
    )
    resp.raise_for_status()
    data = resp.json()

    out = {}
    for token, cg_id in token_to_cg.items():
        row = data.get(cg_id) or {}
        usd = row.get("usd")
        last_updated_at = row.get("last_updated_at")

        if usd is None:
            continue

        out[token] = {
            "usd": float(usd),
            "coingecko_id": cg_id,
            "last_updated_at": last_updated_at,
            "last_updated_iso": (
                datetime.fromtimestamp(last_updated_at, tz=timezone.utc).isoformat()
                if last_updated_at
                else None
            ),
        }

    for token in list(out.keys()):
        out[token]["pricing_source"] = "coingecko_simple_price"
        out[token]["pricing_ts"] = out[token].get("last_updated_iso")
        out[token]["pricing_source_detail"] = {
            "from_token_coingecko_id": out[token].get("coingecko_id"),
            "from_token_last_updated_at": out[token].get("last_updated_iso"),
        }

    return out


def _fetch_sqlite_reference_prices_usd(tokens: list[str]) -> dict:
    out = {}

    for token in tokens:
        token = (token or "").strip().upper()
        if not token:
            continue

        if token == "USDC":
            out[token] = {
                "usd": 1.0,
                "pricing_source": "sqlite_usd_snapshots",
                "pricing_ts": None,
                "pricing_source_detail": {"asset": "usdc"},
            }
            continue

        row = call_with_supported_kwargs(
            db.get_latest_price,
            asset=token.lower(),
            currency="usd",
        )
        if not row:
            continue

        price = _extract_price_number(row)
        if price is None:
            continue

        pricing_ts = None
        if isinstance(row, dict):
            pricing_ts = row.get("ts") or row.get("timestamp")
        elif isinstance(row, (list, tuple)) and row:
            head = row[0]
            if isinstance(head, str):
                pricing_ts = head

        out[token] = {
            "usd": price,
            "pricing_source": "sqlite_usd_snapshots",
            "pricing_ts": pricing_ts,
            "pricing_source_detail": {"asset": token.lower()},
        }

    return out


def _resolve_from_major_benchmark_source(tokens: list[str]) -> dict:
    return _fetch_coingecko_reference_prices_usd(tokens)


def _resolve_from_solana_native_benchmark_source(tokens: list[str]) -> dict:
    return _fetch_jupiter_price_v3_reference_prices_usd(tokens)


def _resolve_from_long_tail_benchmark_source(tokens: list[str]) -> dict:
    return {}


def _resolve_from_sqlite_fallback(tokens: list[str]) -> dict:
    return _fetch_sqlite_reference_prices_usd(tokens)


def _resolve_quote_benchmark_prices_usd(tokens: list[str]) -> dict:
    resolved = {}

    for resolver in (
        _resolve_from_solana_native_benchmark_source,
        _resolve_from_major_benchmark_source,
        _resolve_from_long_tail_benchmark_source,
        _resolve_from_sqlite_fallback,
    ):
        missing = [token for token in tokens if token not in resolved]
        if not missing:
            break

        try:
            resolved.update(resolver(missing))
        except Exception:
            pass

    return resolved


def _resolve_quote_reference_prices_usd(tokens: list[str]) -> dict:
    return _resolve_quote_benchmark_prices_usd(tokens)


def _build_reference_baseline_from_resolved_prices(
    from_token: str,
    to_token: str,
    amount: float,
    best_output_amount: float | None,
    from_row: dict | None,
    to_row: dict | None,
):
    if not from_row or not to_row or to_row["usd"] <= 0:
        return None, None

    input_usd_price = float(from_row["usd"])
    output_usd_price = float(to_row["usd"])
    input_usd_value = amount * input_usd_price
    ideal_output_amount = input_usd_value / output_usd_price

    baseline = {
        "label": "Theoretical reference baseline",
        "is_executable": False,
        "input_amount": amount,
        "input_token": from_token,
        "input_usd_price": input_usd_price,
        "input_usd_value": input_usd_value,
        "ideal_output_amount": ideal_output_amount,
        "output_token": to_token,
        "output_usd_price": output_usd_price,
        "output_usd_value": ideal_output_amount * output_usd_price,
        "pricing_source": (
            from_row.get("pricing_source")
            or to_row.get("pricing_source")
            or "coingecko_simple_price"
        ),
        "pricing_ts": from_row.get("pricing_ts") or to_row.get("pricing_ts"),
        "pricing_source_detail": {
            "from_token": from_row.get("pricing_source_detail"),
            "to_token": to_row.get("pricing_source_detail"),
        },
        "note": "Fresh market reference for quote comparison. Not an executable quote.",
    }

    baseline_vs_recommended = None
    if best_output_amount is not None and ideal_output_amount:
        diff_abs = best_output_amount - ideal_output_amount
        diff_pct = (diff_abs / ideal_output_amount) * 100

        baseline_vs_recommended = {
            "output_diff_abs": diff_abs,
            "output_diff_pct": diff_pct,
            "note": "Difference between the fresh theoretical reference and the current recommended executable route.",
        }

    return baseline, baseline_vs_recommended


def _build_fresh_quote_reference_baseline(
    from_token: str,
    to_token: str,
    amount: float,
    best_output_amount: float | None,
    fallback_input_usd_value: float | None,
    reference_prices: dict | None = None,
):
    """
    Try to build a quote-time theoretical reference baseline from resolved prices.
    If that fails, fall back to the existing cached/sqlite baseline helper.
    """
    try:
        fresh_prices = reference_prices or {}
        baseline, baseline_vs_recommended = _build_reference_baseline_from_resolved_prices(
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            best_output_amount=best_output_amount,
            from_row=fresh_prices.get(from_token),
            to_row=fresh_prices.get(to_token),
        )
        if baseline:
            return baseline, baseline_vs_recommended

    except Exception:
        pass

    # Fallback to existing cached/sqlite-based baseline so quote preview never breaks
    return _build_inline_baseline(
        from_token=from_token,
        to_token=to_token,
        amount=amount,
        fallback_input_usd_value=fallback_input_usd_value,
        best_output_amount=best_output_amount,
    )







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


def _public_swap_token_meta(symbol: str, meta: dict) -> dict:
    return {
        "symbol": symbol,
        "display_name": meta.get("display_name") or meta.get("name") or symbol,
        "mint": meta.get("mint"),
        "decimals": meta.get("decimals"),
        "tags": meta.get("tags") or [],
        "verified": bool(meta.get("verified")),
        "default_enabled": bool(meta.get("default_enabled")),
    }


@app.get("/swap/tokens")
def swap_tokens():
    tokens = []
    for symbol, meta in TOKEN_META.items():
        if not meta.get("default_enabled"):
            continue
        public_meta = _public_swap_token_meta(symbol, meta)
        if not public_meta.get("mint") or public_meta.get("decimals") is None:
            continue
        tokens.append(public_meta)

    return {"ok": True, "tokens": tokens}


JUP_API_KEY = os.environ.get("JUP_API_KEY", "").strip()

def to_raw_amount(amount: float, decimals: int) -> int:
    raw = round(amount * (10 ** decimals))
    if raw <= 0:
        raise HTTPException(status_code=400, detail="amount is too small after decimal conversion")
    return raw



def _safe_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _ui_amount(raw_value, decimals: int):
    try:
        if raw_value is None:
            return None
        return int(raw_value) / (10 ** decimals)
    except Exception:
        return None


def _route_steps(route_plan: list[dict]) -> list[dict]:
    steps = []
    for leg in route_plan or []:
        swap_info = leg.get("swapInfo") or {}
        steps.append(
            {
                "label": swap_info.get("label"),
                "percent": leg.get("percent"),
                "input_mint": swap_info.get("inputMint"),
                "output_mint": swap_info.get("outputMint"),
                "in_amount_raw": swap_info.get("inAmount"),
                "out_amount_raw": swap_info.get("outAmount"),
            }
        )
    return steps


def _route_labels(route_plan: list[dict]) -> list[str]:
    out = []
    seen = set()
    for step in _route_steps(route_plan):
        label = step.get("label")
        if label and label not in seen:
            seen.add(label)
            out.append(label)
    return out


def _build_option_explanation(
    *,
    only_direct_routes: bool,
    restrict_intermediate_tokens: bool,
    route_labels: list[str],
    route_plan: list[dict],
) -> str:
    parts = []

    if only_direct_routes:
        parts.append("Direct-route-only check.")
    elif restrict_intermediate_tokens:
        parts.append("Stable-token intermediate restriction enabled.")
    else:
        parts.append("Broader routing search with intermediate restriction relaxed.")

    if route_labels:
        parts.append("Uses " + " → ".join(route_labels[:3]) + ".")

    if len(route_plan) > 1:
        parts.append(f"Route plan has {len(route_plan)} legs.")
    elif len(route_plan) == 1:
        parts.append("Single-leg route plan.")

    return " ".join(parts)


def _fetch_jupiter_swap_instructions(
    *,
    quote_response: dict,
    user_public_key: str,
    as_legacy_transaction: bool = True,
) -> dict:
    url = "https://api.jup.ag/swap/v1/swap-instructions"

    payload = {
        "userPublicKey": user_public_key,
        "quoteResponse": quote_response,
        "wrapAndUnwrapSol": True,
        "useSharedAccounts": True,
        "dynamicComputeUnitLimit": True,
        "asLegacyTransaction": as_legacy_transaction,
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    jup_api_key = os.getenv("JUP_API_KEY")
    if jup_api_key:
        headers["x-api-key"] = jup_api_key

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=e.code, detail=f"Jupiter swap-instructions HTTP error: {body}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jupiter swap-instructions request failed: {e}")



SOLANA_MAINNET_RPC_URL = os.environ.get(
    "SOLANA_MAINNET_RPC_URL",
    "https://api.mainnet-beta.solana.com",
).strip()


def _solana_rpc_call(
    rpc_url: str,
    method: str,
    params: list | None = None,
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or [],
    }

    try:
        resp = requests.post(
            rpc_url,
            json=payload,
            timeout=20,
            headers={"accept": "application/json", "content-type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Solana RPC request failed: {e}")

    if isinstance(data, dict) and data.get("error"):
        raise HTTPException(status_code=502, detail=f"Solana RPC error: {data['error']}")

    return data


def _estimate_swap_network_fee_lamports(
    *,
    quote_response: dict,
    user_public_key: str,
    rpc_url: str,
    as_legacy_transaction: bool = True,
) -> dict:
    """
    Backend-owned fee estimation for a Jupiter quote.

    For now this estimates the signature/network fee conservatively via
    getFeeForMessage using a legacy-style minimal message placeholder.
    It does not attempt to fully serialize every Jupiter instruction yet.
    That is acceptable for this sprint because the main goal is to move
    ownership and error handling into the backend.
    """
    if not quote_response or not isinstance(quote_response, dict):
        return {
            "ok": False,
            "lamports": None,
            "sol": None,
            "scope": "invalid_quote_response",
            "reason": "invalid_quote_response",
            "detail": "quote_response missing or invalid",
        }

    if not user_public_key:
        return {
            "ok": False,
            "lamports": None,
            "sol": None,
            "scope": "wallet_not_connected",
            "reason": "wallet_not_connected",
            "detail": "user_public_key is required for fee estimation",
        }

    try:
        instructions = _fetch_jupiter_swap_instructions(
            quote_response=quote_response,
            user_public_key=user_public_key,
            as_legacy_transaction=as_legacy_transaction,
        )

        if not isinstance(instructions, dict):
            return {
                "ok": False,
                "lamports": None,
                "sol": None,
                "scope": "instructions_unavailable",
                "reason": "instructions_unavailable",
                "detail": "swap instructions response was not a dict",
            }

        # We only need a recent blockhash + fee-for-message call on backend.
        # For this sprint, use a minimal legacy-message placeholder and keep
        # failures explicit instead of hiding them in the browser.
        latest_blockhash_resp = _solana_rpc_call(
            rpc_url,
            "getLatestBlockhash",
            [{"commitment": "confirmed"}],
        )

        _ = latest_blockhash_resp.get("result", {}).get("value", {}).get("blockhash")

        fallback_lamports = 5000

        try:
            fee_resp = _solana_rpc_call(
                rpc_url,
                "getFees",
                [{"commitment": "confirmed"}],
            )

            fee_value = fee_resp.get("result", {}).get("value", {})
            lamports_per_signature = fee_value.get("feeCalculator", {}).get("lamportsPerSignature")

            if isinstance(lamports_per_signature, int):
                lamports = lamports_per_signature
                return {
                    "ok": True,
                    "lamports": lamports,
                    "sol": lamports / 1_000_000_000,
                    "scope": "solana_signature_fee_mainnet_estimate",
                    "reason": None,
                    "detail": None,
                }
        except HTTPException:
            pass
        except Exception:
            pass

        return {
            "ok": True,
            "lamports": fallback_lamports,
            "sol": fallback_lamports / 1_000_000_000,
            "scope": "solana_fallback_signature_fee_estimate",
            "reason": "fallback_used",
            "detail": "Used fallback signature-fee estimate because the RPC fee method was unavailable.",
        }

    except HTTPException as e:
        return {
            "ok": False,
            "lamports": None,
            "sol": None,
            "scope": "estimation_failed",
            "reason": "http_exception",
            "detail": e.detail,
        }
    except Exception as e:
        return {
            "ok": False,
            "lamports": None,
            "sol": None,
            "scope": "estimation_failed",
            "reason": "unexpected_error",
            "detail": str(e),
        }


def _attach_backend_network_fee_estimate(
    option: dict | None,
    *,
    user_public_key: str | None,
    rpc_url: str,
) -> dict | None:
    if not option:
        return option

    if not user_public_key:
        option["estimated_network_fee"] = None
        option["network_fee_scope"] = "wallet_not_connected"
        option["network_fee_detail"] = None
        return option

    fee_result = _estimate_swap_network_fee_lamports(
        quote_response=option.get("raw_quote"),
        user_public_key=user_public_key,
        rpc_url=rpc_url,
        as_legacy_transaction=True,
    )

    if fee_result.get("ok"):
        option["estimated_network_fee"] = {
            "lamports": fee_result.get("lamports"),
            "sol": fee_result.get("sol"),
        }
    else:
        option["estimated_network_fee"] = None

    option["network_fee_scope"] = fee_result.get("scope")
    option["network_fee_detail"] = fee_result.get("detail")

    return option




def _fetch_jupiter_quote(params: dict) -> dict:
    url = "https://api.jup.ag/swap/v1/quote?" + urllib.parse.urlencode(params)

    headers = {
        "Accept": "application/json",
    }

    jup_api_key = os.getenv("JUP_API_KEY")
    if jup_api_key:
        headers["x-api-key"] = jup_api_key

    req = urllib.request.Request(
        url,
        headers=headers,
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=e.code, detail=f"Jupiter HTTP error: {body}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Jupiter request failed: {e}")


def _try_fetch_jupiter_quote(params: dict) -> dict:
    try:
        return {"ok": True, "data": _fetch_jupiter_quote(params)}
    except HTTPException as e:
        return {
            "ok": False,
            "error": {
                "status_code": e.status_code,
                "detail": e.detail,
            },
        }


def _build_raydium_quote_params(
    *,
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int = 50,
    tx_version: str = "V0",
) -> dict:
    return {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_raw),
        "slippageBps": str(slippage_bps),
        "txVersion": tx_version,
    }


def _fetch_raydium_quote(params: dict) -> dict:
    url = "https://transaction-v1.raydium.io/compute/swap-base-in?" + urllib.parse.urlencode(
        params
    )

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

            if payload.get("success") is False:
                detail = payload.get("msg") or "Raydium quote request was not successful"
                raise HTTPException(status_code=502, detail=f"Raydium quote failed: {detail}")

            return payload
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=e.code, detail=f"Raydium HTTP error: {body}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Raydium request failed: {e}")


def _try_fetch_raydium_quote(params: dict) -> dict:
    try:
        return {"ok": True, "data": _fetch_raydium_quote(params)}
    except HTTPException as e:
        return {
            "ok": False,
            "error": {
                "status_code": e.status_code,
                "detail": e.detail,
            },
        }


METEORA_DLMM_SOL_MINT = "So11111111111111111111111111111111111111112"
METEORA_DLMM_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
METEORA_DLMM_SOL_USDC_CANDIDATE = {
    "address": "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
    "name": "SOL-USDC",
    "token_x": METEORA_DLMM_SOL_MINT,
    "token_y": METEORA_DLMM_USDC_MINT,
    "bin_step": 4,
}

ORCA_WHIRLPOOL_SOL_MINT = "So11111111111111111111111111111111111111112"
ORCA_WHIRLPOOL_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

PHOENIX_SOL_MINT = "So11111111111111111111111111111111111111112"
PHOENIX_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PHOENIX_SOL_USDC_MARKET = {
    "address": "4DoNfFBfF7UokCC2FQzriy7yHK6DY6NVdYpuekQ5pRgg",
    "name": "SOL/USDC",
    "base_mint": PHOENIX_SOL_MINT,
    "quote_mint": PHOENIX_USDC_MINT,
}


def _build_meteora_dlmm_quote_payload(
    *,
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int = 50,
    rpc_url: str | None = None,
) -> dict:
    pool_candidates = []
    mint_pair = {input_mint, output_mint}
    if mint_pair == {METEORA_DLMM_SOL_MINT, METEORA_DLMM_USDC_MINT}:
        pool_candidates.append(dict(METEORA_DLMM_SOL_USDC_CANDIDATE))

    return {
        "rpc_url": rpc_url or os.getenv("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com",
        "input_mint": input_mint,
        "output_mint": output_mint,
        "amount_raw": str(amount_raw),
        "slippage_bps": int(slippage_bps),
        "pool_candidates": pool_candidates,
    }


def _fetch_meteora_dlmm_quote(payload: dict) -> dict:
    helper_path = project_root() / "tools" / "meteora_dlmm_quote.mjs"
    if not helper_path.exists():
        raise HTTPException(status_code=502, detail=f"Meteora DLMM helper missing: {helper_path}")

    try:
        proc = subprocess.run(
            [os.getenv("NODE_BINARY") or "node", str(helper_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=20,
            cwd=project_root(),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=502, detail=f"Meteora DLMM helper runtime missing: {e}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Meteora DLMM helper timed out")

    stdout = (proc.stdout or "").strip()
    if not stdout:
        stderr = (proc.stderr or "").strip()
        raise HTTPException(
            status_code=502,
            detail=f"Meteora DLMM helper returned no JSON output: {stderr[-500:]}",
        )

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Meteora DLMM helper returned invalid JSON: {e}")

    if proc.returncode != 0 and parsed.get("ok") is not False:
        detail = parsed.get("error") or (proc.stderr or "").strip()
        raise HTTPException(status_code=502, detail=f"Meteora DLMM helper failed: {detail}")

    return parsed


def _try_fetch_meteora_dlmm_quote(payload: dict) -> dict:
    try:
        data = _fetch_meteora_dlmm_quote(payload)
        if data.get("ok") is True:
            return {"ok": True, "data": data}

        error = data.get("error") if isinstance(data, dict) else None
        return {
            "ok": False,
            "error": {
                "status_code": 502,
                "detail": error.get("message") if isinstance(error, dict) else "Meteora DLMM quote failed",
                "code": error.get("code") if isinstance(error, dict) else None,
                "helper_error": error,
            },
        }
    except HTTPException as e:
        return {
            "ok": False,
            "error": {
                "status_code": e.status_code,
                "detail": e.detail,
            },
        }


def _build_orca_whirlpool_quote_payload(
    *,
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int = 50,
    rpc_url: str | None = None,
) -> dict:
    payload = {
        "rpc_url": rpc_url or os.getenv("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com",
        "input_mint": input_mint,
        "output_mint": output_mint,
        "amount_raw": str(amount_raw),
        "slippage_bps": int(slippage_bps),
        "pool_candidates": [],
    }

    if input_mint != ORCA_WHIRLPOOL_SOL_MINT or output_mint != ORCA_WHIRLPOOL_USDC_MINT:
        payload["unsupported_pair"] = True
        payload["unsupported_pair_detail"] = (
            "Orca Whirlpool quote helper currently supports SOL -> USDC only."
        )

    return payload


def _fetch_orca_whirlpool_quote(payload: dict) -> dict:
    if payload.get("unsupported_pair"):
        raise HTTPException(
            status_code=400,
            detail=payload.get("unsupported_pair_detail") or "Unsupported Orca Whirlpool quote pair",
        )

    helper_path = project_root() / "tools" / "orca_whirlpool_quote_research.mjs"
    if not helper_path.exists():
        raise HTTPException(status_code=502, detail=f"Orca Whirlpool helper missing: {helper_path}")

    try:
        proc = subprocess.run(
            [os.getenv("NODE_BINARY") or "node", str(helper_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=20,
            cwd=project_root(),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=502, detail=f"Orca Whirlpool helper runtime missing: {e}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Orca Whirlpool helper timed out")

    stdout = (proc.stdout or "").strip()
    if not stdout:
        stderr = (proc.stderr or "").strip()
        raise HTTPException(
            status_code=502,
            detail=f"Orca Whirlpool helper returned no JSON output: {stderr[-500:]}",
        )

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Orca Whirlpool helper returned invalid JSON: {e}")

    if proc.returncode != 0 and parsed.get("ok") is not False:
        detail = parsed.get("error") or (proc.stderr or "").strip()
        raise HTTPException(status_code=502, detail=f"Orca Whirlpool helper failed: {detail}")

    return parsed


def _try_fetch_orca_whirlpool_quote(payload: dict) -> dict:
    try:
        data = _fetch_orca_whirlpool_quote(payload)
        if data.get("ok") is True:
            return {"ok": True, "data": data}

        error = data.get("error") if isinstance(data, dict) else None
        return {
            "ok": False,
            "error": {
                "status_code": 502,
                "detail": error.get("message") if isinstance(error, dict) else "Orca Whirlpool quote failed",
                "code": error.get("code") if isinstance(error, dict) else None,
                "helper_error": error,
            },
        }
    except HTTPException as e:
        return {
            "ok": False,
            "error": {
                "status_code": e.status_code,
                "detail": e.detail,
            },
        }


def _build_phoenix_quote_payload(
    *,
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int = 50,
    rpc_url: str | None = None,
) -> dict:
    market_candidates = []
    if input_mint == PHOENIX_SOL_MINT and output_mint == PHOENIX_USDC_MINT:
        market_candidates.append(dict(PHOENIX_SOL_USDC_MARKET))

    payload = {
        "rpc_url": rpc_url or os.getenv("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com",
        "input_mint": input_mint,
        "output_mint": output_mint,
        "amount_raw": str(amount_raw),
        "slippage_bps": int(slippage_bps),
        "market_candidates": market_candidates,
    }

    if input_mint != PHOENIX_SOL_MINT or output_mint != PHOENIX_USDC_MINT:
        payload["unsupported_pair"] = True
        payload["unsupported_pair_detail"] = (
            "Phoenix quote helper currently supports SOL -> USDC only."
        )

    return payload


def _fetch_phoenix_quote(payload: dict) -> dict:
    if payload.get("unsupported_pair"):
        raise HTTPException(
            status_code=400,
            detail=payload.get("unsupported_pair_detail") or "Unsupported Phoenix quote pair",
        )

    helper_path = project_root() / "tools" / "phoenix_quote_research.mjs"
    if not helper_path.exists():
        raise HTTPException(status_code=502, detail=f"Phoenix helper missing: {helper_path}")

    try:
        proc = subprocess.run(
            [os.getenv("NODE_BINARY") or "node", str(helper_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=20,
            cwd=project_root(),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=502, detail=f"Phoenix helper runtime missing: {e}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Phoenix helper timed out")

    stdout = (proc.stdout or "").strip()
    if not stdout:
        stderr = (proc.stderr or "").strip()
        raise HTTPException(
            status_code=502,
            detail=f"Phoenix helper returned no JSON output: {stderr[-500:]}",
        )

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Phoenix helper returned invalid JSON: {e}")

    if proc.returncode != 0 and parsed.get("ok") is not False:
        detail = parsed.get("error") or (proc.stderr or "").strip()
        raise HTTPException(status_code=502, detail=f"Phoenix helper failed: {detail}")

    return parsed


def _try_fetch_phoenix_quote(payload: dict) -> dict:
    try:
        data = _fetch_phoenix_quote(payload)
        if data.get("ok") is True:
            return {"ok": True, "data": data}

        error = data.get("error") if isinstance(data, dict) else None
        return {
            "ok": False,
            "error": {
                "status_code": 502,
                "detail": error.get("message") if isinstance(error, dict) else "Phoenix quote failed",
                "code": error.get("code") if isinstance(error, dict) else None,
                "helper_error": error,
            },
        }
    except HTTPException as e:
        return {
            "ok": False,
            "error": {
                "status_code": e.status_code,
                "detail": e.detail,
            },
        }



PHANTOM_SOL_MINT = "So11111111111111111111111111111111111111112"
PHANTOM_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _build_phantom_quote_payload(
    *,
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int = 50,
    user_public_key: str | None = None,
) -> dict:
    payload = {
        "sell_chain_id": "solana:mainnet",
        "sell_token_is_native": input_mint == PHANTOM_SOL_MINT,
        "buy_token_mint": output_mint,
        "amount": str(amount_raw),
        "amount_unit": "base",
        "slippage_bps": int(slippage_bps),
        "taker_address": user_public_key,
    }

    if input_mint != PHANTOM_SOL_MINT or output_mint != PHANTOM_USDC_MINT:
        payload["unsupported_pair"] = True
        payload["unsupported_pair_detail"] = (
            "Phantom quote research helper currently supports SOL -> USDC only."
        )

    if not user_public_key:
        payload["skip_reason"] = "wallet_public_key_required_for_phantom_quote"

    return payload


def _fetch_phantom_quote(payload: dict) -> dict:
    if payload.get("unsupported_pair"):
        raise HTTPException(
            status_code=400,
            detail=payload.get("unsupported_pair_detail") or "Unsupported Phantom quote pair",
        )

    if not payload.get("taker_address"):
        raise HTTPException(
            status_code=400,
            detail="Phantom quote requires user_public_key as taker_address",
        )

    helper_path = project_root() / "tools" / "phantom_quote_research.mjs"
    if not helper_path.exists():
        raise HTTPException(status_code=502, detail=f"Phantom quote helper missing: {helper_path}")

    try:
        proc = subprocess.run(
            [os.getenv("NODE_BINARY") or "node", str(helper_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=20,
            cwd=project_root(),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=502, detail=f"Phantom quote helper runtime missing: {e}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Phantom quote helper timed out")

    stdout = (proc.stdout or "").strip()
    if not stdout:
        stderr = (proc.stderr or "").strip()
        raise HTTPException(
            status_code=502,
            detail=f"Phantom quote helper returned no JSON output: {stderr[-500:]}",
        )

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Phantom quote helper returned invalid JSON: {e}")

    if proc.returncode != 0 and parsed.get("ok") is not False:
        detail = parsed.get("error") or (proc.stderr or "").strip()
        raise HTTPException(status_code=502, detail=f"Phantom quote helper failed: {detail}")

    return parsed


def _try_fetch_phantom_quote(payload: dict) -> dict:
    try:
        data = _fetch_phantom_quote(payload)
        if data.get("ok") is True:
            return {"ok": True, "data": data}

        error = data.get("error") if isinstance(data, dict) else None
        return {
            "ok": False,
            "error": {
                "status_code": data.get("status_code") if isinstance(data, dict) else 502,
                "detail": error.get("message") if isinstance(error, dict) else "Phantom quote failed",
                "code": error.get("code") if isinstance(error, dict) else None,
                "helper_error": error,
                "helper_response": data,
            },
        }
    except HTTPException as e:
        return {
            "ok": False,
            "error": {
                "status_code": e.status_code,
                "detail": e.detail,
            },
        }


TOKEN_META_BY_MINT = {
    (meta.get("mint") or "").strip(): {"symbol": symbol, **meta}
    for symbol, meta in TOKEN_META.items()
    if isinstance(meta, dict) and meta.get("mint")
}


def _mint_meta(fee_mint: str | None) -> dict | None:
    if not fee_mint:
        return None
    return TOKEN_META_BY_MINT.get((fee_mint or "").strip())


def _extract_explicit_route_fees(quote: dict) -> dict:
    platform_fee = quote.get("platformFee")
    route_plan = quote.get("routePlan") or []

    route_fee_items = []
    for leg in route_plan:
        swap_info = leg.get("swapInfo") or {}
        fee_amount_raw = swap_info.get("feeAmount")
        fee_mint = swap_info.get("feeMint")

        if fee_amount_raw in (None, "", "0", 0):
            continue

        mint_meta = _mint_meta(fee_mint)
        decimals = mint_meta.get("decimals") if mint_meta else None
        fee_token = mint_meta.get("symbol") if mint_meta else None

        route_fee_items.append(
            {
                "label": swap_info.get("label"),
                "fee_amount_raw": str(fee_amount_raw),
                "fee_amount": (
                    _ui_amount(fee_amount_raw, decimals)
                    if decimals is not None
                    else None
                ),
                "fee_mint": fee_mint,
                "fee_token": fee_token,
            }
        )

    return {
        "platform_fee": platform_fee,
        "route_fee_items": route_fee_items,
        "has_explicit_fees": bool(platform_fee) or bool(route_fee_items),
    }


def _raydium_route_steps(route_plan: list[dict]) -> list[dict]:
    steps = []
    for leg in route_plan or []:
        steps.append(
            {
                "label": "Raydium",
                "percent": leg.get("percent"),
                "input_mint": leg.get("inputMint"),
                "output_mint": leg.get("outputMint"),
                "in_amount_raw": leg.get("inputAmount"),
                "out_amount_raw": leg.get("outputAmount"),
            }
        )
    return steps


def _extract_raydium_route_fees(quote_data: dict) -> dict:
    route_plan = quote_data.get("routePlan") or []
    route_fee_items = []

    for leg in route_plan:
        fee_amount_raw = leg.get("feeAmount")
        fee_mint = leg.get("feeMint")

        if fee_amount_raw in (None, "", "0", 0):
            continue

        mint_meta = _mint_meta(fee_mint)
        decimals = mint_meta.get("decimals") if mint_meta else None
        fee_token = mint_meta.get("symbol") if mint_meta else None

        route_fee_items.append(
            {
                "label": "Raydium",
                "fee_amount_raw": str(fee_amount_raw),
                "fee_amount": (
                    _ui_amount(fee_amount_raw, decimals)
                    if decimals is not None
                    else None
                ),
                "fee_mint": fee_mint,
                "fee_token": fee_token,
            }
        )

    return {
        "platform_fee": None,
        "route_fee_items": route_fee_items,
        "has_explicit_fees": bool(route_fee_items),
    }


def _extract_meteora_dlmm_route_fees(quote: dict) -> dict:
    route_fee_items = []
    fee_mint = quote.get("input_mint")
    mint_meta = _mint_meta(fee_mint)
    decimals = mint_meta.get("decimals") if mint_meta else None
    fee_token = mint_meta.get("symbol") if mint_meta else None

    for raw_key, label in (
        ("fee_raw", "Meteora DLMM swap fee"),
        ("protocol_fee_raw", "Meteora DLMM protocol fee"),
    ):
        fee_amount_raw = quote.get(raw_key)
        if fee_amount_raw in (None, "", "0", 0):
            continue

        route_fee_items.append(
            {
                "label": label,
                "fee_amount_raw": str(fee_amount_raw),
                "fee_amount": (
                    _ui_amount(fee_amount_raw, decimals)
                    if decimals is not None
                    else None
                ),
                "fee_mint": fee_mint,
                "fee_token": fee_token,
            }
        )

    return {
        "platform_fee": None,
        "route_fee_items": route_fee_items,
        "has_explicit_fees": bool(route_fee_items),
    }


def _extract_orca_whirlpool_route_fees(quote: dict) -> dict:
    route_fee_items = []
    fee_amount_raw = quote.get("fee_raw")
    fee_mint = quote.get("input_mint")
    mint_meta = _mint_meta(fee_mint)
    decimals = mint_meta.get("decimals") if mint_meta else None
    fee_token = mint_meta.get("symbol") if mint_meta else None

    if fee_amount_raw not in (None, "", "0", 0):
        route_fee_items.append(
            {
                "label": "Orca Whirlpool trade fee",
                "fee_amount_raw": str(fee_amount_raw),
                "fee_amount": (
                    _ui_amount(fee_amount_raw, decimals)
                    if decimals is not None
                    else None
                ),
                "fee_mint": fee_mint,
                "fee_token": fee_token,
            }
        )

    return {
        "platform_fee": None,
        "route_fee_items": route_fee_items,
        "has_explicit_fees": bool(route_fee_items),
    }


def _extract_phoenix_route_fees(quote: dict) -> dict:
    route_fee_items = []
    taker_fee_bps = quote.get("taker_fee_bps")

    if taker_fee_bps not in (None, ""):
        route_fee_items.append(
            {
                "label": "Phoenix taker fee",
                "fee_bps": taker_fee_bps,
                "fee_amount_raw": None,
                "fee_amount": None,
                "fee_mint": quote.get("output_mint"),
                "fee_token": "USDC",
            }
        )

    return {
        "platform_fee": None,
        "route_fee_items": route_fee_items,
        "has_explicit_fees": bool(route_fee_items),
    }


def _extract_phantom_route_fees(quote: dict) -> dict:
    first_quote = ((quote.get("quoteResponse") or {}).get("quotes") or [{}])[0] or {}
    route_fee_items = []

    for fee in first_quote.get("fees") or []:
        token = fee.get("token") or {}
        fee_mint = token.get("address")
        if not fee_mint and token.get("resourceType") == "nativeToken" and token.get("slip44") == "501":
            fee_mint = PHANTOM_SOL_MINT

        mint_meta = _mint_meta(fee_mint)
        decimals = mint_meta.get("decimals") if mint_meta else None
        fee_token = mint_meta.get("symbol") if mint_meta else None
        fee_amount_raw = fee.get("amount")

        route_fee_items.append(
            {
                "label": fee.get("name") or fee.get("type") or "Phantom disclosed fee",
                "fee_amount_raw": str(fee_amount_raw) if fee_amount_raw is not None else None,
                "fee_amount": (
                    _ui_amount(fee_amount_raw, decimals)
                    if fee_amount_raw is not None and decimals is not None
                    else None
                ),
                "fee_mint": fee_mint,
                "fee_token": fee_token,
                "fee_type": fee.get("type"),
                "percentage": fee.get("percentage"),
                "raw_fee": fee,
            }
        )

    return {
        "platform_fee": None,
        "route_fee_items": route_fee_items,
        "has_explicit_fees": bool(route_fee_items),
    }


def _compute_trade_execution_cost(
    reference_output_amount: float | None,
    quoted_output_amount: float | None,
    output_token: str | None,
) -> dict:
    if reference_output_amount is None or quoted_output_amount is None:
        return {
            "amount": None,
            "token": output_token,
            "reference_output_amount": reference_output_amount,
            "quoted_output_amount": quoted_output_amount,
            "raw_difference": None,
            "scope": "benchmark_shortfall_vs_fresh_reference",
            "floored_at_zero": True,
        }

    raw_difference = reference_output_amount - quoted_output_amount
    amount = max(0.0, raw_difference)

    return {
        "amount": amount,
        "token": output_token,
        "reference_output_amount": reference_output_amount,
        "quoted_output_amount": quoted_output_amount,
        "raw_difference": raw_difference,
        "scope": "benchmark_shortfall_vs_fresh_reference",
        "floored_at_zero": True,
    }


def _attach_cost_fields(
    option: dict | None,
    reference_output_amount: float | None,
) -> dict | None:
    if not option:
        return option

    quoted_output_amount = _safe_float(option.get("estimated_output"))
    trade_cost = _compute_trade_execution_cost(
        reference_output_amount=reference_output_amount,
        quoted_output_amount=quoted_output_amount,
        output_token=option.get("to_token"),
    )

    option["estimated_trade_execution_cost"] = trade_cost
    option["execution_cost"] = trade_cost.get("amount")
    option["cost_scope"] = trade_cost.get("scope")

    return option




def _sum_disclosed_route_fees_usd(
    explicit_route_fees: dict | None,
    reference_prices: dict | None,
) -> dict:
    """
    Sum only explicitly disclosed route fees that we can price in USD.
    Disclosure means the quote/provider exposed fee evidence, even if this
    backend cannot normalize or price every disclosed fee item.

    Returns:
        {
            "route_fees_usd": float | None,
            "route_fees_disclosed": bool,
            "priced_fee_items": [...],
            "unpriced_fee_items": [...],
        }
    """
    explicit_route_fees = explicit_route_fees or {}
    reference_prices = reference_prices or {}

    route_fee_items = explicit_route_fees.get("route_fee_items") or []
    route_fees_disclosed = bool(explicit_route_fees.get("has_explicit_fees"))

    total_usd = 0.0
    priced_fee_items = []
    unpriced_fee_items = []

    for item in route_fee_items:
        fee_amount = _safe_float(item.get("fee_amount"))
        fee_token = item.get("fee_token")

        if fee_amount is None or not fee_token:
            unpriced_fee_items.append(item)
            continue

        token_price_row = reference_prices.get(fee_token) or {}
        token_usd_price = _safe_float(token_price_row.get("usd"))

        if token_usd_price is None:
            unpriced_fee_items.append(item)
            continue

        fee_usd = fee_amount * token_usd_price
        total_usd += fee_usd

        priced_fee_items.append({
            **item,
            "fee_usd": fee_usd,
        })

    if not route_fees_disclosed:
        return {
            "route_fees_usd": None,
            "route_fees_disclosed": False,
            "priced_fee_items": [],
            "unpriced_fee_items": [],
        }

    return {
        "route_fees_usd": total_usd if priced_fee_items else None,
        "route_fees_disclosed": True,
        "priced_fee_items": priced_fee_items,
        "unpriced_fee_items": unpriced_fee_items,
    }


def _build_recommended_swap_cost_summary(
    option: dict | None,
    *,
    reference_prices: dict | None,
) -> dict | None:
    """
    Build the recommended-route cost summary in USD.

    Headline math rule:
    estimated_total_swap_cost_usd =
        execution_cost_usd
      + network_cost_usd
      + route_fees_usd (only when disclosed and priceable)
    """
    if not option:
        return None

    reference_prices = reference_prices or {}

    execution_cost = option.get("estimated_trade_execution_cost") or {}
    execution_cost_amount = _safe_float(execution_cost.get("amount"))
    execution_cost_token = execution_cost.get("token") or option.get("to_token")
    execution_price_row = reference_prices.get(execution_cost_token) or {}
    execution_token_usd_price = _safe_float(execution_price_row.get("usd"))
    execution_cost_usd = (
        execution_cost_amount * execution_token_usd_price
        if execution_cost_amount is not None and execution_token_usd_price is not None
        else None
    )

    network_fee = option.get("estimated_network_fee") or {}
    network_fee_sol = _safe_float(network_fee.get("sol"))

    sol_price_row = reference_prices.get("SOL") or {}
    sol_usd_price = _safe_float(sol_price_row.get("usd"))
    network_cost_usd = (
        network_fee_sol * sol_usd_price
        if network_fee_sol is not None and sol_usd_price is not None
        else None
    )

    route_fee_summary = _sum_disclosed_route_fees_usd(
        option.get("explicit_route_fees"),
        reference_prices=reference_prices,
    )
    route_fees_usd = route_fee_summary.get("route_fees_usd")
    route_fees_disclosed = bool(route_fee_summary.get("route_fees_disclosed"))

    known_parts = [
        x for x in [execution_cost_usd, network_cost_usd, route_fees_usd] if x is not None
    ]
    estimated_total_swap_cost_usd = sum(known_parts) if known_parts else None

    return {
        "execution_cost_usd": execution_cost_usd,
        "network_cost_usd": network_cost_usd,
        "route_fees_usd": route_fees_usd,
        "route_fees_disclosed": route_fees_disclosed,
        "estimated_total_swap_cost_usd": estimated_total_swap_cost_usd,
        "math_rule": "execution_cost_usd + network_cost_usd + disclosed_route_fees_usd_only",
        "route_fee_detail": route_fee_summary,
    }


def _attach_recommended_swap_cost_summary(
    option: dict | None,
    *,
    reference_prices: dict | None,
) -> dict | None:
    if not option:
        return option

    cost_summary = _build_recommended_swap_cost_summary(
        option,
        reference_prices=reference_prices,
    )

    option["swap_cost_summary"] = cost_summary

    if cost_summary:
        option["execution_cost_usd"] = cost_summary.get("execution_cost_usd")
        option["network_cost_usd"] = cost_summary.get("network_cost_usd")
        option["route_fees_usd"] = cost_summary.get("route_fees_usd")
        option["route_fees_disclosed"] = cost_summary.get("route_fees_disclosed")
        option["estimated_total_swap_cost_usd"] = cost_summary.get("estimated_total_swap_cost_usd")

    return option



def _build_cost_transparency(*, network_fee_scope: str) -> dict:
    return {
        "ranking_basis": "highest_receive_amount",
        "benchmark_gap_scope": "reference_comparison_not_fee",
        "explicit_fee_scope": "provider_disclosed_fee_evidence",
        "explicit_fees_may_be_reflected_in_output": True,
        "network_fee_scope": network_fee_scope,
        "cost_completeness": "partial",
    }




def _normalize_quote_option(
    *,
    variant_id: str,
    label: str,
    kind: str,
    quote: dict,
    from_token: str,
    to_token: str,
    input_amount: float,
    input_amount_raw: int,
    output_decimals: int,
    checked_params: dict,
) -> dict:
    route_plan = quote.get("routePlan") or []
    route_labels = _route_labels(route_plan)
    out_amount_raw = quote.get("outAmount")
    threshold_raw = quote.get("otherAmountThreshold")

    only_direct_routes = str(checked_params.get("onlyDirectRoutes", "false")).lower() == "true"
    restrict_intermediate_tokens = str(
        checked_params.get("restrictIntermediateTokens", "true")
    ).lower() == "true"
    execution_surface_label = "Jupiter"

    option = {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "jupiter-metis",
        "execution_surface_label": execution_surface_label,
        "quote_status": "live",
        "execution_status": "executable_capable",
        "supports_current_pair": True,
        "quote_source_type": "aggregator",
        "is_comparison_only": False,
        "is_clickable": True,
        "is_jupiter_only": True,
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": input_amount,
        "input_amount_raw": str(input_amount_raw),
        "estimated_output": _ui_amount(out_amount_raw, output_decimals),
        "estimated_output_raw": out_amount_raw,
        "min_received": _ui_amount(threshold_raw, output_decimals),
        "min_received_raw": threshold_raw,
        "estimated_total_swap_cost": None,
        "estimated_trade_execution_cost": None,
        "execution_cost": None,
        "cost_scope": "not_computed_yet",
        "cost_transparency": _build_cost_transparency(
            network_fee_scope="estimated_for_executable_when_available",
        ),
        "explicit_route_fees": _extract_explicit_route_fees(quote),
        "estimated_network_fee": None,
        "network_fee_scope": "not_estimated_yet",
        "price_impact_pct": _safe_float(quote.get("priceImpactPct")),
        "slippage_bps": quote.get("slippageBps"),
        "route_label": route_labels[0] if route_labels else None,
        "route_labels": route_labels,
        "route_steps": _route_steps(route_plan),
        "route_step_count": len(route_plan),
        "route_shape": (
            "direct"
            if only_direct_routes
            else ("single-path" if len(route_plan) == 1 else "multi-leg-or-split")
        ),
        "protections": {
            "slippage_bps": quote.get("slippageBps"),
            "restrict_intermediate_tokens": restrict_intermediate_tokens,
            "only_direct_routes": only_direct_routes,
        },
        "explanation": _build_option_explanation(
            only_direct_routes=only_direct_routes,
            restrict_intermediate_tokens=restrict_intermediate_tokens,
            route_labels=route_labels,
            route_plan=route_plan,
        ),
        "raw_quote": quote,
        "_sort_out_amount_raw": int(out_amount_raw) if out_amount_raw is not None else -1,
    }
    return option


def _normalize_raydium_quote_option(
    *,
    variant_id: str,
    label: str,
    kind: str,
    quote: dict,
    from_token: str,
    to_token: str,
    input_amount: float,
    input_amount_raw: int,
    output_decimals: int,
) -> dict:
    quote_data = quote.get("data") or {}
    route_plan = quote_data.get("routePlan") or []
    out_amount_raw = quote_data.get("outputAmount")
    threshold_raw = quote_data.get("otherAmountThreshold")

    option = {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "raydium-trade-api",
        "execution_surface_label": "Raydium",
        "quote_status": "live",
        "execution_status": "quote_only",
        "supports_current_pair": True,
        "quote_source_type": "venue_trade_api",
        "is_comparison_only": True,
        "is_clickable": False,
        "is_jupiter_only": False,
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": input_amount,
        "input_amount_raw": str(input_amount_raw),
        "estimated_output": _ui_amount(out_amount_raw, output_decimals),
        "estimated_output_raw": out_amount_raw,
        "min_received": _ui_amount(threshold_raw, output_decimals),
        "min_received_raw": threshold_raw,
        "estimated_total_swap_cost": None,
        "estimated_trade_execution_cost": None,
        "execution_cost": None,
        "cost_scope": "not_computed_yet",
        "cost_transparency": _build_cost_transparency(
            network_fee_scope="unavailable_for_quote_only_preview",
        ),
        "explicit_route_fees": _extract_raydium_route_fees(quote_data),
        "estimated_network_fee": None,
        "network_fee_scope": "not_estimated_in_preview",
        "network_fee_detail": "Raydium is quote-only in this preview path.",
        "price_impact_pct": _safe_float(quote_data.get("priceImpactPct")),
        "slippage_bps": quote_data.get("slippageBps"),
        "route_label": "Raydium",
        "route_labels": ["Raydium"],
        "route_steps": _raydium_route_steps(route_plan),
        "route_step_count": len(route_plan),
        "route_shape": "single-path" if len(route_plan) == 1 else "multi-leg-or-split",
        "protections": {
            "slippage_bps": quote_data.get("slippageBps"),
        },
        "explanation": "Raydium routed quote. Comparison-only for now.",
        "raw_quote": quote,
        "_sort_out_amount_raw": int(out_amount_raw) if out_amount_raw is not None else -1,
    }
    return option


def _normalize_meteora_dlmm_quote_option(
    *,
    variant_id: str,
    label: str,
    kind: str,
    quote: dict,
    from_token: str,
    to_token: str,
    input_amount: float,
    input_amount_raw: int,
    output_decimals: int,
) -> dict:
    pool = quote.get("pool") or {}
    out_amount_raw = quote.get("out_amount_raw")
    threshold_raw = quote.get("min_out_amount_raw")
    route_step = {
        "label": "Meteora DLMM",
        "pool_address": pool.get("address"),
        "pool_name": pool.get("name"),
        "bin_step": pool.get("bin_step"),
        "input_mint": quote.get("input_mint"),
        "output_mint": quote.get("output_mint"),
        "in_amount_raw": quote.get("in_amount_raw"),
        "out_amount_raw": out_amount_raw,
        "bin_arrays": quote.get("bin_arrays") or [],
    }

    return {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "meteora-dlmm",
        "execution_surface_label": "Meteora",
        "quote_status": "live",
        "execution_status": "quote_only",
        "supports_current_pair": True,
        "quote_source_type": "venue_native_pool",
        "is_comparison_only": True,
        "is_clickable": False,
        "is_jupiter_only": False,
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": input_amount,
        "input_amount_raw": str(input_amount_raw),
        "estimated_output": _ui_amount(out_amount_raw, output_decimals),
        "estimated_output_raw": out_amount_raw,
        "min_received": _ui_amount(threshold_raw, output_decimals),
        "min_received_raw": threshold_raw,
        "estimated_total_swap_cost": None,
        "estimated_trade_execution_cost": None,
        "execution_cost": None,
        "cost_scope": "not_computed_yet",
        "cost_transparency": _build_cost_transparency(
            network_fee_scope="unavailable_for_quote_only_preview",
        ),
        "explicit_route_fees": _extract_meteora_dlmm_route_fees(quote),
        "estimated_network_fee": None,
        "network_fee_scope": "not_estimated_in_preview",
        "network_fee_detail": "Meteora DLMM is quote-only in this preview path.",
        "price_impact_pct": _safe_float(quote.get("price_impact")),
        "slippage_bps": quote.get("slippage_bps"),
        "route_label": "Meteora DLMM",
        "route_labels": ["Meteora DLMM"],
        "route_steps": [route_step],
        "route_step_count": 1,
        "route_shape": "single-pool",
        "protections": {
            "slippage_bps": quote.get("slippage_bps"),
        },
        "explanation": "Meteora DLMM single-pool quote. Comparison-only for now.",
        "raw_quote": quote,
        "_sort_out_amount_raw": int(out_amount_raw) if out_amount_raw is not None else -1,
    }


def _normalize_orca_whirlpool_quote_option(
    *,
    variant_id: str,
    label: str,
    kind: str,
    quote: dict,
    from_token: str,
    to_token: str,
    input_amount: float,
    input_amount_raw: int,
    output_decimals: int,
) -> dict:
    pool = quote.get("pool") or {}
    out_amount_raw = quote.get("out_amount_raw")
    threshold_raw = quote.get("min_out_amount_raw")
    route_step = {
        "label": "Orca Whirlpool",
        "pool_address": pool.get("address"),
        "pool_name": pool.get("name"),
        "tick_spacing": pool.get("tick_spacing") or pool.get("tickSpacing"),
        "fee_rate": pool.get("fee_rate") or pool.get("feeRate"),
        "input_mint": quote.get("input_mint"),
        "output_mint": quote.get("output_mint"),
        "in_amount_raw": quote.get("in_amount_raw"),
        "out_amount_raw": out_amount_raw,
    }

    return {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "orca-whirlpool",
        "execution_surface_label": "Orca",
        "quote_status": "live",
        "execution_status": "quote_only",
        "supports_current_pair": True,
        "quote_source_type": "venue_native_pool_sdk",
        "is_comparison_only": True,
        "is_clickable": False,
        "is_jupiter_only": False,
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": input_amount,
        "input_amount_raw": str(input_amount_raw),
        "estimated_output": _ui_amount(out_amount_raw, output_decimals),
        "estimated_output_raw": out_amount_raw,
        "min_received": _ui_amount(threshold_raw, output_decimals),
        "min_received_raw": threshold_raw,
        "estimated_total_swap_cost": None,
        "estimated_trade_execution_cost": None,
        "execution_cost": None,
        "cost_scope": "not_computed_yet",
        "cost_transparency": _build_cost_transparency(
            network_fee_scope="unavailable_for_quote_only_preview",
        ),
        "explicit_route_fees": _extract_orca_whirlpool_route_fees(quote),
        "estimated_network_fee": None,
        "network_fee_scope": "not_estimated_in_preview",
        "network_fee_detail": "Orca Whirlpool is quote-only in this preview path.",
        "price_impact_pct": _safe_float(quote.get("price_impact")),
        "slippage_bps": quote.get("slippage_bps"),
        "route_label": "Orca Whirlpool",
        "route_labels": ["Orca"],
        "route_steps": [route_step],
        "route_step_count": 1,
        "route_shape": "single-pool",
        "protections": {
            "slippage_bps": quote.get("slippage_bps"),
        },
        "explanation": "Orca Whirlpool single-pool SDK quote. Comparison-only for now.",
        "raw_quote": quote,
        "_sort_out_amount_raw": int(out_amount_raw) if out_amount_raw is not None else -1,
    }


def _normalize_phoenix_quote_option(
    *,
    variant_id: str,
    label: str,
    kind: str,
    quote: dict,
    from_token: str,
    to_token: str,
    input_amount: float,
    input_amount_raw: int,
    output_decimals: int,
) -> dict:
    market = quote.get("market") or {}
    out_amount_raw = quote.get("out_amount_raw")
    threshold_raw = quote.get("min_out_amount_raw")
    route_step = {
        "label": "Phoenix CLOB",
        "market_address": market.get("address"),
        "market_name": market.get("name"),
        "top_bid": quote.get("top_bid"),
        "top_ask": quote.get("top_ask"),
        "fill_status": quote.get("fill_status"),
        "fully_filled": quote.get("fully_filled"),
        "input_mint": quote.get("input_mint"),
        "output_mint": quote.get("output_mint"),
        "in_amount_raw": quote.get("in_amount_raw"),
        "out_amount_raw": out_amount_raw,
    }

    return {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "phoenix-clob",
        "execution_surface_label": "Phoenix",
        "quote_status": "live",
        "execution_status": "quote_only",
        "supports_current_pair": True,
        "quote_source_type": "venue_clob_sdk",
        "is_comparison_only": True,
        "is_clickable": False,
        "is_jupiter_only": False,
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": input_amount,
        "input_amount_raw": str(input_amount_raw),
        "estimated_output": _ui_amount(out_amount_raw, output_decimals),
        "estimated_output_raw": out_amount_raw,
        "min_received": _ui_amount(threshold_raw, output_decimals),
        "min_received_raw": threshold_raw,
        "estimated_total_swap_cost": None,
        "estimated_trade_execution_cost": None,
        "execution_cost": None,
        "cost_scope": "not_computed_yet",
        "cost_transparency": _build_cost_transparency(
            network_fee_scope="unavailable_for_quote_only_preview",
        ),
        "explicit_route_fees": _extract_phoenix_route_fees(quote),
        "estimated_network_fee": None,
        "network_fee_scope": "not_estimated_in_preview",
        "network_fee_detail": "Phoenix CLOB is quote-only in this preview path.",
        "price_impact_pct": None,
        "slippage_bps": quote.get("slippage_bps"),
        "route_label": "Phoenix CLOB",
        "route_labels": ["Phoenix"],
        "route_steps": [route_step],
        "route_step_count": 1,
        "route_shape": "single-clob-market",
        "protections": {
            "slippage_bps": quote.get("slippage_bps"),
            "fill_status": quote.get("fill_status"),
            "fully_filled": quote.get("fully_filled"),
            "taker_fee_bps": quote.get("taker_fee_bps"),
        },
        "explanation": "Phoenix single-market CLOB SDK quote. Comparison-only for now.",
        "raw_quote": quote,
        "_sort_out_amount_raw": int(out_amount_raw) if out_amount_raw is not None else -1,
    }


def _normalize_phantom_quote_option(
    *,
    variant_id: str,
    label: str,
    kind: str,
    quote: dict,
    from_token: str,
    to_token: str,
    input_amount: float,
    input_amount_raw: int,
    output_decimals: int,
) -> dict:
    quote_response = quote.get("quoteResponse") or {}
    quotes = quote_response.get("quotes") or []
    first_quote = quotes[0] if quotes else {}
    out_amount_raw = quote.get("first_quote_buyAmount") or first_quote.get("buyAmount")
    base_provider = first_quote.get("baseProvider") or {}
    sources = first_quote.get("sources") or []
    route_label = base_provider.get("name") or "Phantom"
    route_labels = [
        source.get("name")
        for source in sources
        if isinstance(source, dict) and source.get("name")
    ] or [route_label]
    route_steps = [
        {
            "label": source.get("name"),
            "proportion": source.get("proportion"),
        }
        for source in sources
        if isinstance(source, dict)
    ]
    if not route_steps:
        route_steps = [{"label": route_label}]

    return {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "phantom-routing-api",
        "execution_surface_label": "Phantom",
        "quote_status": "live",
        "execution_status": "quote_only",
        "supports_current_pair": True,
        "quote_source_type": "wallet_routing_api",
        "is_comparison_only": True,
        "is_clickable": False,
        "is_official_quote": True,
        "is_jupiter_only": False,
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": input_amount,
        "input_amount_raw": str(input_amount_raw),
        "estimated_output": _ui_amount(out_amount_raw, output_decimals),
        "estimated_output_raw": out_amount_raw,
        "min_received": None,
        "min_received_raw": None,
        "estimated_total_swap_cost": None,
        "estimated_trade_execution_cost": None,
        "execution_cost": None,
        "cost_scope": "not_computed_yet",
        "cost_transparency": _build_cost_transparency(
            network_fee_scope="unavailable_for_quote_only_preview",
        ),
        "explicit_route_fees": _extract_phantom_route_fees(quote),
        "estimated_network_fee": None,
        "network_fee_scope": "not_estimated_in_preview",
        "network_fee_detail": "Phantom routing API is quote-only in this preview path.",
        "price_impact_pct": _safe_float(first_quote.get("priceImpact")),
        "slippage_bps": None,
        "route_label": route_label,
        "route_labels": route_labels,
        "route_steps": route_steps,
        "route_step_count": len(route_steps),
        "route_shape": "wallet-routing",
        "protections": {
            "slippage_tolerance": first_quote.get("slippageTolerance")
            or quote_response.get("slippageTolerance"),
            "simulation_failed": first_quote.get("simulationFailed"),
            "base_provider": base_provider,
        },
        "explanation": "Phantom routing API quote. Comparison-only for now.",
        "raw_quote": quote,
        "_sort_out_amount_raw": int(out_amount_raw) if out_amount_raw is not None else -1,
    }


def _dedupe_options(options: list[dict]) -> list[dict]:
    out = []
    seen = set()

    for opt in options:
        if not opt:
            continue

        key = (
            opt.get("provider"),
            opt.get("execution_surface_label"),
            opt.get("estimated_output_raw"),
            tuple(opt.get("route_labels") or []),
            opt.get("protections", {}).get("only_direct_routes"),
            opt.get("protections", {}).get("restrict_intermediate_tokens"),
        )

        if key in seen:
            continue

        seen.add(key)
        out.append(opt)

    return out


def _rank_quote_options(options: list[dict]) -> list[dict]:
    ranked = _dedupe_options(options)
    ranked.sort(key=lambda x: x.get("_sort_out_amount_raw", -1), reverse=True)
    return ranked


def _route_simplicity_rank(option: dict | None) -> tuple:
    if not option or option.get("supports_current_pair") is False:
        return (999, -1)

    route_shape = option.get("route_shape")
    route_step_count = option.get("route_step_count")
    if route_step_count is None:
        route_step_count = len(option.get("route_steps") or [])
    try:
        route_step_count = int(route_step_count)
    except Exception:
        route_step_count = 999

    shape_rank = {
        "single-pool": 0,
        "single-clob-market": 0,
        "direct": 1,
        "single-path": 2,
        "multi-leg-or-split": 5,
        "wallet-routing": 8,
    }.get(route_shape, 4)

    output_raw = option.get("_sort_out_amount_raw")
    if output_raw is None:
        try:
            output_raw = int(option.get("estimated_output_raw"))
        except Exception:
            output_raw = -1

    return (shape_rank + route_step_count, -int(output_raw))


def _select_direct_route_option(options: list[dict]) -> dict | None:
    candidates = [opt for opt in _dedupe_options(options) if opt.get("supports_current_pair") is not False]
    if not candidates:
        return None

    return sorted(candidates, key=_route_simplicity_rank)[0]


def _is_executable_quote_option(option: dict | None) -> bool:
    if not option:
        return False

    if option.get("is_comparison_only") is True:
        return False

    return option.get("is_clickable") is not False


def _quote_option_output_key(option: dict | None) -> tuple:
    if not option:
        return tuple()

    return (
        option.get("provider"),
        option.get("execution_surface_label"),
        option.get("variant_id"),
        option.get("estimated_output_raw"),
        tuple(option.get("route_labels") or []),
    )


def _same_quote_option(left: dict | None, right: dict | None) -> bool:
    return _quote_option_output_key(left) == _quote_option_output_key(right)


def _quote_option_universe_key(option: dict | None) -> tuple:
    if not option:
        return tuple()

    return (
        option.get("provider"),
        option.get("execution_surface_label"),
    )


def _select_diverse_other_options(
    ranked_options: list[dict],
    *,
    best_quote: dict | None,
    recommended: dict | None,
    direct: dict | None = None,
    limit: int | None = None,
) -> list[dict]:
    candidates = []
    for opt in ranked_options:
        if _same_quote_option(opt, best_quote):
            continue
        if _same_quote_option(opt, recommended):
            continue
        if _same_quote_option(opt, direct):
            continue
        candidates.append(opt)

    featured_universes = {
        key for key in (
            _quote_option_universe_key(best_quote),
            _quote_option_universe_key(recommended),
            _quote_option_universe_key(direct),
        )
        if key
    }

    selected = []
    selected_universes = set()
    for opt in candidates:
        key = _quote_option_universe_key(opt)
        if key in featured_universes:
            continue
        if key in selected_universes:
            continue

        selected_universes.add(key)
        selected.append(opt)

        if limit is not None and len(selected) >= limit:
            break

    return selected


def _with_quote_role(option: dict | None, *, kind: str, label: str) -> dict | None:
    if not option:
        return option

    return {
        **option,
        "kind": kind,
        "label": label,
    }


def _strip_internal_sort_key(option: dict | None) -> dict | None:
    if not option:
        return option
    option.pop("_sort_out_amount_raw", None)
    return option



def _extract_price_number(value) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        for key in ("price", "usd_price", "value"):
            v = value.get(key)
            if isinstance(v, (int, float)):
                return float(v)

    if isinstance(value, (list, tuple)):
        # Common pattern in this project: (ts, price)
        for item in reversed(value):
            if isinstance(item, (int, float)):
                return float(item)

    return None


def _latest_usd_price_for_token(token_symbol: str) -> float | None:
    token_symbol = (token_symbol or "").strip().upper()

    # Stable shortcut for now
    if token_symbol == "USDC":
        return 1.0

    row = call_with_supported_kwargs(
        db.get_latest_price,
        asset=token_symbol.lower(),
        currency="usd",
    )
    return _extract_price_number(row)






def _build_inline_baseline(
    from_token: str,
    to_token: str,
    amount: float,
    fallback_input_usd_value: float | None = None,
    best_output_amount: float | None = None,
):
    input_usd_price = _latest_usd_price_for_token(from_token)
    output_usd_price = _latest_usd_price_for_token(to_token)

    input_usd_value = None
    if input_usd_price is not None:
        input_usd_value = amount * input_usd_price
    else:
        input_usd_value = fallback_input_usd_value

    ideal_output_amount = None
    if input_usd_value is not None and output_usd_price is not None and output_usd_price > 0:
        ideal_output_amount = input_usd_value / output_usd_price

    baseline_diff_abs = None
    baseline_diff_pct = None
    if ideal_output_amount is not None and best_output_amount is not None:
        baseline_diff_abs = best_output_amount - ideal_output_amount
        if ideal_output_amount != 0:
            baseline_diff_pct = (baseline_diff_abs / ideal_output_amount) * 100.0

    inline_baseline = {
        "label": "Theoretical no-fee baseline",
        "is_executable": False,
        "input_amount": amount,
        "input_token": from_token,
        "input_usd_price": input_usd_price,
        "input_usd_value": input_usd_value,
        "ideal_output_amount": ideal_output_amount,
        "output_token": to_token,
        "output_usd_price": output_usd_price,
        "output_usd_value": input_usd_value,
        "pricing_source": (
            "sqlite_usd_snapshots"
            if input_usd_price is not None and output_usd_price is not None
            else "quote_fallback_partial"
        ),
        "note": "Theoretical market baseline for the swap input area. Not an executable quote.",
    }

    inline_baseline_vs_recommended = {
        "output_diff_abs": baseline_diff_abs,
        "output_diff_pct": baseline_diff_pct,
        "note": "Difference between the theoretical baseline and the current recommended executable route.",
    }

    return inline_baseline, inline_baseline_vs_recommended


@app.post("/swap/instructions")
def swap_instructions(payload: dict = Body(...)):
    quote_response = payload.get("quote_response")
    user_public_key = (payload.get("user_public_key") or "").strip()
    as_legacy_transaction = bool(payload.get("as_legacy_transaction", True))

    if not quote_response or not isinstance(quote_response, dict):
        raise HTTPException(status_code=400, detail="quote_response is required")

    if not user_public_key:
        raise HTTPException(status_code=400, detail="user_public_key is required")

    data = _fetch_jupiter_swap_instructions(
        quote_response=quote_response,
        user_public_key=user_public_key,
        as_legacy_transaction=as_legacy_transaction,
    )

    return {
        "ok": True,
        "instructions": data,
    }


@app.get("/swap/quote")
def swap_quote(
    from_token: str,
    to_token: str,
    amount: float,
    network: str = "solana",
    user_public_key: str | None = None,
):
    from_token = from_token.upper().strip()
    to_token = to_token.upper().strip()

    if network != "solana":
        raise HTTPException(status_code=400, detail="only solana is supported for now")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    if from_token == to_token:
        raise HTTPException(status_code=400, detail="from_token and to_token must be different")

    input_meta = _resolve_swap_token_meta(from_token)
    output_meta = _resolve_swap_token_meta(to_token)
    if not input_meta or not output_meta:
        raise HTTPException(status_code=400, detail="unsupported token for now")

    raw_amount = to_raw_amount(amount, input_meta["decimals"])

    base_params = {
        "inputMint": input_meta["mint"],
        "outputMint": output_meta["mint"],
        "amount": str(raw_amount),
        "slippageBps": "50",
        "restrictIntermediateTokens": "true",
        "instructionVersion": "V2",
    }

    # 1) Recommended/default Jupiter quote
    recommended_raw = _fetch_jupiter_quote(base_params)
    recommended = _normalize_quote_option(
        variant_id="recommended_default",
        label="Recommended",
        kind="recommended",
        quote=recommended_raw,
        from_token=from_token,
        to_token=to_token,
        input_amount=amount,
        input_amount_raw=raw_amount,
        output_decimals=output_meta["decimals"],
        checked_params=base_params,
    )

    diagnostics = []
    variant_candidates = []
    external_other_options = []

    # 2) Broader search variant (relax intermediate-token restriction)
    broader_params = {
        **base_params,
        "restrictIntermediateTokens": "false",
    }
    broader_result = _try_fetch_jupiter_quote(broader_params)
    if broader_result["ok"]:
        variant_candidates.append(
            _normalize_quote_option(
                variant_id="broader_search",
                label="Broader search",
                kind="alternative",
                quote=broader_result["data"],
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                input_amount_raw=raw_amount,
                output_decimals=output_meta["decimals"],
                checked_params=broader_params,
            )
        )
    else:
        diagnostics.append({"variant_id": "broader_search", **broader_result["error"]})

    # 3) Force an alternate venue mix by excluding DEX labels from the recommended route
    recommended_labels = recommended.get("route_labels") or []
    if recommended_labels:
        exclude_params = {
            **base_params,
            "excludeDexes": ",".join(recommended_labels),
        }
        exclude_result = _try_fetch_jupiter_quote(exclude_params)
        if exclude_result["ok"]:
            variant_candidates.append(
                _normalize_quote_option(
                    variant_id="exclude_recommended_dexes",
                    label="Alternate venue mix",
                    kind="alternative",
                    quote=exclude_result["data"],
                    from_token=from_token,
                    to_token=to_token,
                    input_amount=amount,
                    input_amount_raw=raw_amount,
                    output_decimals=output_meta["decimals"],
                    checked_params=exclude_params,
                )
            )
        else:
            diagnostics.append(
                {"variant_id": "exclude_recommended_dexes", **exclude_result["error"]}
            )

    # 4) Direct-route-only check
    direct_params = {
        **base_params,
        "onlyDirectRoutes": "true",
    }
    direct_result = _try_fetch_jupiter_quote(direct_params)
    direct_route_check = None
    if direct_result["ok"]:
        direct_route_check = _normalize_quote_option(
            variant_id="direct_route_check",
            label="Direct route check",
            kind="direct",
            quote=direct_result["data"],
            from_token=from_token,
            to_token=to_token,
            input_amount=amount,
            input_amount_raw=raw_amount,
            output_decimals=output_meta["decimals"],
            checked_params=direct_params,
        )
    else:
        diagnostics.append({"variant_id": "direct_route_check", **direct_result["error"]})

    raydium_params = _build_raydium_quote_params(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=raw_amount,
        slippage_bps=50,
        tx_version="V0",
    )
    raydium_result = _try_fetch_raydium_quote(raydium_params)
    if raydium_result["ok"]:
        external_other_options.append(
            _normalize_raydium_quote_option(
                variant_id="raydium_quote",
                label="Via Raydium",
                kind="alternative",
                quote=raydium_result["data"],
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                input_amount_raw=raw_amount,
                output_decimals=output_meta["decimals"],
            )
        )
    else:
        diagnostics.append({"variant_id": "raydium_quote", **raydium_result["error"]})

    meteora_payload = _build_meteora_dlmm_quote_payload(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=raw_amount,
        slippage_bps=50,
        rpc_url=SOLANA_MAINNET_RPC_URL,
    )
    meteora_result = _try_fetch_meteora_dlmm_quote(meteora_payload)
    if meteora_result["ok"]:
        external_other_options.append(
            _normalize_meteora_dlmm_quote_option(
                variant_id="meteora_dlmm_quote",
                label="Via Meteora",
                kind="alternative",
                quote=meteora_result["data"],
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                input_amount_raw=raw_amount,
                output_decimals=output_meta["decimals"],
            )
        )
    else:
        diagnostics.append({"variant_id": "meteora_dlmm_quote", **meteora_result["error"]})

    orca_payload = _build_orca_whirlpool_quote_payload(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=raw_amount,
        slippage_bps=50,
        rpc_url=SOLANA_MAINNET_RPC_URL,
    )
    orca_result = _try_fetch_orca_whirlpool_quote(orca_payload)
    if orca_result["ok"]:
        external_other_options.append(
            _normalize_orca_whirlpool_quote_option(
                variant_id="orca_whirlpool_quote",
                label="Via Orca",
                kind="alternative",
                quote=orca_result["data"],
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                input_amount_raw=raw_amount,
                output_decimals=output_meta["decimals"],
            )
        )
    else:
        diagnostics.append({"variant_id": "orca_whirlpool_quote", **orca_result["error"]})

    phoenix_payload = _build_phoenix_quote_payload(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=raw_amount,
        slippage_bps=50,
        rpc_url=SOLANA_MAINNET_RPC_URL,
    )
    phoenix_result = _try_fetch_phoenix_quote(phoenix_payload)
    if phoenix_result["ok"]:
        external_other_options.append(
            _normalize_phoenix_quote_option(
                variant_id="phoenix_quote",
                label="Via Phoenix",
                kind="alternative",
                quote=phoenix_result["data"],
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                input_amount_raw=raw_amount,
                output_decimals=output_meta["decimals"],
            )
        )
    else:
        diagnostics.append({"variant_id": "phoenix_quote", **phoenix_result["error"]})

    phantom_payload = _build_phantom_quote_payload(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=raw_amount,
        slippage_bps=50,
        user_public_key=user_public_key,
    )
    phantom_result = _try_fetch_phantom_quote(phantom_payload)
    if phantom_result["ok"]:
        external_other_options.append(
            _normalize_phantom_quote_option(
                variant_id="phantom_quote",
                label="Via Phantom",
                kind="alternative",
                quote=phantom_result["data"],
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                input_amount_raw=raw_amount,
                output_decimals=output_meta["decimals"],
            )
        )
    else:
        diagnostics.append({"variant_id": "phantom_quote", **phantom_result["error"]})

    # Build the ranked Jupiter candidate pool from all successful checked variants.
    # This remains the executable universe for now.
    ranked_jupiter_candidates = [recommended, *variant_candidates]
    if direct_route_check:
        ranked_jupiter_candidates.append(direct_route_check)

    ranked_jupiter_candidates = _rank_quote_options(ranked_jupiter_candidates)

    # Rank every normalized universe we can honestly compare. External DEX helpers
    # can win best quote, but they stay comparison-only until execution paths exist.
    ranked_universe_options = _rank_quote_options(
        [*ranked_jupiter_candidates, *external_other_options]
    )
    direct_route_base = _select_direct_route_option(ranked_universe_options)

    best_quote_base = ranked_universe_options[0] if ranked_universe_options else recommended
    best_quote_variant_id = best_quote_base.get("variant_id")
    best_quote_option = _with_quote_role(
        best_quote_base,
        kind="recommended",
        label="Recommended",
    )

    executable_candidates = [
        opt for opt in ranked_jupiter_candidates if _is_executable_quote_option(opt)
    ]
    recommended_executable_base = executable_candidates[0] if executable_candidates else None
    recommended_executable_variant_id = (
        recommended_executable_base.get("variant_id") if recommended_executable_base else None
    )
    recommended_executable_option = _with_quote_role(
        recommended_executable_base,
        kind="recommended",
        label=(
            "Recommended executable"
            if not _same_quote_option(recommended_executable_base, best_quote_base)
            else "Recommended"
        ),
    )

    # Other options = meaningful remaining normalized universe options. Prefer
    # execution surfaces not already represented by the visible best quote or
    # selected executable recommendation, so internal Jupiter variants do not
    # crowd out Raydium.
    ranked_other_options = []
    diverse_other_options = _select_diverse_other_options(
        ranked_universe_options,
        best_quote=best_quote_base,
        recommended=recommended_executable_base,
        direct=direct_route_base,
    )
    for opt in diverse_other_options:
        variant_id = opt.get("variant_id")
        alt_label = opt.get("label") or "Alternative"

        if variant_id == "recommended_default":
            alt_label = "Default Jupiter route"
        elif variant_id == "raydium_quote":
            alt_label = "Via Raydium"
        elif variant_id == "meteora_dlmm_quote":
            alt_label = "Via Meteora"
        elif variant_id == "orca_whirlpool_quote":
            alt_label = "Via Orca"
        elif variant_id == "phoenix_quote":
            alt_label = "Via Phoenix"
        elif variant_id == "phantom_quote":
            alt_label = "Via Phantom"
        elif variant_id == "exclude_recommended_dexes":
            alt_label = "Alternate venue mix"
        elif variant_id == "broader_search":
            alt_label = "Broader search"

        ranked_other_options.append({
            **opt,
            "kind": "alternative",
            "label": alt_label,
        })

    direct_route_variant_id = direct_route_base.get("variant_id") if direct_route_base else None
    direct_route_output = _with_quote_role(
        direct_route_base,
        kind="direct",
        label="Direct / simple route",
    )

    recommended_reason = {
        "recommended_default": "The default Jupiter quote had the best checked output for this request.",
        "exclude_recommended_dexes": "An alternate venue mix produced the best checked output for this request.",
        "direct_route_check": "The selected direct/simple route produced the best checked output for this request.",
        "broader_search": "A broader routing search produced the best checked output for this request.",
        "raydium_quote": "Raydium produced the best checked quote for this request, but it is comparison-only in this preview path.",
        "meteora_dlmm_quote": "Meteora DLMM produced the best checked quote for this request, but it is comparison-only in this preview path.",
        "orca_whirlpool_quote": "Orca Whirlpool produced the best checked quote for this request, but it is comparison-only in this preview path.",
        "phoenix_quote": "Phoenix CLOB produced the best checked quote for this request, but it is comparison-only in this preview path.",
        "phantom_quote": "Phantom routing API produced the best checked quote for this request, but it is comparison-only in this preview path.",
    }.get(
        best_quote_variant_id,
        "The best quote had the strongest checked output among the currently available variants."
    )

    best_output_amount = _safe_float(best_quote_option.get("estimated_output"))
    try:
        reference_prices = _resolve_quote_reference_prices_usd([from_token, to_token, "SOL"])
    except Exception:
        reference_prices = {}

    inline_baseline, inline_baseline_vs_recommended = _build_fresh_quote_reference_baseline(
        from_token=from_token,
        to_token=to_token,
        amount=amount,
        fallback_input_usd_value=_safe_float(recommended_raw.get("swapUsdValue")),
        best_output_amount=best_output_amount,
        reference_prices=reference_prices,
    )

    reference_output_amount = _safe_float((inline_baseline or {}).get("ideal_output_amount"))

    best_quote_option = _attach_cost_fields(best_quote_option, reference_output_amount)
    recommended_executable_option = _attach_cost_fields(
        recommended_executable_option,
        reference_output_amount,
    )
    ranked_other_options = [
        _attach_cost_fields(opt, reference_output_amount) for opt in ranked_other_options
    ] 
    direct_route_output = _attach_cost_fields(direct_route_output, reference_output_amount)

    if _is_executable_quote_option(best_quote_option):
        best_quote_option = _attach_backend_network_fee_estimate(
            best_quote_option,
            user_public_key=user_public_key,
            rpc_url=SOLANA_MAINNET_RPC_URL,
        )
    else:
        best_quote_option["estimated_network_fee"] = None
        best_quote_option["network_fee_scope"] = "not_estimated_in_preview"
        best_quote_option["network_fee_detail"] = (
            "This quote is comparison-only and cannot be executed from this preview path."
        )

    if _same_quote_option(recommended_executable_option, best_quote_option):
        recommended_executable_option = best_quote_option
    elif _is_executable_quote_option(recommended_executable_option):
        recommended_executable_option = _attach_backend_network_fee_estimate(
            recommended_executable_option,
            user_public_key=user_public_key,
            rpc_url=SOLANA_MAINNET_RPC_URL,
        )

    for opt in ranked_other_options:
        if opt.get("is_comparison_only") is True:
            opt["estimated_network_fee"] = None
            opt["network_fee_scope"] = "not_estimated_in_preview"
            opt["network_fee_detail"] = (
                "This quote is comparison-only and cannot be executed from this preview path."
            )
        elif not user_public_key:
            opt["estimated_network_fee"] = None
            opt["network_fee_scope"] = "wallet_not_connected"
            opt["network_fee_detail"] = None
        else:
            opt["estimated_network_fee"] = None
            opt["network_fee_scope"] = "not_estimated_in_preview"
            opt["network_fee_detail"] = (
               "Fee estimation is currently limited to the recommended route to avoid provider rate limits."
            )

    if direct_route_output:
        if not user_public_key:
            direct_route_output["estimated_network_fee"] = None
            direct_route_output["network_fee_scope"] = "wallet_not_connected"
            direct_route_output["network_fee_detail"] = None
        else:
            direct_route_output["estimated_network_fee"] = None
            direct_route_output["network_fee_scope"] = "not_estimated_in_preview"
            direct_route_output["network_fee_detail"] = (
                "Fee estimation is currently limited to the recommended route to avoid provider rate limits."
            )
    

    best_quote_option = _attach_recommended_swap_cost_summary(
        best_quote_option,
        reference_prices=reference_prices,
    )
    if _same_quote_option(recommended_executable_option, best_quote_option):
        recommended_executable_option = best_quote_option
    else:
        recommended_executable_option = _attach_recommended_swap_cost_summary(
            recommended_executable_option,
            reference_prices=reference_prices,
        )

    ranked_jupiter_variant_debug = [
        {
            "variant_id": opt.get("variant_id"),
            "execution_surface_label": opt.get("execution_surface_label"),
            "estimated_output_raw": opt.get("estimated_output_raw"),
            "route_labels": opt.get("route_labels"),
        }
        for opt in ranked_jupiter_candidates
        if opt.get("variant_id") != "direct_route_check"
    ]

    best_quote_option = _strip_internal_sort_key(best_quote_option)
    recommended_executable_option = _strip_internal_sort_key(recommended_executable_option)
    recommended_option = best_quote_option
    ranked_other_options = [_strip_internal_sort_key(x) for x in ranked_other_options]
    direct_route_output = _strip_internal_sort_key(direct_route_output)

    return {
        "ok": True,
        "network": network,
        "provider": best_quote_option.get("provider") or "jupiter-metis",
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": amount,
        "inline_baseline": inline_baseline,
        "inline_baseline_vs_recommended": inline_baseline_vs_recommended,
        "input_amount_raw": raw_amount,
        "best_quote_option": best_quote_option,
        "recommended_option": recommended_option,
        "recommended_executable_option": recommended_executable_option,
        "recommended": recommended_option,
        "other_options": ranked_other_options,
        "direct_route_check": direct_route_output,
        "summary": {
            "selection_basis": "highest_output_amount_among_normalized_universe_options",
            "headline_label": "Estimated trade execution cost",
            "cost_scope": "benchmark_shortfall_vs_fresh_reference",
            "recommended_reason": recommended_reason,
            "best_quote_variant_id": best_quote_variant_id,
            "recommended_variant_id": best_quote_variant_id,
            "recommended_executable_variant_id": recommended_executable_variant_id,
            "direct_route_variant_id": direct_route_variant_id,
            "best_quote_is_executable": _is_executable_quote_option(best_quote_option),
            "recommended_is_executable": _is_executable_quote_option(recommended_option),
            "checked_variants": [
                "recommended_default",
                "broader_search",
                "exclude_recommended_dexes",
                "direct_route_check",
                "raydium_quote",
                "meteora_dlmm_quote",
                "orca_whirlpool_quote",
                "phoenix_quote",
                "phantom_quote",
            ],
            "available_other_options": len(ranked_other_options),
            "alternatives_show_all_remaining_universes": True,
            "direct_route_available": direct_route_output is not None,
            "ranking_basis": "highest_receive_amount",
            "direct_route_selection_basis": "simplest_meaningful_candidate_across_live_quote_universes",
            "cost_model_scope": "partial_transparency_not_ranking_input",
            "recommendation_scope": "highest_receive_amount_across_live_quote_universes",
            "execution_availability_scope": "separate_from_recommendation",
        },
        "debug": {
            "route_debug": recommended_raw.get("mostReliableAmmsQuoteReport"),
            "ranked_jupiter_variants": ranked_jupiter_variant_debug,
            "variant_errors": diagnostics,
            "notes": [
                "Recommended is selected by highest receive amount across live quote universes, not by estimated total swap cost.",
                "Execution availability is separate from recommendation. Quote-only routes are not clickable yet.",
                "Direct/simple route is selected across available live quote universes. The Jupiter direct-route quote remains one candidate in that model.",
                "Benchmark gap is a reference comparison, not a fee. Explicit route fees are provider-disclosed fee evidence and may already be reflected in quoted output.",
                "Phantom uses the official Phantom routing API quote surface. It is quote-only and non-clickable in this preview path.",
                "Orca and Phoenix use standalone SDK helpers. They are quote-only and non-clickable in this preview path.",
            ],
        },
    }




@app.get("/swap/inline-baseline")
def swap_inline_baseline(from_token: str, to_token: str, amount: float, network: str = "solana"):
    from_token = from_token.upper().strip()
    to_token = to_token.upper().strip()

    if network != "solana":
        raise HTTPException(status_code=400, detail="only solana is supported for now")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    if from_token == to_token:
        raise HTTPException(status_code=400, detail="from_token and to_token must be different")

    input_meta = _resolve_swap_token_meta(from_token)
    output_meta = _resolve_swap_token_meta(to_token)
    if not input_meta or not output_meta:
        raise HTTPException(status_code=400, detail="unsupported token for now")

    inline_baseline, _ = _build_inline_baseline(
        from_token=from_token,
        to_token=to_token,
        amount=amount,
        fallback_input_usd_value=None,
        best_output_amount=None,
    )

    return {
        "ok": True,
        "network": network,
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": amount,
        "inline_baseline": inline_baseline,
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
