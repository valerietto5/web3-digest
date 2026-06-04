from __future__ import annotations
from fastapi.responses import HTMLResponse

from .ui_page import build_ui_html
from fastapi import FastAPI, HTTPException, Query
from pathlib import Path
import base64
import binascii
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
import re
import hashlib
import urllib.parse
import urllib.request
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import Body

import requests
from datetime import datetime, timezone
from providers.helius_activity import fetch_wallet_activity
from providers.token_holder_concentration import (
    fetch_token_holder_concentration,
    get_holder_concentration_rpc_config_status,
)
from providers.token_resolver import resolve_token
from token_registry import default_swap_token_meta_by_symbol, get_token_meta_by_symbol, mint_to_asset_key, TOKENS

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


def _resolve_swap_token_for_quote(query: str) -> dict | None:
    raw_query = (query or "").strip()
    if not raw_query:
        return None

    registry_meta = _resolve_swap_token_meta(raw_query)
    if registry_meta:
        out = dict(registry_meta)
        out["source"] = "registry"
        out["quote_label"] = (out.get("symbol") or raw_query).strip().upper()
        out["external"] = False
        return out

    resolved = resolve_token(raw_query, allow_external=True)
    if resolved.get("ok") is not True:
        return {
            "source": "external_resolver",
            "external": True,
            "resolution_error": resolved.get("error") or {
                "code": "TOKEN_RESOLUTION_FAILED",
                "message": "Token could not be resolved.",
            },
        }

    token = resolved.get("token") if isinstance(resolved, dict) else None
    if not isinstance(token, dict):
        return {
            "source": "external_resolver",
            "external": True,
            "resolution_error": {
                "code": "TOKEN_RESOLUTION_FAILED",
                "message": "Token resolver returned no token metadata.",
            },
        }

    mint = (token.get("mint") or "").strip()
    decimals = token.get("decimals")
    symbol = (token.get("symbol") or "").strip()
    display_name = (token.get("display_name") or token.get("name") or symbol).strip()
    if not mint or not isinstance(decimals, int) or decimals < 0 or not (symbol or display_name):
        return {
            "source": "external_resolver",
            "external": True,
            "mint": mint,
            "resolution_error": {
                "code": "TOKEN_RESOLUTION_INCOMPLETE",
                "message": "External token metadata is missing mint, decimals, or display label.",
                "token": token,
            },
        }

    return {
        "asset": f"external:{mint}",
        "symbol": symbol or display_name,
        "name": token.get("name") or display_name or symbol,
        "display_name": display_name or symbol,
        "mint": mint,
        "decimals": decimals,
        "logo_uri": token.get("logo_uri"),
        "verified": bool(token.get("verified")),
        "default_enabled": False,
        "tags": token.get("tags") or [],
        "coingecko_id": token.get("coingecko_id"),
        "dexscreener_chain_id": token.get("dexscreener_chain_id"),
        "source": "external_resolver",
        "resolver_source": token.get("source"),
        "external": True,
        "quote_label": symbol or display_name,
        "warnings": token.get("warnings") or [],
        "liquidity_usd": token.get("liquidity_usd"),
        "price_usd": token.get("price_usd"),
        "pair_address": token.get("pair_address"),
        "pair_url": token.get("pair_url"),
    }


def _external_token_response_meta(side: str, meta: dict) -> dict | None:
    if not meta or not meta.get("external"):
        return None
    return {
        "side": side,
        "symbol": meta.get("symbol"),
        "display_name": meta.get("display_name") or meta.get("name") or meta.get("symbol"),
        "mint": meta.get("mint"),
        "decimals": meta.get("decimals"),
        "source": meta.get("resolver_source") or meta.get("source"),
        "verified": bool(meta.get("verified")),
        "warnings": meta.get("warnings") or [],
        "liquidity_usd": meta.get("liquidity_usd"),
        "price_usd": meta.get("price_usd"),
        "pair_address": meta.get("pair_address"),
        "pair_url": meta.get("pair_url"),
    }


def _external_token_reference_price_row(meta: dict | None) -> dict | None:
    if not meta or not meta.get("external"):
        return None

    price_usd = _safe_float(meta.get("price_usd"))
    if price_usd is None or price_usd <= 0:
        return None

    return {
        "usd": price_usd,
        "pricing_source": "dexscreener_solana",
        "pricing_ts": None,
        "pricing_source_detail": {
            "source": meta.get("resolver_source") or meta.get("source"),
            "mint": meta.get("mint"),
            "pair_address": meta.get("pair_address"),
            "pair_url": meta.get("pair_url"),
            "liquidity_usd": meta.get("liquidity_usd"),
            "external_token_metadata": True,
            "verified": bool(meta.get("verified")),
        },
        "reference_quality": "external_unverified_reference",
        "usd_valuation_reliable": False,
    }


def _apply_external_token_reference_prices(reference_prices: dict, token_meta_by_label: dict) -> dict:
    prices = dict(reference_prices or {})
    for token_label, meta in (token_meta_by_label or {}).items():
        row = _external_token_reference_price_row(meta)
        if row:
            prices[token_label] = row
    return prices


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
    out = {}

    try:
        from dexscreener import fetch_best_pair_price_usd_solana
    except Exception:
        return out

    for token in tokens:
        token = (token or "").strip().upper()
        meta = _resolve_swap_token_meta(token)
        if not meta:
            continue

        tags = {str(tag).lower() for tag in (meta.get("tags") or [])}
        if "meme" not in tags:
            continue

        mint = meta.get("mint")
        if not mint:
            continue

        pair = fetch_best_pair_price_usd_solana(mint, min_liquidity_usd=5_000.0)
        if not pair:
            continue

        out[token] = {
            "usd": float(pair.price_usd),
            "pricing_source": "dexscreener_solana",
            "pricing_ts": None,
            "pricing_source_detail": {
                "mint": mint,
                "chain_id": meta.get("dexscreener_chain_id") or "solana",
                "liquidity_usd": pair.liquidity_usd,
                "url": pair.url,
            },
        }

    return out


def _resolve_from_sqlite_fallback(tokens: list[str]) -> dict:
    return _fetch_sqlite_reference_prices_usd(tokens)


def _resolve_quote_benchmark_prices_usd(tokens: list[str]) -> dict:
    resolved = {}

    for resolver in (
        _resolve_from_long_tail_benchmark_source,
        _resolve_from_solana_native_benchmark_source,
        _resolve_from_major_benchmark_source,
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

    pricing_source = (
        to_row.get("pricing_source")
        or from_row.get("pricing_source")
        or "coingecko_simple_price"
    )
    pricing_ts = (
        to_row.get("pricing_ts")
        if to_row.get("pricing_source")
        else from_row.get("pricing_ts")
    )

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
        "pricing_source": pricing_source,
        "pricing_ts": pricing_ts,
        "pricing_source_detail": {
            "from_token": from_row.get("pricing_source_detail"),
            "to_token": to_row.get("pricing_source_detail"),
        },
        "note": "Fresh market reference for quote comparison. Not an executable quote.",
    }

    baseline_vs_recommended = None
    if best_output_amount is not None and ideal_output_amount:
        diff_abs = best_output_amount - ideal_output_amount
        diff_usd = diff_abs * output_usd_price
        diff_pct = (diff_abs / ideal_output_amount) * 100

        baseline_vs_recommended = {
            "output_diff_abs": diff_abs,
            "output_diff_usd": diff_usd,
            "output_diff_pct": diff_pct,
            "output_token": to_token,
            "output_usd_price": output_usd_price,
            "pricing_source": baseline.get("pricing_source"),
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

    try:
        import token_registry
        for _mint, info in getattr(token_registry, "TOKENS", {}).items():
            if not isinstance(info, dict):
                continue
            if (info.get("asset") or "").strip().lower() == asset.lower():
                return info.get("symbol") or info.get("name") or asset.upper()
    except Exception:
        pass

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


@app.get("/wallet/activity")
def wallet_activity(address: str = Query(""), limit: int = Query(20)):
    address = (address or "").strip()
    if not address:
        raise HTTPException(status_code=400, detail="address is required")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")

    return fetch_wallet_activity(address, limit=limit)


def _public_swap_token_meta(symbol: str, meta: dict) -> dict:
    asset_key = meta.get("asset") or str(symbol or "").lower()
    return {
        "asset": asset_key,
        "asset_key": asset_key,
        "symbol": symbol,
        "display_name": meta.get("display_name") or meta.get("name") or symbol,
        "mint": meta.get("mint"),
        "decimals": meta.get("decimals"),
        "tags": meta.get("tags") or [],
        "verified": bool(meta.get("verified")),
        "default_enabled": bool(meta.get("default_enabled")),
    }


def _normalize_refresh_asset_for_diagnostics(asset: str) -> str:
    raw = str(asset or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    if low.startswith("spl:"):
        return mint_to_asset_key(raw.split(":", 1)[1])
    for mint in TOKENS.keys():
        if raw == mint or low == mint.lower():
            return mint_to_asset_key(mint)
    return low


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


@app.get("/tokens/resolve")
def token_resolve(query: str = Query(""), allow_external: bool = Query(True)):
    result = resolve_token(query, allow_external=allow_external)
    if not isinstance(result, dict):
        return result

    token = result.get("token")
    decimals = token.get("decimals") if isinstance(token, dict) else None
    can_quote = isinstance(decimals, int) and decimals >= 0
    result["can_quote"] = bool(result.get("ok") is True and can_quote)
    if isinstance(token, dict):
        token["can_quote"] = result["can_quote"]
    if result.get("ok") is True and not can_quote:
        result["reason"] = "decimals_unresolved"
    elif result.get("ok") is not True:
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        result["reason"] = error.get("code") or "token_unresolved"
    return result


@app.get("/tokens/holder-concentration")
def token_holder_concentration(mint: str = Query("")):
    mint = (mint or "").strip()
    if not mint:
        raise HTTPException(status_code=400, detail="mint is required")

    return fetch_token_holder_concentration(mint)


@app.get("/tokens/holder-concentration/config")
def token_holder_concentration_config():
    return {
        "ok": True,
        "rpc": get_holder_concentration_rpc_config_status(),
        "note": "Set TOKEN_HOLDER_CONCENTRATION_RPC_URL to use a dedicated RPC for holder concentration.",
    }


def _build_promotion_audit_summary(report: dict) -> dict:
    pairs = report.get("pairs") if isinstance(report, dict) else []
    if not isinstance(pairs, list):
        pairs = []

    counts = {
        "strong": 0,
        "good": 0,
        "thin": 0,
        "weak": 0,
    }
    successful_universes = []
    seen_universes = set()

    for pair in pairs:
        classification = pair.get("classification")
        if classification in counts:
            counts[classification] += 1

        for universe in pair.get("universes") or []:
            if universe.get("status") != "success":
                continue
            label = universe.get("universe")
            if not label:
                continue
            key = str(label).strip().lower()
            if not key or key in seen_universes:
                continue
            seen_universes.add(key)
            successful_universes.append(str(label).strip())

    best_pair_classification = "weak"
    for label in ("strong", "good", "thin", "weak"):
        if counts[label] > 0:
            best_pair_classification = label
            break

    coverage_label = {
        "strong": "Strong coverage",
        "good": "Good coverage",
        "thin": "Thin coverage",
        "weak": "Weak coverage",
    }.get(best_pair_classification, "Weak coverage")

    return {
        "total_pairs": len(pairs),
        "strong_pairs": counts["strong"],
        "good_pairs": counts["good"],
        "thin_pairs": counts["thin"],
        "weak_pairs": counts["weak"],
        "successful_universes": successful_universes,
        "phantom_supported": "phantom" in seen_universes,
        "pumpswap_supported": "pumpswap" in seen_universes,
        "best_pair_classification": best_pair_classification,
        "coverage_label": coverage_label,
    }


@app.get("/tokens/promotion-audit")
def token_promotion_audit(
    mint: str = Query(""),
    amount: float = Query(1.0),
    request_delay: float = Query(1.5),
):
    mint = (mint or "").strip()
    if not mint:
        raise HTTPException(status_code=400, detail="mint is required")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")
    if request_delay < 0 or request_delay > 5:
        raise HTTPException(status_code=400, detail="request_delay must be between 0 and 5 seconds")

    from tools.token_promotion_audit import audit_mint

    report = audit_mint(mint, amount=amount, request_delay=request_delay)
    report["promotion_summary"] = _build_promotion_audit_summary(report)
    return report


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


def _swap_execution_error(code: str, message: str, **extra) -> dict:
    error = {
        "code": code,
        "message": message,
    }
    error.update({k: v for k, v in extra.items() if v is not None})
    return {
        "ok": False,
        "error": error,
    }


def _fetch_jupiter_swap_transaction(
    *,
    quote_response: dict,
    user_public_key: str,
    as_legacy_transaction: bool = False,
) -> dict:
    url = "https://api.jup.ag/swap/v1/swap"

    payload = {
        "quoteResponse": quote_response,
        "userPublicKey": user_public_key,
        "wrapAndUnwrapSol": True,
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
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            e.close()
        except Exception:
            pass
        if e.code in (401, 403) or "api key" in body.lower() or "unauthorized" in body.lower():
            return _swap_execution_error(
                "SWAP_EXECUTION_JUPITER_AUTH_REQUIRED",
                "Jupiter swap execution requires valid Jupiter API authorization.",
                status_code=e.code,
                detail=body,
            )
        if e.code == 429:
            return _swap_execution_error(
                "SWAP_EXECUTION_RATE_LIMITED",
                "Jupiter swap execution is rate-limited right now.",
                status_code=e.code,
                detail=body,
            )
        return _swap_execution_error(
            "SWAP_EXECUTION_PREPARE_FAILED",
            "Jupiter swap transaction preparation failed.",
            status_code=e.code,
            detail=body,
        )
    except json.JSONDecodeError as e:
        return _swap_execution_error(
            "SWAP_EXECUTION_PREPARE_FAILED",
            "Jupiter swap transaction response was not valid JSON.",
            detail=str(e),
        )
    except Exception as e:
        return _swap_execution_error(
            "SWAP_EXECUTION_PREPARE_FAILED",
            "Jupiter swap transaction request failed.",
            detail=str(e),
        )

    if not isinstance(data, dict):
        return _swap_execution_error(
            "SWAP_EXECUTION_PREPARE_FAILED",
            "Jupiter swap transaction response was not an object.",
        )

    swap_transaction = data.get("swapTransaction")
    if not swap_transaction:
        return _swap_execution_error(
            "SWAP_EXECUTION_PREPARE_FAILED",
            "Jupiter swap transaction response did not include swapTransaction.",
            raw=data,
        )

    return {
        "ok": True,
        "swap_transaction": swap_transaction,
        "last_valid_block_height": data.get("lastValidBlockHeight"),
        "raw": data,
    }


JUPITER_EXECUTION_PROVIDER_ALIASES = {
    "jupiter": "jupiter-metis",
    "jupiter-metis": "jupiter-metis",
}

SUPPORTED_EXECUTION_PROVIDERS = {"jupiter-metis", "raydium-trade-api", "orca-whirlpool", "meteora-dlmm", "pumpswap"}
BENCHMARK_ONLY_SWAP_PROVIDERS = {"phantom-routing-api"}

SWAP_EXECUTION_PROVIDER_CAPABILITIES = {
    "jupiter-metis": {
        "quote": True,
        "prepare": True,
        "submit": True,
        "status": "executable_v1",
        "label": "Jupiter",
    },
    "raydium-trade-api": {
        "quote": True,
        "prepare": True,
        "submit": True,
        "status": "executable_v1",
        "label": "Raydium",
    },
    "orca-whirlpool": {
        "quote": True,
        "prepare": True,
        "submit": True,
        "status": "executable_v1",
        "label": "Orca",
    },
    "meteora-dlmm": {
        "quote": True,
        "prepare": True,
        "submit": True,
        "status": "executable_v1_single_pool",
        "label": "Meteora",
    },
    "pumpswap": {
        "quote": True,
        "prepare": True,
        "submit": True,
        "status": "executable_v1",
        "label": "PumpSwap",
    },
    "phantom-routing-api": {
        "quote": True,
        "prepare": False,
        "submit": False,
        "status": "benchmark_quote_only",
        "label": "Phantom",
    },
    "phoenix-clob": {
        "quote": True,
        "prepare": False,
        "submit": False,
        "status": "advanced_research",
        "label": "Phoenix",
    },
}

JUPITER_EXECUTION_VARIANTS = {
    "recommended_default",
    "broader_search",
    "exclude_recommended_dexes",
    "direct_route_check",
}

SWAP_EXECUTION_PROVIDER_VARIANTS = {
    "jupiter-metis": JUPITER_EXECUTION_VARIANTS,
    "raydium-trade-api": {"raydium_quote"},
    "orca-whirlpool": {"orca_whirlpool_quote"},
    "meteora-dlmm": {"meteora_dlmm_quote"},
    "pumpswap": {"pumpswap_quote"},
}


def _resolution_has_mint_and_decimals(resolution: dict | None) -> bool:
    if not isinstance(resolution, dict):
        return True

    decimals = resolution.get("decimals")
    return bool(resolution.get("mint")) and isinstance(decimals, int)


def get_swap_execution_provider_capability(provider_id: str | None) -> dict:
    provider = _normalize_execution_provider(provider_id or "") or (provider_id or "").strip().lower()
    capability = SWAP_EXECUTION_PROVIDER_CAPABILITIES.get(provider)
    if capability:
        return {
            "provider": provider,
            **capability,
        }
    return {
        "provider": provider or None,
        "quote": False,
        "prepare": False,
        "submit": False,
        "status": "unknown",
        "label": provider or "Unknown",
    }


def build_swap_execution_readiness(
    option,
    *,
    from_resolution: dict | None = None,
    to_resolution: dict | None = None,
    network: str = "solana",
) -> dict:
    reasons = []
    warnings = []
    provider = (option or {}).get("provider") if isinstance(option, dict) else None
    capability = get_swap_execution_provider_capability(provider)
    provider_id = capability.get("provider")
    supported_variants = SWAP_EXECUTION_PROVIDER_VARIANTS.get(provider_id, set())
    variant_id = (option or {}).get("variant_id")

    if (network or "").lower() != "solana":
        reasons.append("UNSUPPORTED_NETWORK")
    elif not capability.get("prepare") or not capability.get("submit"):
        reasons.append("NON_JUPITER_ROUTE")
    elif variant_id not in supported_variants:
        reasons.append("UNSUPPORTED_VARIANT")
    elif (option or {}).get("is_comparison_only") is True:
        reasons.append("COMPARISON_ONLY_ROUTE")
    elif (option or {}).get("is_clickable") is not True:
        reasons.append("NOT_CLICKABLE")
    elif (option or {}).get("execution_status") != "executable_capable":
        reasons.append("NOT_CLICKABLE")
    elif (
        not _resolution_has_mint_and_decimals(from_resolution)
        or not _resolution_has_mint_and_decimals(to_resolution)
    ):
        reasons.append("TOKEN_DECIMALS_UNAVAILABLE")

    execution_ready = not reasons
    return {
        "execution_ready": execution_ready,
        "execution_stage": "prepare_available" if execution_ready else "quote_only",
        "execution_provider": provider_id if execution_ready else None,
        "provider_status": capability.get("status"),
        "provider_label": capability.get("label"),
        "prepare_capable": bool(capability.get("prepare")),
        "submit_capable": bool(capability.get("submit")),
        "reasons": reasons,
        "warnings": warnings,
    }


def _normalize_execution_provider(provider: str) -> str | None:
    key = (provider or "").strip().lower()
    return JUPITER_EXECUTION_PROVIDER_ALIASES.get(key)


def get_swap_execution_provider(provider_id: str) -> dict | None:
    provider = _normalize_execution_provider(provider_id) or (provider_id or "").strip().lower()
    if provider == "jupiter-metis":
        return {
            "provider": "jupiter-metis",
            "execution_surface_label": "Jupiter",
            "prepare": _prepare_jupiter_swap_transaction,
        }
    if provider == "raydium-trade-api":
        return {
            "provider": "raydium-trade-api",
            "execution_surface_label": "Raydium",
            "prepare": _prepare_raydium_swap_transaction,
        }
    if provider == "orca-whirlpool":
        return {
            "provider": "orca-whirlpool",
            "execution_surface_label": "Orca",
            "prepare": _prepare_orca_whirlpool_swap_transaction,
        }
    if provider == "meteora-dlmm":
        return {
            "provider": "meteora-dlmm",
            "execution_surface_label": "Meteora",
            "prepare": _prepare_meteora_dlmm_swap_transaction,
        }
    if provider == "pumpswap":
        return {
            "provider": "pumpswap",
            "execution_surface_label": "PumpSwap",
            "prepare": _prepare_pumpswap_swap_transaction,
        }
    return None


def _build_jupiter_execution_quote_params(
    *,
    input_meta: dict,
    output_meta: dict,
    amount_raw: int,
    slippage_bps: int,
    variant_id: str,
) -> dict:
    params = {
        "inputMint": input_meta["mint"],
        "outputMint": output_meta["mint"],
        "amount": str(amount_raw),
        "slippageBps": str(slippage_bps),
        "restrictIntermediateTokens": "true",
        "instructionVersion": "V2",
    }

    if variant_id == "broader_search":
        params["restrictIntermediateTokens"] = "false"
    elif variant_id == "direct_route_check":
        params["onlyDirectRoutes"] = "true"

    return params


def _jupiter_quote_error_response(e: HTTPException) -> dict:
    detail = e.detail
    detail_text = json.dumps(detail) if isinstance(detail, (dict, list)) else str(detail)
    lower = detail_text.lower()

    if e.status_code == 429 or "too many requests" in lower or "rate limit" in lower:
        return _swap_execution_error(
            "SWAP_EXECUTION_RATE_LIMITED",
            "Jupiter quote request is rate-limited right now.",
            status_code=e.status_code,
            detail=detail,
        )

    if e.status_code in (401, 403) or "api key" in lower or "unauthorized" in lower:
        return _swap_execution_error(
            "SWAP_EXECUTION_JUPITER_AUTH_REQUIRED",
            "Jupiter quote request requires valid Jupiter API authorization.",
            status_code=e.status_code,
            detail=detail,
        )

    return _swap_execution_error(
        "SWAP_EXECUTION_QUOTE_FAILED",
        "Could not refresh a Jupiter quote for swap execution.",
        status_code=e.status_code,
        detail=detail,
    )


def _fetch_fresh_jupiter_execution_quote(
    *,
    input_meta: dict,
    output_meta: dict,
    amount_raw: int,
    slippage_bps: int,
    variant_id: str,
) -> dict:
    params = _build_jupiter_execution_quote_params(
        input_meta=input_meta,
        output_meta=output_meta,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
        variant_id=variant_id,
    )

    if variant_id != "exclude_recommended_dexes":
        try:
            return {
                "ok": True,
                "quote": _fetch_jupiter_quote(params),
                "params": params,
            }
        except HTTPException as e:
            return _jupiter_quote_error_response(e)

    try:
        base_quote = _fetch_jupiter_quote(params)
        labels = _route_labels(base_quote.get("routePlan") or [])
        if not labels:
            return _swap_execution_error(
                "SWAP_EXECUTION_UNSUPPORTED_ROUTE",
                "Alternate venue mix execution requires a default Jupiter route to exclude.",
            )
        exclude_params = {
            **params,
            "excludeDexes": ",".join(labels),
        }
        return {
            "ok": True,
            "quote": _fetch_jupiter_quote(exclude_params),
            "params": exclude_params,
        }
    except HTTPException as e:
        return _jupiter_quote_error_response(e)


def _jupiter_execution_quote_summary(
    *,
    quote: dict,
    from_token: str,
    to_token: str,
    amount: float,
    output_decimals: int,
    slippage_bps: int,
    variant_id: str,
) -> dict:
    return {
        "from_token": from_token,
        "to_token": to_token,
        "amount": amount,
        "estimated_output": _ui_amount(quote.get("outAmount"), output_decimals),
        "estimated_output_raw": quote.get("outAmount"),
        "min_received": _ui_amount(quote.get("otherAmountThreshold"), output_decimals),
        "min_received_raw": quote.get("otherAmountThreshold"),
        "slippage_bps": slippage_bps,
        "variant_id": variant_id,
    }


RAYDIUM_EXECUTION_SOL_MINT = "So11111111111111111111111111111111111111112"
RAYDIUM_DEFAULT_COMPUTE_UNIT_PRICE_MICRO_LAMPORTS = "10000"
RAYDIUM_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def _base58_decode_bytes(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("base58 value is required")

    decoded = 0
    for char in value:
        if char not in _BASE58_ALPHABET:
            raise ValueError("invalid base58 character")
        decoded = decoded * 58 + _BASE58_ALPHABET.index(char)
    raw = decoded.to_bytes((decoded.bit_length() + 7) // 8, "big") if decoded else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return (b"\x00" * leading_zeroes) + raw


def _solana_pubkey_bytes(value: str) -> bytes:
    raw = _base58_decode_bytes(value)
    if len(raw) != 32:
        raise ValueError("Solana public key must decode to 32 bytes")
    return raw


def _ed25519_is_on_curve(compressed: bytes) -> bool:
    if len(compressed) != 32:
        return False

    p = 2**255 - 19
    y = int.from_bytes(compressed, "little") & ((1 << 255) - 1)
    if y >= p:
        return False

    y2 = (y * y) % p
    u = (y2 - 1) % p
    d = (-121665 * pow(121666, p - 2, p)) % p
    v = (d * y2 + 1) % p
    if v == 0:
        return False
    x2 = (u * pow(v, p - 2, p)) % p
    return pow(x2, (p - 1) // 2, p) == 1 or x2 == 0


def _solana_create_program_address(seeds: list[bytes], program_id: bytes) -> bytes:
    if len(seeds) > 16:
        raise ValueError("too many PDA seeds")
    for seed in seeds:
        if len(seed) > 32:
            raise ValueError("PDA seed is too long")

    digest = hashlib.sha256(
        b"".join(seeds) + program_id + b"ProgramDerivedAddress"
    ).digest()
    if _ed25519_is_on_curve(digest):
        raise ValueError("PDA landed on curve")
    return digest


def _solana_find_program_address(seeds: list[bytes], program_id: bytes) -> tuple[bytes, int]:
    for bump in range(255, -1, -1):
        try:
            address = _solana_create_program_address(seeds + [bytes([bump])], program_id)
            return address, bump
        except ValueError:
            continue
    raise ValueError("could not find a valid PDA")


def _derive_solana_associated_token_account(
    *,
    owner: str,
    mint: str,
    token_program_id: str = RAYDIUM_TOKEN_PROGRAM_ID,
) -> str:
    owner_bytes = _solana_pubkey_bytes(owner)
    mint_bytes = _solana_pubkey_bytes(mint)
    token_program_bytes = _solana_pubkey_bytes(token_program_id)
    associated_program_bytes = _solana_pubkey_bytes(SOLANA_ASSOCIATED_TOKEN_PROGRAM_ID)
    ata_bytes, _bump = _solana_find_program_address(
        [owner_bytes, token_program_bytes, mint_bytes],
        associated_program_bytes,
    )
    return _base58_encode_bytes(ata_bytes)


def _raydium_prepare_token_accounts(
    *,
    input_mint: str,
    output_mint: str,
    user_public_key: str,
) -> dict:
    wrap_sol = input_mint == RAYDIUM_EXECUTION_SOL_MINT
    unwrap_sol = output_mint == RAYDIUM_EXECUTION_SOL_MINT

    input_account = None
    output_account = None
    if not wrap_sol:
        input_account = _derive_solana_associated_token_account(
            owner=user_public_key,
            mint=input_mint,
        )
    if not unwrap_sol:
        output_account = _derive_solana_associated_token_account(
            owner=user_public_key,
            mint=output_mint,
        )

    return {
        "wrap_sol": wrap_sol,
        "unwrap_sol": unwrap_sol,
        "input_account": input_account,
        "output_account": output_account,
    }


def _raydium_execution_error(code: str, message: str, **extra) -> dict:
    return _swap_execution_error(code, message, **extra)


def _raydium_quote_error_response(e: HTTPException) -> dict:
    return _swap_execution_error(
        "SWAP_EXECUTION_QUOTE_FAILED",
        "Could not refresh a Raydium quote for swap execution.",
        status_code=e.status_code,
    )


def _safe_raydium_provider_scalar(value, *, fallback: str | None = None):
    if value is None or isinstance(value, (dict, list, tuple)):
        return fallback

    text = str(value).strip()
    if not text:
        return fallback

    lower = text.lower()
    unsafe_markers = (
        "http://",
        "https://",
        "api-key",
        "api_key",
        "access_token",
        "key=",
        "token=",
        "auth=",
        "signature=",
        "password",
        "secret",
        "transaction_base64",
        "transactionbase64",
        "swaptransaction",
        "signed_transaction",
        "signedtransaction",
    )
    if any(marker in lower for marker in unsafe_markers):
        return fallback

    if len(text) > 240:
        text = text[:237] + "..."
    return text


def _safe_raydium_provider_error_details(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}

    provider_message = None
    for key in ("msg", "message"):
        provider_message = _safe_raydium_provider_scalar(payload.get(key))
        if provider_message:
            break

    provider_code = _safe_raydium_provider_scalar(payload.get("code") or payload.get("id"))

    error = payload.get("error")
    if isinstance(error, dict):
        if not provider_message:
            for key in ("msg", "message"):
                provider_message = _safe_raydium_provider_scalar(error.get(key))
                if provider_message:
                    break
        if not provider_code:
            provider_code = _safe_raydium_provider_scalar(error.get("code") or error.get("id"))
    elif error is not None and not provider_message:
        provider_message = _safe_raydium_provider_scalar(error)

    details = {}
    if provider_message:
        details["provider_message"] = provider_message
    if provider_code:
        details["provider_code"] = provider_code
    return details


def _fetch_fresh_raydium_execution_quote(
    *,
    input_meta: dict,
    output_meta: dict,
    amount_raw: int,
    slippage_bps: int,
) -> dict:
    params = _build_raydium_quote_params(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
        tx_version="V0",
    )

    try:
        return {
            "ok": True,
            "quote": _fetch_raydium_quote(params),
            "params": params,
        }
    except HTTPException as e:
        return _raydium_quote_error_response(e)


def _extract_raydium_transaction_base64(payload: dict) -> dict:
    data = payload.get("data")
    if isinstance(data, list):
        if len(data) > 1:
            return _raydium_execution_error(
                "SWAP_EXECUTION_RAYDIUM_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
                "Raydium returned multiple transactions, which are not supported in V1.",
            )
        if not data:
            return _raydium_execution_error(
                "SWAP_EXECUTION_RAYDIUM_TRANSACTION_MISSING",
                "Raydium did not return a swap transaction.",
            )
        item = data[0]
    elif isinstance(data, dict):
        item = data
    else:
        item = payload

    transaction = None
    if isinstance(item, dict):
        transaction = item.get("transaction") or item.get("transactionBase64")

    if not transaction:
        return _raydium_execution_error(
            "SWAP_EXECUTION_RAYDIUM_TRANSACTION_MISSING",
            "Raydium did not return a swap transaction.",
        )

    return {
        "ok": True,
        "transaction_base64": transaction,
    }


def _fetch_raydium_swap_transaction(
    *,
    swap_response: dict,
    user_public_key: str,
    tx_version: str = "V0",
    wrap_sol: bool = False,
    unwrap_sol: bool = False,
    compute_unit_price_micro_lamports: str | None = None,
    input_account: str | None = None,
    output_account: str | None = None,
) -> dict:
    payload = {
        "txVersion": tx_version,
        "wallet": user_public_key,
        "wrapSol": bool(wrap_sol),
        "unwrapSol": bool(unwrap_sol),
        "swapResponse": swap_response,
        "computeUnitPriceMicroLamports": str(
            RAYDIUM_DEFAULT_COMPUTE_UNIT_PRICE_MICRO_LAMPORTS
            if compute_unit_price_micro_lamports is None
            else compute_unit_price_micro_lamports
        ),
    }
    if input_account:
        payload["inputAccount"] = input_account
    if output_account:
        payload["outputAccount"] = output_account

    req = urllib.request.Request(
        "https://transaction-v1.raydium.io/transaction/swap-base-in",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "web3-digest/0.1 raydium-execution-prepare",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _raydium_execution_error(
                "SWAP_EXECUTION_RAYDIUM_RATE_LIMITED",
                "Raydium transaction preparation is rate-limited right now.",
                status_code=e.code,
            )
        if e.code in (401, 403):
            return _raydium_execution_error(
                "SWAP_EXECUTION_RAYDIUM_FORBIDDEN",
                "Raydium transaction preparation was blocked by the provider.",
                status_code=e.code,
            )
        return _raydium_execution_error(
            "SWAP_EXECUTION_RAYDIUM_PREPARE_FAILED",
            "Raydium transaction preparation failed.",
            status_code=e.code,
        )
    except Exception:
        return _raydium_execution_error(
            "SWAP_EXECUTION_RAYDIUM_PREPARE_FAILED",
            "Raydium transaction preparation failed.",
        )

    if data.get("success") is False:
        return _raydium_execution_error(
            "SWAP_EXECUTION_RAYDIUM_PREPARE_FAILED",
            "Raydium transaction preparation was not successful.",
            **_safe_raydium_provider_error_details(data),
        )

    extracted = _extract_raydium_transaction_base64(data)
    if extracted.get("ok") is not True:
        return extracted

    return {
        "ok": True,
        "transaction_base64": extracted["transaction_base64"],
        "raw": data,
    }


def _raydium_execution_quote_summary(
    *,
    quote: dict,
    from_token: str,
    to_token: str,
    amount: float,
    output_decimals: int,
    slippage_bps: int,
    variant_id: str,
) -> dict:
    data = quote.get("data") or {}
    return {
        "from_token": from_token,
        "to_token": to_token,
        "amount": amount,
        "estimated_output": _ui_amount(data.get("outputAmount"), output_decimals),
        "estimated_output_raw": data.get("outputAmount"),
        "min_received": _ui_amount(data.get("otherAmountThreshold"), output_decimals),
        "min_received_raw": data.get("otherAmountThreshold"),
        "slippage_bps": slippage_bps,
        "variant_id": variant_id,
    }


def _orca_execution_error(code: str, message: str, **extra) -> dict:
    return _swap_execution_error(code, message, **extra)


def _orca_quote_error_response(e: HTTPException) -> dict:
    return _swap_execution_error(
        "SWAP_EXECUTION_QUOTE_FAILED",
        "Could not refresh an Orca Whirlpool quote for swap execution.",
        status_code=e.status_code,
    )


def _safe_orca_provider_scalar(value, *, fallback: str | None = None):
    if value is None or isinstance(value, (dict, list, tuple)):
        return fallback

    text = str(value).strip()
    if not text:
        return fallback

    lower = text.lower()
    unsafe_markers = (
        "http://",
        "https://",
        "api-key",
        "api_key",
        "access_token",
        "key=",
        "token=",
        "auth=",
        "signature=",
        "password",
        "secret",
        "transaction_base64",
        "transactionbase64",
        "signed_transaction",
        "signedtransaction",
    )
    if any(marker in lower for marker in unsafe_markers):
        return fallback

    if len(text) > 240:
        text = text[:237] + "..."
    return text


def _safe_orca_provider_error_details(helper_error) -> dict:
    if not isinstance(helper_error, dict):
        return {}

    details = {}
    provider_message = _safe_orca_provider_scalar(helper_error.get("message") or helper_error.get("msg"))
    provider_code = _safe_orca_provider_scalar(helper_error.get("code") or helper_error.get("id"))
    provider_detail = _safe_orca_provider_scalar(helper_error.get("detail") or helper_error.get("details"))

    if provider_message:
        details["provider_message"] = provider_message
    if provider_code:
        details["provider_code"] = provider_code
    if provider_detail:
        details["provider_detail"] = provider_detail
    return details


def _configured_swap_prepare_rpc_url() -> tuple[str | None, str | None]:
    for name in (
        "SWAP_PREPARE_RPC_URL",
        "SWAP_SUBMIT_RPC_URL",
        "SOLANA_RPC_URL",
        "SOLANA_MAINNET_RPC_URL",
        "HELIUS_RPC_URL",
    ):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value, name
    return None, None


def _fetch_fresh_orca_whirlpool_execution_quote(
    *,
    input_meta: dict,
    output_meta: dict,
    amount_raw: int,
    slippage_bps: int,
) -> dict:
    payload = _build_orca_whirlpool_quote_payload(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
    )

    try:
        quote = _fetch_orca_whirlpool_quote(payload)
    except HTTPException as e:
        return _orca_quote_error_response(e)

    if not isinstance(quote, dict) or quote.get("ok") is not True:
        error = quote.get("error") if isinstance(quote, dict) else None
        safe_details = _safe_orca_provider_error_details(error)
        safe_details["quote_response_keys"] = sorted([
            str(key) for key in quote.keys()
            if isinstance(key, str) and _safe_orca_provider_scalar(key)
        ])[:24] if isinstance(quote, dict) else []
        if isinstance(error, dict):
            safe_details["quote_error_keys"] = sorted([
                str(key) for key in error.keys()
                if isinstance(key, str) and _safe_orca_provider_scalar(key)
            ])[:24]
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_PREPARE_FAILED",
            "Orca refreshed quote was not successful.",
            **safe_details,
        )

    return {
        "ok": True,
        "quote": quote,
        "payload": payload,
    }


def _extract_orca_whirlpool_transaction_base64(payload: dict) -> dict:
    transactions = payload.get("transactions")
    if isinstance(transactions, list):
        if len(transactions) > 1:
            return _orca_execution_error(
                "SWAP_EXECUTION_ORCA_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
                "Orca returned multiple transactions, which are not supported in V1.",
            )
        if not transactions:
            return _orca_execution_error(
                "SWAP_EXECUTION_ORCA_TRANSACTION_MISSING",
                "Orca did not return a swap transaction.",
            )
        item = transactions[0]
    else:
        data = payload.get("data")
        if isinstance(data, list):
            if len(data) > 1:
                return _orca_execution_error(
                    "SWAP_EXECUTION_ORCA_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
                    "Orca returned multiple transactions, which are not supported in V1.",
                )
            if not data:
                return _orca_execution_error(
                    "SWAP_EXECUTION_ORCA_TRANSACTION_MISSING",
                    "Orca did not return a swap transaction.",
                )
            item = data[0]
        elif isinstance(data, dict):
            item = data
        else:
            item = payload

    transaction = None
    if isinstance(item, dict):
        transaction = (
            item.get("transaction")
            or item.get("transactionBase64")
            or item.get("transaction_base64")
        )

    if not transaction:
        transaction = (
            payload.get("transaction")
            or payload.get("transactionBase64")
            or payload.get("transaction_base64")
        )

    if not transaction:
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_TRANSACTION_MISSING",
            "Orca did not return a swap transaction.",
        )

    return {
        "ok": True,
        "transaction_base64": transaction,
    }


def _fetch_orca_whirlpool_swap_transaction(
    *,
    quote_response: dict,
    user_public_key: str,
    tx_version: str = "V0",
) -> dict:
    helper_path = project_root() / "tools" / "orca_whirlpool_prepare.mjs"
    if not helper_path.exists():
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_HELPER_FAILED",
            "Orca transaction preparation helper is not available yet.",
        )

    payload = {
        "quote_response": quote_response,
        "user_public_key": user_public_key,
        "tx_version": tx_version,
    }
    rpc_url, _rpc_source = _configured_swap_prepare_rpc_url()
    if rpc_url:
        payload["rpc_url"] = rpc_url

    try:
        proc = subprocess.run(
            [os.getenv("NODE_BINARY") or "node", str(helper_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=25,
            cwd=project_root(),
        )
    except FileNotFoundError:
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_HELPER_FAILED",
            "Orca transaction preparation runtime is not available.",
        )
    except subprocess.TimeoutExpired:
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_HELPER_FAILED",
            "Orca transaction preparation helper timed out.",
        )
    except Exception:
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_HELPER_FAILED",
            "Orca transaction preparation helper failed.",
        )

    stdout = (proc.stdout or "").strip()
    if not stdout:
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_HELPER_FAILED",
            "Orca transaction preparation helper returned no JSON output.",
        )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_HELPER_FAILED",
            "Orca transaction preparation helper returned invalid JSON.",
        )

    if proc.returncode != 0 or data.get("ok") is False:
        helper_error = data.get("error") if isinstance(data, dict) else None
        helper_code = helper_error.get("code") if isinstance(helper_error, dict) else None
        if helper_code == "ORCA_MULTIPLE_TRANSACTIONS_UNSUPPORTED":
            return _orca_execution_error(
                "SWAP_EXECUTION_ORCA_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
                "Orca returned multiple transactions, which are not supported in V1.",
                **_safe_orca_provider_error_details(helper_error),
            )
        if helper_code in (
            "EMPTY_STDIN",
            "INVALID_JSON",
            "INVALID_REQUEST",
            "INVALID_QUOTE_RESPONSE",
            "INVALID_PUBLIC_KEY",
            "INVALID_AMOUNT_RAW",
            "INVALID_SLIPPAGE_BPS",
            "UNSUPPORTED_TX_VERSION",
        ):
            return _orca_execution_error(
                "SWAP_EXECUTION_ORCA_HELPER_FAILED",
                "Orca transaction preparation helper rejected the request.",
                **_safe_orca_provider_error_details(helper_error),
            )
        return _orca_execution_error(
            "SWAP_EXECUTION_ORCA_PREPARE_FAILED",
            "Orca transaction preparation was not successful.",
            **_safe_orca_provider_error_details(helper_error),
        )

    extracted = _extract_orca_whirlpool_transaction_base64(data)
    if extracted.get("ok") is not True:
        return extracted

    return {
        "ok": True,
        "transaction_base64": extracted["transaction_base64"],
        "raw": data,
    }


def _orca_execution_quote_summary(
    *,
    quote: dict,
    from_token: str,
    to_token: str,
    amount: float,
    output_decimals: int,
    slippage_bps: int,
    variant_id: str,
) -> dict:
    return {
        "from_token": from_token,
        "to_token": to_token,
        "amount": amount,
        "estimated_output": _ui_amount(quote.get("out_amount_raw"), output_decimals),
        "estimated_output_raw": quote.get("out_amount_raw"),
        "min_received": _ui_amount(quote.get("min_out_amount_raw"), output_decimals),
        "min_received_raw": quote.get("min_out_amount_raw"),
        "slippage_bps": slippage_bps,
        "variant_id": variant_id,
    }


def _meteora_execution_error(code: str, message: str, **extra) -> dict:
    return _swap_execution_error(code, message, **extra)


def _safe_meteora_provider_scalar(value, *, fallback: str | None = None):
    if value is None or isinstance(value, (dict, list, tuple)):
        return fallback

    text = str(value).strip()
    if not text:
        return fallback

    lower = text.lower()
    unsafe_markers = (
        "http://",
        "https://",
        "api-key",
        "api_key",
        "access_token",
        "key=",
        "token=",
        "auth=",
        "signature=",
        "password",
        "secret",
        "transaction_base64",
        "transactionbase64",
        "swaptransaction",
        "signed_transaction",
        "signedtransaction",
    )
    if any(marker in lower for marker in unsafe_markers):
        return fallback

    if len(text) > 240:
        text = text[:237] + "..."
    return text


def _safe_meteora_provider_error_details(helper_error) -> dict:
    if not isinstance(helper_error, dict):
        return {}

    details = {}
    provider_message = _safe_meteora_provider_scalar(helper_error.get("message") or helper_error.get("msg"))
    provider_code = _safe_meteora_provider_scalar(helper_error.get("code") or helper_error.get("id"))
    provider_detail = _safe_meteora_provider_scalar(helper_error.get("detail") or helper_error.get("details"))

    if provider_message:
        details["provider_message"] = provider_message
    if provider_code:
        details["provider_code"] = provider_code
    if provider_detail:
        details["provider_detail"] = provider_detail
    return details


def _fetch_fresh_meteora_dlmm_execution_quote(
    *,
    input_meta: dict,
    output_meta: dict,
    amount_raw: int,
    slippage_bps: int,
) -> dict:
    rpc_url, _rpc_source = _configured_swap_prepare_rpc_url()
    payload = _build_meteora_dlmm_quote_payload(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
        rpc_url=rpc_url or SOLANA_MAINNET_RPC_URL,
    )

    result = _try_fetch_meteora_dlmm_quote(payload)
    if result.get("ok") is not True:
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_PREPARE_FAILED",
            "Could not refresh a Meteora DLMM quote for swap execution.",
            provider_detail=result.get("error", {}).get("detail") if isinstance(result.get("error"), dict) else None,
            provider_code=result.get("error", {}).get("code") if isinstance(result.get("error"), dict) else None,
        )

    quote = result["data"]
    if quote.get("route_shape") == "two-hop" or isinstance(quote.get("leg_quotes"), list):
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_UNSUPPORTED_ROUTE",
            "Only single-pool Meteora DLMM routes are supported for prepare V1.",
            provider_detail="two-hop routes remain quote-only",
        )
    if not (quote.get("pool") or {}).get("address") or not quote.get("bin_arrays"):
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_PREPARE_FAILED",
            "Meteora DLMM quote is missing pool or bin array data required for prepare.",
        )

    return {
        "ok": True,
        "quote": quote,
        "payload": payload,
    }


def _extract_meteora_dlmm_transaction_base64(payload: dict) -> dict:
    transaction = payload.get("transaction_base64") or payload.get("transactionBase64") or payload.get("transaction")
    if not transaction:
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_TRANSACTION_MISSING",
            "Meteora DLMM did not return a swap transaction.",
        )
    return {
        "ok": True,
        "transaction_base64": transaction,
    }


def _fetch_meteora_dlmm_swap_transaction(
    *,
    quote_response: dict,
    user_public_key: str,
    tx_version: str = "V0",
) -> dict:
    helper_path = project_root() / "tools" / "meteora_dlmm_prepare.mjs"
    if not helper_path.exists():
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_HELPER_FAILED",
            "Meteora DLMM transaction preparation helper is not available yet.",
        )

    payload = {
        "user_public_key": user_public_key,
        "pool_address": (quote_response.get("pool") or {}).get("address"),
        "input_mint": quote_response.get("input_mint"),
        "output_mint": quote_response.get("output_mint"),
        "amount_raw": quote_response.get("in_amount_raw"),
        "min_out_amount_raw": quote_response.get("min_out_amount_raw"),
        "slippage_bps": quote_response.get("slippage_bps"),
        "bin_arrays": quote_response.get("bin_arrays"),
        "route_shape": quote_response.get("route_shape") or "single-pool",
        "tx_version": tx_version,
    }
    rpc_url, _rpc_source = _configured_swap_prepare_rpc_url()
    if rpc_url:
        payload["rpc_url"] = rpc_url

    try:
        proc = subprocess.run(
            [os.getenv("NODE_BINARY") or "node", str(helper_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=25,
            cwd=project_root(),
        )
    except FileNotFoundError:
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_HELPER_FAILED",
            "Meteora DLMM transaction preparation runtime is not available.",
        )
    except subprocess.TimeoutExpired:
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_HELPER_FAILED",
            "Meteora DLMM transaction preparation helper timed out.",
        )
    except Exception:
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_HELPER_FAILED",
            "Meteora DLMM transaction preparation helper failed.",
        )

    stdout = (proc.stdout or "").strip()
    if not stdout:
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_HELPER_FAILED",
            "Meteora DLMM transaction preparation helper returned no JSON output.",
        )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_HELPER_FAILED",
            "Meteora DLMM transaction preparation helper returned invalid JSON.",
        )

    if proc.returncode != 0 or data.get("ok") is False:
        helper_error = data.get("error") if isinstance(data, dict) else None
        helper_code = helper_error.get("code") if isinstance(helper_error, dict) else None
        if helper_code == "METEORA_DLMM_UNSUPPORTED_ROUTE":
            return _meteora_execution_error(
                "SWAP_EXECUTION_METEORA_UNSUPPORTED_ROUTE",
                "This Meteora DLMM route cannot be prepared for execution.",
                **_safe_meteora_provider_error_details(helper_error),
            )
        if helper_code in (
            "EMPTY_STDIN",
            "INVALID_JSON",
            "INVALID_REQUEST",
            "INVALID_PUBLIC_KEY",
            "INVALID_AMOUNT_RAW",
            "METEORA_DLMM_BIN_ARRAYS_REQUIRED",
            "INVALID_SLIPPAGE_BPS",
            "UNSUPPORTED_TX_VERSION",
        ):
            return _meteora_execution_error(
                "SWAP_EXECUTION_METEORA_HELPER_FAILED",
                "Meteora DLMM transaction preparation helper rejected the request.",
                **_safe_meteora_provider_error_details(helper_error),
            )
        return _meteora_execution_error(
            "SWAP_EXECUTION_METEORA_PREPARE_FAILED",
            "Meteora DLMM transaction preparation was not successful.",
            **_safe_meteora_provider_error_details(helper_error),
        )

    extracted = _extract_meteora_dlmm_transaction_base64(data)
    if extracted.get("ok") is not True:
        return extracted

    return {
        "ok": True,
        "transaction_base64": extracted["transaction_base64"],
        "raw": data,
    }


def _meteora_dlmm_execution_quote_summary(
    *,
    quote: dict,
    from_token: str,
    to_token: str,
    amount: float,
    output_decimals: int,
    slippage_bps: int,
    variant_id: str,
) -> dict:
    return {
        "from_token": from_token,
        "to_token": to_token,
        "amount": amount,
        "estimated_output": _ui_amount(quote.get("out_amount_raw"), output_decimals),
        "estimated_output_raw": quote.get("out_amount_raw"),
        "min_received": _ui_amount(quote.get("min_out_amount_raw"), output_decimals),
        "min_received_raw": quote.get("min_out_amount_raw"),
        "slippage_bps": slippage_bps,
        "variant_id": variant_id,
    }


def _pumpswap_execution_error(code: str, message: str, **extra) -> dict:
    return _swap_execution_error(code, message, **extra)


def _pumpswap_quote_error_response(e: HTTPException) -> dict:
    return _swap_execution_error(
        "SWAP_EXECUTION_PUMPSWAP_PREPARE_FAILED",
        "Could not refresh a PumpSwap quote for swap execution.",
        status_code=e.status_code,
    )


def _safe_pumpswap_provider_scalar(value, *, fallback: str | None = None):
    if value is None or isinstance(value, (dict, list, tuple)):
        return fallback

    text = str(value).strip()
    if not text:
        return fallback

    lower = text.lower()
    unsafe_markers = (
        "http://",
        "https://",
        "api-key",
        "api_key",
        "access_token",
        "key=",
        "token=",
        "auth=",
        "signature=",
        "password",
        "secret",
        "transaction_base64",
        "transactionbase64",
        "swaptransaction",
        "signed_transaction",
        "signedtransaction",
    )
    if any(marker in lower for marker in unsafe_markers):
        return fallback

    if len(text) > 240:
        text = text[:237] + "..."
    return text


def _safe_pumpswap_provider_error_details(helper_error) -> dict:
    if not isinstance(helper_error, dict):
        return {}

    details = {}
    provider_message = _safe_pumpswap_provider_scalar(helper_error.get("message") or helper_error.get("msg"))
    provider_code = _safe_pumpswap_provider_scalar(helper_error.get("code") or helper_error.get("id"))
    provider_detail = _safe_pumpswap_provider_scalar(helper_error.get("detail") or helper_error.get("details"))

    if provider_message:
        details["provider_message"] = provider_message
    if provider_code:
        details["provider_code"] = provider_code
    if provider_detail:
        details["provider_detail"] = provider_detail
    return details


def _safe_pumpswap_quote_error_details(quote_response) -> dict:
    if not isinstance(quote_response, dict):
        return {}

    error = quote_response.get("error")
    if not isinstance(error, dict):
        return {}

    details = {}
    provider_message = _safe_pumpswap_provider_scalar(error.get("message") or error.get("msg"))
    provider_code = _safe_pumpswap_provider_scalar(error.get("code") or error.get("id"))
    raw_details = error.get("details") or error.get("detail")
    provider_detail = _safe_pumpswap_provider_scalar(raw_details)
    if provider_detail is None and isinstance(raw_details, dict):
        provider_detail = _safe_pumpswap_provider_scalar(raw_details.get("message") or raw_details.get("detail"))

    if provider_message:
        details["provider_message"] = provider_message
    if provider_code:
        details["provider_code"] = provider_code
    if provider_detail:
        details["provider_detail"] = provider_detail
    return details


def _fetch_fresh_pumpswap_execution_quote(
    *,
    input_meta: dict,
    output_meta: dict,
    amount_raw: int,
    slippage_bps: int,
    user_public_key: str,
) -> dict:
    rpc_url, _rpc_source = _configured_swap_prepare_rpc_url()
    payload = _build_pumpswap_quote_payload(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
        rpc_url=rpc_url or SOLANA_MAINNET_RPC_URL,
        user_public_key=user_public_key,
    )

    try:
        quote = _fetch_pumpswap_quote(payload)
        if not isinstance(quote, dict) or quote.get("ok") is False:
            return _pumpswap_execution_error(
                "SWAP_EXECUTION_PUMPSWAP_PREPARE_FAILED",
                "Could not refresh a PumpSwap quote for swap execution.",
                **_safe_pumpswap_quote_error_details(quote),
            )
        if quote.get("direction") not in {"buy_base_with_quote", "sell_base_for_quote"}:
            return _pumpswap_execution_error(
                "SWAP_EXECUTION_PUMPSWAP_UNSUPPORTED_ROUTE",
                "This PumpSwap route cannot be prepared for execution.",
            )
        return {
            "ok": True,
            "quote": quote,
            "payload": payload,
        }
    except HTTPException as e:
        return _pumpswap_quote_error_response(e)


def _extract_pumpswap_transaction_base64(payload: dict) -> dict:
    transactions = payload.get("transactions")
    if isinstance(transactions, list):
        if len(transactions) > 1:
            return _pumpswap_execution_error(
                "SWAP_EXECUTION_PUMPSWAP_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
                "PumpSwap returned multiple transactions, which are not supported in V1.",
            )
        if not transactions:
            return _pumpswap_execution_error(
                "SWAP_EXECUTION_PUMPSWAP_TRANSACTION_MISSING",
                "PumpSwap did not return a swap transaction.",
            )
        item = transactions[0]
    else:
        data = payload.get("data")
        if isinstance(data, list):
            if len(data) > 1:
                return _pumpswap_execution_error(
                    "SWAP_EXECUTION_PUMPSWAP_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
                    "PumpSwap returned multiple transactions, which are not supported in V1.",
                )
            if not data:
                return _pumpswap_execution_error(
                    "SWAP_EXECUTION_PUMPSWAP_TRANSACTION_MISSING",
                    "PumpSwap did not return a swap transaction.",
                )
            item = data[0]
        elif isinstance(data, dict):
            item = data
        else:
            item = payload

    transaction = None
    if isinstance(item, dict):
        transaction = (
            item.get("transaction")
            or item.get("transactionBase64")
            or item.get("transaction_base64")
        )

    if not transaction:
        transaction = (
            payload.get("transaction")
            or payload.get("transactionBase64")
            or payload.get("transaction_base64")
        )

    if not transaction:
        return _pumpswap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_TRANSACTION_MISSING",
            "PumpSwap did not return a swap transaction.",
        )

    return {
        "ok": True,
        "transaction_base64": transaction,
    }


def _fetch_pumpswap_swap_transaction(
    *,
    quote_response: dict,
    user_public_key: str,
    tx_version: str = "V0",
) -> dict:
    helper_path = project_root() / "tools" / "pumpswap_prepare.mjs"
    if not helper_path.exists():
        return _pumpswap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED",
            "PumpSwap transaction preparation helper is not available yet.",
        )

    payload = {
        "quote_response": quote_response,
        "user_public_key": user_public_key,
        "tx_version": tx_version,
    }
    rpc_url, _rpc_source = _configured_swap_prepare_rpc_url()
    if rpc_url:
        payload["rpc_url"] = rpc_url

    try:
        proc = subprocess.run(
            [os.getenv("NODE_BINARY") or "node", str(helper_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=25,
            cwd=project_root(),
        )
    except FileNotFoundError:
        return _pumpswap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED",
            "PumpSwap transaction preparation runtime is not available.",
        )
    except subprocess.TimeoutExpired:
        return _pumpswap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED",
            "PumpSwap transaction preparation helper timed out.",
        )
    except Exception:
        return _pumpswap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED",
            "PumpSwap transaction preparation helper failed.",
        )

    stdout = (proc.stdout or "").strip()
    if not stdout:
        return _pumpswap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED",
            "PumpSwap transaction preparation helper returned no JSON output.",
        )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return _pumpswap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED",
            "PumpSwap transaction preparation helper returned invalid JSON.",
        )

    if proc.returncode != 0 or data.get("ok") is False:
        helper_error = data.get("error") if isinstance(data, dict) else None
        helper_code = helper_error.get("code") if isinstance(helper_error, dict) else None
        if helper_code == "PUMPSWAP_MULTIPLE_TRANSACTIONS_UNSUPPORTED":
            return _pumpswap_execution_error(
                "SWAP_EXECUTION_PUMPSWAP_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
                "PumpSwap returned multiple transactions, which are not supported in V1.",
                **_safe_pumpswap_provider_error_details(helper_error),
            )
        if helper_code in (
            "PUMPSWAP_PREPARE_NOT_IMPLEMENTED",
            "EMPTY_STDIN",
            "INVALID_JSON",
            "INVALID_REQUEST",
            "INVALID_QUOTE_RESPONSE",
            "INVALID_PUBLIC_KEY",
            "UNSUPPORTED_TX_VERSION",
        ):
            return _pumpswap_execution_error(
                "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED",
                "PumpSwap transaction preparation helper rejected the request.",
                **_safe_pumpswap_provider_error_details(helper_error),
            )
        return _pumpswap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_PREPARE_FAILED",
            "PumpSwap transaction preparation was not successful.",
            **_safe_pumpswap_provider_error_details(helper_error),
        )

    extracted = _extract_pumpswap_transaction_base64(data)
    if extracted.get("ok") is not True:
        return extracted

    return {
        "ok": True,
        "transaction_base64": extracted["transaction_base64"],
        "raw": data,
    }


def _pumpswap_execution_quote_summary(
    *,
    quote: dict,
    from_token: str,
    to_token: str,
    amount: float,
    output_decimals: int,
    slippage_bps: int,
    variant_id: str,
) -> dict:
    return {
        "from_token": from_token,
        "to_token": to_token,
        "amount": amount,
        "estimated_output": _ui_amount(quote.get("out_amount_raw"), output_decimals),
        "estimated_output_raw": quote.get("out_amount_raw"),
        "min_received": _ui_amount(quote.get("min_out_amount_raw"), output_decimals),
        "min_received_raw": quote.get("min_out_amount_raw"),
        "slippage_bps": slippage_bps,
        "variant_id": variant_id,
    }


def _provider_not_implemented_error(provider_id: str) -> dict:
    return _swap_execution_error(
        "SWAP_EXECUTION_PROVIDER_NOT_IMPLEMENTED",
        "Execution is not available for this provider yet.",
        provider=provider_id or None,
    )


def _swap_submit_preflight_metadata() -> dict:
    rpc_url, rpc_source = _configured_swap_submit_rpc_url()
    return {
        "can_submit": bool(rpc_url),
        "network": "solana",
        "required_config": "SWAP_SUBMIT_RPC_URL",
        "configured_source": rpc_source if rpc_url else None,
    }


def _prepare_jupiter_swap_transaction(
    *,
    input_meta: dict,
    output_meta: dict,
    amount: float,
    amount_raw: int,
    slippage_bps: int,
    variant_id: str,
    user_public_key: str,
    from_token_query: str,
    to_token_query: str,
) -> dict:
    if variant_id not in JUPITER_EXECUTION_VARIANTS:
        return _swap_execution_error(
            "SWAP_EXECUTION_UNSUPPORTED_ROUTE",
            "This route cannot be prepared for execution.",
        )

    fresh_quote = _fetch_fresh_jupiter_execution_quote(
        input_meta=input_meta,
        output_meta=output_meta,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
        variant_id=variant_id,
    )
    if fresh_quote.get("ok") is not True:
        return fresh_quote

    swap_tx = _fetch_jupiter_swap_transaction(
        quote_response=fresh_quote["quote"],
        user_public_key=user_public_key,
        as_legacy_transaction=False,
    )
    if swap_tx.get("ok") is not True:
        return swap_tx

    from_token = input_meta.get("quote_label") or input_meta.get("symbol") or from_token_query
    to_token = output_meta.get("quote_label") or output_meta.get("symbol") or to_token_query

    return {
        "ok": True,
        "provider": "jupiter-metis",
        "execution_surface_label": "Jupiter",
        "execution_status": "prepared",
        "transaction_base64": swap_tx.get("swap_transaction"),
        "transaction_format": "versioned",
        "last_valid_block_height": swap_tx.get("last_valid_block_height"),
        "quote_summary": _jupiter_execution_quote_summary(
            quote=fresh_quote["quote"],
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            output_decimals=output_meta["decimals"],
            slippage_bps=slippage_bps,
            variant_id=variant_id,
        ),
        "warnings": ["quote_refreshed_before_execution"],
        "submit_preflight": _swap_submit_preflight_metadata(),
    }


def _prepare_raydium_swap_transaction(
    *,
    input_meta: dict,
    output_meta: dict,
    amount: float,
    amount_raw: int,
    slippage_bps: int,
    variant_id: str,
    user_public_key: str,
    from_token_query: str,
    to_token_query: str,
) -> dict:
    if variant_id != "raydium_quote":
        return _swap_execution_error(
            "SWAP_EXECUTION_UNSUPPORTED_ROUTE",
            "This Raydium route cannot be prepared for execution.",
        )

    fresh_quote = _fetch_fresh_raydium_execution_quote(
        input_meta=input_meta,
        output_meta=output_meta,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
    )
    if fresh_quote.get("ok") is not True:
        return fresh_quote

    try:
        token_accounts = _raydium_prepare_token_accounts(
            input_mint=input_meta.get("mint") or "",
            output_mint=output_meta.get("mint") or "",
            user_public_key=user_public_key,
        )
    except Exception:
        return _swap_execution_error(
            "SWAP_EXECUTION_RAYDIUM_UNSUPPORTED_ROUTE",
            "This Raydium route cannot be prepared because required token accounts could not be derived.",
        )

    swap_tx = _fetch_raydium_swap_transaction(
        swap_response=fresh_quote["quote"],
        user_public_key=user_public_key,
        tx_version="V0",
        wrap_sol=token_accounts["wrap_sol"],
        unwrap_sol=token_accounts["unwrap_sol"],
        input_account=token_accounts["input_account"],
        output_account=token_accounts["output_account"],
    )
    if swap_tx.get("ok") is not True:
        return swap_tx

    from_token = input_meta.get("quote_label") or input_meta.get("symbol") or from_token_query
    to_token = output_meta.get("quote_label") or output_meta.get("symbol") or to_token_query

    return {
        "ok": True,
        "provider": "raydium-trade-api",
        "execution_surface_label": "Raydium",
        "execution_status": "prepared",
        "transaction_base64": swap_tx.get("transaction_base64"),
        "transaction_format": "versioned",
        "quote_summary": _raydium_execution_quote_summary(
            quote=fresh_quote["quote"],
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            output_decimals=output_meta["decimals"],
            slippage_bps=slippage_bps,
            variant_id=variant_id,
        ),
        "warnings": ["quote_refreshed_before_execution"],
        "submit_preflight": _swap_submit_preflight_metadata(),
    }


def _prepare_orca_whirlpool_swap_transaction(
    *,
    input_meta: dict,
    output_meta: dict,
    amount: float,
    amount_raw: int,
    slippage_bps: int,
    variant_id: str,
    user_public_key: str,
    from_token_query: str,
    to_token_query: str,
) -> dict:
    if variant_id != "orca_whirlpool_quote":
        return _swap_execution_error(
            "SWAP_EXECUTION_ORCA_UNSUPPORTED_ROUTE",
            "This Orca route cannot be prepared for execution.",
        )

    fresh_quote = _fetch_fresh_orca_whirlpool_execution_quote(
        input_meta=input_meta,
        output_meta=output_meta,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
    )
    if fresh_quote.get("ok") is not True:
        return fresh_quote

    swap_tx = _fetch_orca_whirlpool_swap_transaction(
        quote_response=fresh_quote["quote"],
        user_public_key=user_public_key,
        tx_version="V0",
    )
    if swap_tx.get("ok") is not True:
        return swap_tx

    from_token = input_meta.get("quote_label") or input_meta.get("symbol") or from_token_query
    to_token = output_meta.get("quote_label") or output_meta.get("symbol") or to_token_query

    return {
        "ok": True,
        "provider": "orca-whirlpool",
        "execution_surface_label": "Orca",
        "execution_status": "prepared",
        "transaction_base64": swap_tx.get("transaction_base64"),
        "transaction_format": "versioned",
        "quote_summary": _orca_execution_quote_summary(
            quote=fresh_quote["quote"],
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            output_decimals=output_meta["decimals"],
            slippage_bps=slippage_bps,
            variant_id=variant_id,
        ),
        "warnings": ["quote_refreshed_before_execution"],
        "submit_preflight": _swap_submit_preflight_metadata(),
    }


def _prepare_meteora_dlmm_swap_transaction(
    *,
    input_meta: dict,
    output_meta: dict,
    amount: float,
    amount_raw: int,
    slippage_bps: int,
    variant_id: str,
    user_public_key: str,
    from_token_query: str,
    to_token_query: str,
) -> dict:
    if variant_id != "meteora_dlmm_quote":
        return _swap_execution_error(
            "SWAP_EXECUTION_METEORA_UNSUPPORTED_ROUTE",
            "This Meteora DLMM route cannot be prepared for execution.",
        )

    fresh_quote = _fetch_fresh_meteora_dlmm_execution_quote(
        input_meta=input_meta,
        output_meta=output_meta,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
    )
    if fresh_quote.get("ok") is not True:
        return fresh_quote

    swap_tx = _fetch_meteora_dlmm_swap_transaction(
        quote_response=fresh_quote["quote"],
        user_public_key=user_public_key,
        tx_version="V0",
    )
    if swap_tx.get("ok") is not True:
        return swap_tx

    from_token = input_meta.get("quote_label") or input_meta.get("symbol") or from_token_query
    to_token = output_meta.get("quote_label") or output_meta.get("symbol") or to_token_query

    return {
        "ok": True,
        "provider": "meteora-dlmm",
        "execution_surface_label": "Meteora",
        "execution_status": "prepared",
        "transaction_base64": swap_tx.get("transaction_base64"),
        "transaction_format": "versioned",
        "quote_summary": _meteora_dlmm_execution_quote_summary(
            quote=fresh_quote["quote"],
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            output_decimals=output_meta["decimals"],
            slippage_bps=slippage_bps,
            variant_id=variant_id,
        ),
        "warnings": ["quote_refreshed_before_execution", "meteora_dlmm_prepare_research_only"],
        "submit_preflight": _swap_submit_preflight_metadata(),
    }


def _prepare_pumpswap_swap_transaction(
    *,
    input_meta: dict,
    output_meta: dict,
    amount: float,
    amount_raw: int,
    slippage_bps: int,
    variant_id: str,
    user_public_key: str,
    from_token_query: str,
    to_token_query: str,
) -> dict:
    if variant_id != "pumpswap_quote":
        return _swap_execution_error(
            "SWAP_EXECUTION_PUMPSWAP_UNSUPPORTED_ROUTE",
            "This PumpSwap route cannot be prepared for execution.",
        )

    fresh_quote = _fetch_fresh_pumpswap_execution_quote(
        input_meta=input_meta,
        output_meta=output_meta,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
        user_public_key=user_public_key,
    )
    if fresh_quote.get("ok") is not True:
        return fresh_quote

    swap_tx = _fetch_pumpswap_swap_transaction(
        quote_response=fresh_quote["quote"],
        user_public_key=user_public_key,
        tx_version="V0",
    )
    if swap_tx.get("ok") is not True:
        return swap_tx

    from_token = input_meta.get("quote_label") or input_meta.get("symbol") or from_token_query
    to_token = output_meta.get("quote_label") or output_meta.get("symbol") or to_token_query

    return {
        "ok": True,
        "provider": "pumpswap",
        "execution_surface_label": "PumpSwap",
        "execution_status": "prepared",
        "transaction_base64": swap_tx.get("transaction_base64"),
        "transaction_format": "versioned",
        "quote_summary": _pumpswap_execution_quote_summary(
            quote=fresh_quote["quote"],
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            output_decimals=output_meta["decimals"],
            slippage_bps=slippage_bps,
            variant_id=variant_id,
        ),
        "warnings": ["quote_refreshed_before_execution"],
        "submit_preflight": _swap_submit_preflight_metadata(),
    }


def prepare_swap_transaction_with_provider(
    *,
    provider_id: str,
    input_meta: dict,
    output_meta: dict,
    amount: float,
    amount_raw: int,
    slippage_bps: int,
    variant_id: str,
    user_public_key: str,
    from_token_query: str,
    to_token_query: str,
) -> dict:
    provider = get_swap_execution_provider(provider_id)
    if not provider:
        return _provider_not_implemented_error(provider_id)

    prepare = provider["prepare"]
    return prepare(
        input_meta=input_meta,
        output_meta=output_meta,
        amount=amount,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
        variant_id=variant_id,
        user_public_key=user_public_key,
        from_token_query=from_token_query,
        to_token_query=to_token_query,
    )



SOLANA_MAINNET_RPC_URL = os.environ.get(
    "SOLANA_MAINNET_RPC_URL",
    "https://api.mainnet-beta.solana.com",
).strip()


MAX_SIGNED_SWAP_TRANSACTION_BASE64_CHARS = 200_000


def _configured_swap_submit_rpc_url() -> tuple[str | None, str | None]:
    for name in ("SWAP_SUBMIT_RPC_URL", "SOLANA_RPC_URL", "SOLANA_MAINNET_RPC_URL", "HELIUS_RPC_URL"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value, name
    return None, None


def _swap_submit_error(code: str, message: str, **extra) -> dict:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            **extra,
        },
    }


def _is_swap_submit_rate_limited(value) -> bool:
    text = str(value or "").lower()
    return "too many requests" in text or "rate limit" in text or "rate-limited" in text


def _is_swap_submit_forbidden(value) -> bool:
    text = str(value or "").lower()
    return "forbidden" in text or "access denied" in text or "not authorized" in text


def _safe_rpc_request_exception_detail(exc: Exception) -> str:
    exc_type = type(exc).__name__
    return f"RPC request failed before a response was received. error_type={exc_type}"


def _safe_submit_rpc_error(value) -> dict:
    if not isinstance(value, dict):
        return {
            "message": "RPC returned an error.",
        }

    safe = {}
    if value.get("code") is not None:
        safe["code"] = value.get("code")

    message = str(value.get("message") or "RPC returned an error.")
    if len(message) > 240:
        message = message[:237] + "..."
    safe["message"] = message
    return safe


def _fetch_solana_send_transaction(
    *,
    signed_transaction_base64: str,
    rpc_url: str,
    skip_preflight: bool = False,
    preflight_commitment: str = "confirmed",
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sendTransaction",
        "params": [
            signed_transaction_base64,
            {
                "encoding": "base64",
                "skipPreflight": bool(skip_preflight),
                "preflightCommitment": preflight_commitment or "confirmed",
            },
        ],
    }

    try:
        response = requests.post(
            rpc_url,
            json=payload,
            timeout=25,
            headers={"accept": "application/json", "content-type": "application/json"},
        )
    except requests.RequestException as exc:
        return _swap_submit_error(
            "SWAP_SUBMIT_FAILED",
            "Transaction submission failed.",
            detail=_safe_rpc_request_exception_detail(exc),
        )

    if response.status_code == 403:
        return _swap_submit_error(
            "SWAP_SUBMIT_FORBIDDEN",
            "Transaction submission was blocked by RPC.",
            status_code=response.status_code,
        )
    if response.status_code == 429:
        return _swap_submit_error(
            "SWAP_SUBMIT_RATE_LIMITED",
            "RPC is rate-limited. Try again later.",
            status_code=response.status_code,
        )
    if not response.ok:
        return _swap_submit_error(
            "SWAP_SUBMIT_FAILED",
            "Transaction submission failed.",
            status_code=response.status_code,
            detail="RPC returned an HTTP error.",
        )

    try:
        data = response.json()
    except ValueError as exc:
        return _swap_submit_error(
            "SWAP_SUBMIT_FAILED",
            "Transaction submission returned invalid JSON.",
            detail=str(exc),
        )

    if not isinstance(data, dict):
        return _swap_submit_error(
            "SWAP_SUBMIT_FAILED",
            "Transaction submission returned an unexpected response shape.",
        )

    if data.get("error"):
        rpc_error = data.get("error")
        safe_rpc_error = _safe_submit_rpc_error(rpc_error)
        if _is_swap_submit_rate_limited(rpc_error):
            return _swap_submit_error(
                "SWAP_SUBMIT_RATE_LIMITED",
                "RPC is rate-limited. Try again later.",
                status_code=429,
                rpc_error=safe_rpc_error,
            )
        if _is_swap_submit_forbidden(rpc_error):
            return _swap_submit_error(
                "SWAP_SUBMIT_FORBIDDEN",
                "Transaction submission was blocked by RPC.",
                status_code=403,
                rpc_error=safe_rpc_error,
            )
        return _swap_submit_error(
            "SWAP_SUBMIT_FAILED",
            "Transaction submission failed.",
            rpc_error=safe_rpc_error,
        )

    signature = data.get("result")
    if not isinstance(signature, str) or not signature.strip():
        return _swap_submit_error(
            "SWAP_SUBMIT_FAILED",
            "Transaction submission did not return a signature.",
        )

    return {
        "ok": True,
        "signature": signature.strip(),
        "status": "submitted",
    }


MAX_SWAP_PREFLIGHT_TRANSACTION_BASE64_CHARS = 200_000
SPL_TOKEN_ACCOUNT_RENT_EXEMPT_LAMPORTS_FALLBACK = 2_039_280
SPL_TOKEN_ACCOUNT_RENT_EXEMPT_SIZE = 165
SOLANA_SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
SOLANA_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SOLANA_ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
SOLANA_WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58_encode_bytes(raw: bytes) -> str:
    if not raw:
        return ""
    value = int.from_bytes(raw, "big")
    encoded = ""
    while value:
        value, remainder = divmod(value, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded
    leading_zeroes = len(raw) - len(raw.lstrip(b"\x00"))
    return ("1" * leading_zeroes) + encoded


def _read_solana_shortvec(raw: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(3):
        if offset >= len(raw):
            raise ValueError("shortvec out of range")
        byte = raw[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    raise ValueError("shortvec too long")


def _skip_solana_shortvec_bytes(raw: bytes, offset: int) -> int:
    length, offset = _read_solana_shortvec(raw, offset)
    end = offset + length
    if end > len(raw):
        raise ValueError("shortvec bytes out of range")
    return end


def _read_solana_instruction_indexes(raw: bytes, offset: int) -> tuple[list[int], int]:
    length, offset = _read_solana_shortvec(raw, offset)
    end = offset + length
    if end > len(raw):
        raise ValueError("instruction accounts out of range")
    return list(raw[offset:end]), end


def _extract_pubkeys_from_solana_logs(*values) -> list[str]:
    text = " ".join(str(value or "") for value in values)
    candidates = re.findall(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b", text)
    safe = []
    for candidate in candidates:
        if candidate in safe:
            continue
        safe.append(candidate)
        if len(safe) >= 4:
            break
    return safe


def _fetch_solana_rent_exempt_lamports(rpc_url: str, account_size: int = SPL_TOKEN_ACCOUNT_RENT_EXEMPT_SIZE) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getMinimumBalanceForRentExemption",
        "params": [account_size],
    }
    try:
        response = requests.post(
            rpc_url,
            json=payload,
            timeout=15,
            headers={"accept": "application/json", "content-type": "application/json"},
        )
        if not response.ok:
            raise ValueError("rent RPC returned non-OK status")
        data = response.json()
    except Exception:
        return {
            "ok": False,
            "lamports": SPL_TOKEN_ACCOUNT_RENT_EXEMPT_LAMPORTS_FALLBACK,
            "source": "fallback_spl_token_account_rent_exempt_lamports",
        }

    lamports = data.get("result") if isinstance(data, dict) else None
    if not isinstance(lamports, int) or lamports <= 0:
        return {
            "ok": False,
            "lamports": SPL_TOKEN_ACCOUNT_RENT_EXEMPT_LAMPORTS_FALLBACK,
            "source": "fallback_spl_token_account_rent_exempt_lamports",
        }

    return {
        "ok": True,
        "lamports": lamports,
        "source": "rpc_getMinimumBalanceForRentExemption_165",
    }


def _build_swap_setup_cost_estimate(transaction_diagnostics: dict | None, rpc_url: str) -> dict | None:
    if not isinstance(transaction_diagnostics, dict):
        return None
    ata_details = transaction_diagnostics.get("ata_create_details")
    if not isinstance(ata_details, list) or not ata_details:
        return None

    rent = _fetch_solana_rent_exempt_lamports(rpc_url, SPL_TOKEN_ACCOUNT_RENT_EXEMPT_SIZE)
    rent_lamports = int(rent.get("lamports") or SPL_TOKEN_ACCOUNT_RENT_EXEMPT_LAMPORTS_FALLBACK)
    source = rent.get("source") or "fallback_spl_token_account_rent_exempt_lamports"
    components = []
    for detail in ata_details:
        if not isinstance(detail, dict):
            continue
        components.append({
            "kind": "ata_create",
            "instruction_index": detail.get("instruction_index"),
            "mint": detail.get("mint"),
            "ata_account": detail.get("ata_account"),
            "owner": detail.get("owner"),
            "payer": detail.get("payer"),
            "lamports": rent_lamports,
            "source": source,
        })

    total_lamports = sum(int(item.get("lamports") or 0) for item in components)
    return {
        "setup_cost_estimate_source": source,
        "setup_cost_components": components,
        "setup_cost_estimate_lamports": total_lamports,
        "setup_cost_estimate_sol": total_lamports / 1_000_000_000,
    }


def _decode_solana_transaction_diagnostics(transaction_base64: str, *, expected_user_public_key: str = "") -> dict:
    try:
        raw = base64.b64decode((transaction_base64 or "").strip(), validate=True)
    except (binascii.Error, ValueError):
        return {"decode_ok": False}

    try:
        signature_count, offset = _read_solana_shortvec(raw, 0)
        offset += signature_count * 64
        if offset >= len(raw):
            raise ValueError("missing message")

        first_message_byte = raw[offset]
        version = "legacy"
        if first_message_byte & 0x80:
            version = f"v{first_message_byte & 0x7F}"
            offset += 1

        if offset + 3 > len(raw):
            raise ValueError("missing header")
        offset += 3

        account_count, offset = _read_solana_shortvec(raw, offset)
        account_keys = []
        for _ in range(account_count):
            end = offset + 32
            if end > len(raw):
                raise ValueError("account key out of range")
            account_keys.append(_base58_encode_bytes(raw[offset:end]))
            offset = end

        if offset + 32 > len(raw):
            raise ValueError("missing recent blockhash")
        offset += 32

        instruction_count, offset = _read_solana_shortvec(raw, offset)
        program_ids = []
        ata_create_details = []
        system_transfer_details = []
        token_sync_native_details = []
        token_close_account_details = []
        for instruction_index in range(instruction_count):
            if offset >= len(raw):
                raise ValueError("instruction program out of range")
            program_index = raw[offset]
            offset += 1
            account_indexes, offset = _read_solana_instruction_indexes(raw, offset)
            instruction_data_length, offset = _read_solana_shortvec(raw, offset)
            instruction_data_end = offset + instruction_data_length
            if instruction_data_end > len(raw):
                raise ValueError("instruction data out of range")
            instruction_data = raw[offset:instruction_data_end]
            offset = instruction_data_end
            program_id = account_keys[program_index] if program_index < len(account_keys) else f"loaded_address_index:{program_index}"
            program_ids.append(program_id)
            account_pubkeys = [
                account_keys[index] if index < len(account_keys) else f"loaded_address_index:{index}"
                for index in account_indexes
            ]
            if program_id == SOLANA_ASSOCIATED_TOKEN_PROGRAM_ID:
                ata_create_details.append({
                    "instruction_index": instruction_index,
                    "program_id": program_id,
                    "account_indexes": account_indexes,
                    "account_pubkeys": account_pubkeys,
                    "payer": account_pubkeys[0] if len(account_pubkeys) > 0 else None,
                    "ata_account": account_pubkeys[1] if len(account_pubkeys) > 1 else None,
                    "owner": account_pubkeys[2] if len(account_pubkeys) > 2 else None,
                    "mint": account_pubkeys[3] if len(account_pubkeys) > 3 else None,
                })
            if program_id == SOLANA_SYSTEM_PROGRAM_ID and len(instruction_data) >= 12:
                instruction_type = int.from_bytes(instruction_data[:4], "little")
                if instruction_type == 2:
                    system_transfer_details.append({
                        "instruction_index": instruction_index,
                        "program_id": program_id,
                        "source": account_pubkeys[0] if len(account_pubkeys) > 0 else None,
                        "destination": account_pubkeys[1] if len(account_pubkeys) > 1 else None,
                        "lamports": int.from_bytes(instruction_data[4:12], "little"),
                    })
            if program_id == SOLANA_TOKEN_PROGRAM_ID and instruction_data:
                instruction_type = instruction_data[0]
                if instruction_type == 17:
                    token_sync_native_details.append({
                        "instruction_index": instruction_index,
                        "program_id": program_id,
                        "account": account_pubkeys[0] if account_pubkeys else None,
                    })
                elif instruction_type == 9:
                    token_close_account_details.append({
                        "instruction_index": instruction_index,
                        "program_id": program_id,
                        "account": account_pubkeys[0] if len(account_pubkeys) > 0 else None,
                        "destination": account_pubkeys[1] if len(account_pubkeys) > 1 else None,
                        "owner": account_pubkeys[2] if len(account_pubkeys) > 2 else None,
                    })

        unique_program_ids = []
        for program_id in program_ids:
            if program_id not in unique_program_ids:
                unique_program_ids.append(program_id)

        expected_user = (expected_user_public_key or "").strip()
        fee_payer = account_keys[0] if account_keys else None
        wsol_ata_account = None
        for detail in ata_create_details:
            if detail.get("mint") == SOLANA_WRAPPED_SOL_MINT:
                wsol_ata_account = detail.get("ata_account")
                break
        system_transfers_to_wsol = [
            detail for detail in system_transfer_details
            if wsol_ata_account and detail.get("destination") == wsol_ata_account
        ]
        sync_native_for_wsol = [
            detail for detail in token_sync_native_details
            if wsol_ata_account and detail.get("account") == wsol_ata_account
        ]
        uses_wrapped_sol_mint = SOLANA_WRAPPED_SOL_MINT in account_keys
        native_sol_wrap_complete = None
        if uses_wrapped_sol_mint:
            native_sol_wrap_complete = bool(system_transfers_to_wsol and sync_native_for_wsol)
        unresolved_loaded_addresses = [
            detail for detail in ata_create_details
            if any(str(value).startswith("loaded_address_index:") for value in detail.get("account_pubkeys", []))
        ]
        instruction_details = [
            *({"kind": "system_transfer", **detail} for detail in system_transfer_details),
            *({"kind": "token_sync_native", **detail} for detail in token_sync_native_details),
            *({"kind": "token_close_account", **detail} for detail in token_close_account_details),
        ]
        return {
            "decode_ok": True,
            "transaction_version": version,
            "fee_payer": fee_payer,
            "expected_user_public_key": expected_user or None,
            "fee_payer_matches_expected_user": bool(expected_user and fee_payer == expected_user),
            "expected_user_account_present": bool(expected_user and expected_user in account_keys),
            "static_account_count": len(account_keys),
            "instruction_count": len(program_ids),
            "program_ids": unique_program_ids[:16],
            "instruction_program_ids": program_ids[:64],
            "ata_create_count": program_ids.count(SOLANA_ASSOCIATED_TOKEN_PROGRAM_ID),
            "ata_create_details": ata_create_details,
            "token_program_instruction_count": program_ids.count(SOLANA_TOKEN_PROGRAM_ID),
            "system_program_instruction_count": program_ids.count(SOLANA_SYSTEM_PROGRAM_ID),
            "uses_associated_token_program": SOLANA_ASSOCIATED_TOKEN_PROGRAM_ID in program_ids,
            "uses_token_program": SOLANA_TOKEN_PROGRAM_ID in program_ids,
            "uses_system_program": SOLANA_SYSTEM_PROGRAM_ID in program_ids,
            "uses_wrapped_sol_mint": uses_wrapped_sol_mint,
            "wsol_ata_account": wsol_ata_account,
            "has_system_transfer_to_wsol_account": bool(system_transfers_to_wsol),
            "has_token_sync_native": bool(token_sync_native_details),
            "has_token_close_account": bool(token_close_account_details),
            "wsol_wrap_lamports_detected": sum(
                int(detail.get("lamports") or 0) for detail in system_transfers_to_wsol
            ) or None,
            "native_sol_wrap_complete": native_sol_wrap_complete,
            "system_transfer_details": system_transfer_details,
            "token_sync_native_details": token_sync_native_details,
            "token_close_account_details": token_close_account_details,
            "instruction_details": instruction_details[:24],
            "loaded_address_resolution_available": False,
            "loaded_address_resolution_note": (
                "v0 loaded addresses are not decoded by this lightweight parser yet"
                if version != "legacy" and unresolved_loaded_addresses
                else None
            ),
        }
    except (IndexError, ValueError):
        return {"decode_ok": False}


def _safe_swap_preflight_log_line(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.search(
        r"transaction_base64|transactionBase64|signed_transaction|signedTransaction|swapTransaction|https?://|api[-_]?key|access_token|secret",
        text,
        re.IGNORECASE,
    ):
        return ""
    if len(text) > 180:
        text = text[:177] + "..."
    return text


def _safe_swap_preflight_logs_preview(logs) -> list[str]:
    if not isinstance(logs, list):
        return []
    safe = []
    for item in logs:
        line = _safe_swap_preflight_log_line(item)
        if line:
            safe.append(line)
        if len(safe) >= 8:
            break
    return safe


def _safe_swap_preflight_logs_tail(logs, limit: int = 40) -> list[str]:
    if not isinstance(logs, list):
        return []
    safe = []
    for item in logs[-limit:]:
        line = _safe_swap_preflight_log_line(item)
        if line:
            safe.append(line)
    return safe


def _safe_simulation_error_value(value, *, depth: int = 0):
    if depth > 4:
        return str(type(value).__name__)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return _safe_swap_preflight_log_line(value) or None
    if isinstance(value, list):
        return [_safe_simulation_error_value(item, depth=depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            key_text = str(key)
            if re.search(
                r"transaction_base64|transactionBase64|signed_transaction|signedTransaction|swapTransaction|rpc_url|api[-_]?key|access_token|secret",
                key_text,
                re.IGNORECASE,
            ):
                continue
            safe[key_text] = _safe_simulation_error_value(item, depth=depth + 1)
        return safe
    return _safe_swap_preflight_log_line(value) or None


def _simulation_error_summary(err) -> str | None:
    if err in (None, "", False):
        return None
    if isinstance(err, dict) and "InstructionError" in err:
        instruction_error = err.get("InstructionError")
        if isinstance(instruction_error, list) and len(instruction_error) >= 2:
            return f"InstructionError[{instruction_error[0]}]: {instruction_error[1]}"
    summary = json.dumps(_safe_simulation_error_value(err), sort_keys=True)
    if len(summary) > 300:
        summary = summary[:297] + "..."
    return summary


def _failing_instruction_index(err) -> int | None:
    if isinstance(err, dict):
        instruction_error = err.get("InstructionError")
        if isinstance(instruction_error, list) and instruction_error:
            try:
                return int(instruction_error[0])
            except Exception:
                return None
    return None


def _failing_program_id(err, transaction_diagnostics: dict | None) -> str | None:
    index = _failing_instruction_index(err)
    if index is None or not isinstance(transaction_diagnostics, dict):
        return None
    program_ids = transaction_diagnostics.get("instruction_program_ids")
    if isinstance(program_ids, list) and 0 <= index < len(program_ids):
        return program_ids[index]
    return None


def _classify_swap_preflight_error(err, logs, *, provider: str = "", transaction_diagnostics: dict | None = None) -> str:
    text = " ".join([str(err or ""), " ".join(str(x or "") for x in (logs or []))]).lower()
    if any(term in text for term in ("insufficient funds", "insufficient lamports", "not enough", "account balance", "attempt to debit")):
        return "insufficient_funds"
    if any(term in text for term in ("incorrectprogramid", "incorrect program id", "token-2022", "token2022", "token program", "owner mismatch")):
        return "token_program_error"
    failing_program = (_failing_program_id(err, transaction_diagnostics) or "").lower()
    if "custom program error" in text or "custom" in text and "instructionerror" in text:
        if (provider or "").strip().lower() == "meteora-dlmm" or failing_program:
            return "meteora_program_error" if (provider or "").strip().lower() == "meteora-dlmm" else "provider_program_error"
        return "provider_program_error"
    if any(term in text for term in ("rent", "account setup", "associated token", "initializeaccount", "create account", "wrapped sol", "wsol")):
        return "account_setup"
    return "simulation_failed"


def _fetch_solana_simulate_transaction(
    *,
    transaction_base64: str,
    rpc_url: str,
    provider: str = "",
    variant_id: str = "",
    transaction_diagnostics: dict | None = None,
    setup_cost_estimate: dict | None = None,
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "simulateTransaction",
        "params": [
            transaction_base64,
            {
                "encoding": "base64",
                "sigVerify": False,
                "replaceRecentBlockhash": True,
                "commitment": "processed",
            },
        ],
    }

    try:
        response = requests.post(
            rpc_url,
            json=payload,
            timeout=25,
            headers={"accept": "application/json", "content-type": "application/json"},
        )
    except requests.RequestException:
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "rpc_unavailable",
            "message": "Could not preflight this route right now.",
            "logs_preview": [],
            "transaction_diagnostics": transaction_diagnostics or None,
            **(setup_cost_estimate or {}),
        }

    if not response.ok:
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "rpc_unavailable",
            "message": "Could not preflight this route right now.",
            "status_code": response.status_code,
            "logs_preview": [],
            "transaction_diagnostics": transaction_diagnostics or None,
            **(setup_cost_estimate or {}),
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "rpc_unavailable",
            "message": "Preflight returned invalid JSON.",
            "logs_preview": [],
            "transaction_diagnostics": transaction_diagnostics or None,
            **(setup_cost_estimate or {}),
        }

    if not isinstance(data, dict):
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "rpc_unavailable",
            "message": "Preflight returned an unexpected response shape.",
            "logs_preview": [],
            "transaction_diagnostics": transaction_diagnostics or None,
            **(setup_cost_estimate or {}),
        }

    if data.get("error"):
        rpc_error = _safe_submit_rpc_error(data.get("error"))
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": True,
            "error_category": _classify_swap_preflight_error(
                rpc_error,
                [],
                provider=provider,
                transaction_diagnostics=transaction_diagnostics,
            ),
            "message": "Preflight simulation failed.",
            "rpc_error": rpc_error,
            "raw_simulation_error": _safe_simulation_error_value(rpc_error),
            "simulation_error_summary": _simulation_error_summary(rpc_error),
            "logs_preview": [],
            "logs_tail": [],
            "failing_instruction_index": None,
            "failing_program_id": None,
            "units_consumed": None,
            "insufficient_account_candidates": _extract_pubkeys_from_solana_logs(rpc_error),
            "transaction_diagnostics": transaction_diagnostics or None,
            **(setup_cost_estimate or {}),
        }

    value = ((data.get("result") or {}).get("value") or {})
    logs = value.get("logs") or []
    err = value.get("err")
    logs_preview = _safe_swap_preflight_logs_preview(logs)
    logs_tail = _safe_swap_preflight_logs_tail(logs)
    failing_instruction_index = _failing_instruction_index(err)
    failing_program_id = _failing_program_id(err, transaction_diagnostics)
    if err:
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": True,
            "error_category": _classify_swap_preflight_error(
                err,
                logs,
                provider=provider,
                transaction_diagnostics=transaction_diagnostics,
            ),
            "message": "Preflight simulation indicates this transaction may fail.",
            "raw_simulation_error": _safe_simulation_error_value(err),
            "simulation_error_summary": _simulation_error_summary(err),
            "logs_preview": logs_preview,
            "logs_tail": logs_tail,
            "failing_instruction_index": failing_instruction_index,
            "failing_program_id": failing_program_id,
            "units_consumed": value.get("unitsConsumed"),
            "insufficient_account_candidates": _extract_pubkeys_from_solana_logs(err, logs),
            "transaction_diagnostics": transaction_diagnostics or None,
            **(setup_cost_estimate or {}),
        }

    return {
        "ok": True,
        "provider": provider or None,
        "variant_id": variant_id or None,
        "simulation_supported": True,
        "error_category": None,
        "message": "Preflight simulation passed.",
        "logs_preview": logs_preview,
        "logs_tail": logs_tail,
        "units_consumed": value.get("unitsConsumed"),
        "transaction_diagnostics": transaction_diagnostics or None,
        **(setup_cost_estimate or {}),
    }


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


def _jupiter_quote_failure_diagnostic(variant_id: str, error: HTTPException | dict) -> dict:
    if isinstance(error, HTTPException):
        status_code = error.status_code
        detail = error.detail
    else:
        status_code = error.get("status_code")
        detail = error.get("detail")

    detail_text = json.dumps(detail) if isinstance(detail, (dict, list)) else str(detail or "")
    error_code = None
    message = "Jupiter quote failed."

    json_start = detail_text.find("{")
    if json_start >= 0:
        try:
            parsed = json.loads(detail_text[json_start:])
            if isinstance(parsed, dict):
                error_code = parsed.get("errorCode") or parsed.get("code")
                message = parsed.get("error") or parsed.get("message") or message
        except Exception:
            pass

    if not error_code and "NO_ROUTES_FOUND" in detail_text:
        error_code = "NO_ROUTES_FOUND"
        message = "No routes found"

    return {
        "provider": "jupiter-metis",
        "variant_id": variant_id,
        "status_code": status_code,
        "error_code": error_code,
        "message": message,
        "detail": detail,
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
METEORA_DLMM_BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
METEORA_DLMM_SOL_USDC_CANDIDATE = {
    "address": "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
    "name": "SOL-USDC",
    "token_x": METEORA_DLMM_SOL_MINT,
    "token_y": METEORA_DLMM_USDC_MINT,
    "bin_step": 4,
}
METEORA_DLMM_BONK_SOL_CANDIDATE = {
    "address": "6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp",
    "name": "BONK-SOL",
    "token_x": METEORA_DLMM_BONK_MINT,
    "token_y": METEORA_DLMM_SOL_MINT,
}
METEORA_DLMM_DISCOVERY_API_URL = "https://dlmm.datapi.meteora.ag/pools"
METEORA_DLMM_DISCOVERY_MIN_TVL_USD = 1000
METEORA_DLMM_DISCOVERY_MIN_VOLUME_24H_USD = 1

ORCA_WHIRLPOOL_SOL_MINT = "So11111111111111111111111111111111111111112"
ORCA_WHIRLPOOL_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ORCA_WHIRLPOOL_BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
ORCA_WHIRLPOOL_WIF_MINT = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
ORCA_WHIRLPOOL_BONK_SOL_CANDIDATE = {
    "address": "5zpyutJu9ee6jFymDGoK7F6S5Kczqtc9FomP3ueKuyA9",
    "name": "BONK-SOL",
    "token_mint_a": ORCA_WHIRLPOOL_BONK_MINT,
    "token_mint_b": ORCA_WHIRLPOOL_SOL_MINT,
}
ORCA_WHIRLPOOL_WIF_SOL_CANDIDATE = {
    "address": "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1",
    "name": "WIF-SOL",
    "token_mint_a": ORCA_WHIRLPOOL_WIF_MINT,
    "token_mint_b": ORCA_WHIRLPOOL_SOL_MINT,
}
ORCA_WHIRLPOOL_DISCOVERY_API_URL = "https://api.orca.so/v2/solana/pools"
ORCA_WHIRLPOOL_DISCOVERY_MIN_TVL_USDC = 10000
ORCA_WHIRLPOOL_DISCOVERY_MIN_VOLUME_24H_USDC = 1

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
    elif mint_pair == {METEORA_DLMM_SOL_MINT, METEORA_DLMM_BONK_MINT}:
        pool_candidates.append(dict(METEORA_DLMM_BONK_SOL_CANDIDATE))

    return {
        "rpc_url": rpc_url or os.getenv("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com",
        "input_mint": input_mint,
        "output_mint": output_mint,
        "amount_raw": str(amount_raw),
        "slippage_bps": int(slippage_bps),
        "pool_candidates": pool_candidates,
        "discover_pools": len(pool_candidates) == 0,
        "enable_two_hop_discovery": len(pool_candidates) == 0,
        "discovery": {
            "api_url": METEORA_DLMM_DISCOVERY_API_URL,
            "min_tvl_usd": METEORA_DLMM_DISCOVERY_MIN_TVL_USD,
            "min_volume_24h_usd": METEORA_DLMM_DISCOVERY_MIN_VOLUME_24H_USD,
            "sort_by": "tvl:desc",
            "page_size": 20,
        },
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

    if {input_mint, output_mint} == {ORCA_WHIRLPOOL_SOL_MINT, ORCA_WHIRLPOOL_BONK_MINT}:
        payload["pool_candidates"].append(dict(ORCA_WHIRLPOOL_BONK_SOL_CANDIDATE))
    elif {input_mint, output_mint} == {ORCA_WHIRLPOOL_SOL_MINT, ORCA_WHIRLPOOL_WIF_MINT}:
        payload["pool_candidates"].append(dict(ORCA_WHIRLPOOL_WIF_SOL_CANDIDATE))

    payload["discover_pools"] = len(payload["pool_candidates"]) == 0
    payload["enable_two_hop_discovery"] = len(payload["pool_candidates"]) == 0
    payload["discovery"] = {
        "api_url": ORCA_WHIRLPOOL_DISCOVERY_API_URL,
        "min_tvl_usdc": ORCA_WHIRLPOOL_DISCOVERY_MIN_TVL_USDC,
        "min_volume_24h_usdc": ORCA_WHIRLPOOL_DISCOVERY_MIN_VOLUME_24H_USDC,
        "sort_by": "tvl",
        "page_size": 10,
    }

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


PUMPSWAP_SOL_MINT = "So11111111111111111111111111111111111111112"
PUMPSWAP_DOCS_TOKEN_MINT = "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump"
PUMPSWAP_DOCS_POOL_CANDIDATE = {
    "address": "GseMAnNDvntR5uFePZ51yZBXzNSn7GdFPkfHwfr6d77J",
    "name": "official-docs-example",
    "base_mint": PUMPSWAP_DOCS_TOKEN_MINT,
    "quote_mint": PUMPSWAP_SOL_MINT,
}


def _build_pumpswap_quote_payload(
    *,
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    slippage_bps: int = 50,
    rpc_url: str | None = None,
    user_public_key: str | None = None,
) -> dict:
    mint_pair = {input_mint, output_mint}
    supported_pair = mint_pair == {PUMPSWAP_SOL_MINT, PUMPSWAP_DOCS_TOKEN_MINT}
    pool_candidates = [dict(PUMPSWAP_DOCS_POOL_CANDIDATE)] if supported_pair else []
    is_sol_pair = input_mint == PUMPSWAP_SOL_MINT or output_mint == PUMPSWAP_SOL_MINT

    payload = {
        "rpc_url": rpc_url or os.getenv("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com",
        "input_mint": input_mint,
        "output_mint": output_mint,
        "amount_raw": str(amount_raw),
        "slippage_bps": int(slippage_bps),
        "user_public_key": user_public_key,
        "pool_candidates": pool_candidates,
    }

    if not supported_pair and is_sol_pair:
        payload["discover_canonical_pool"] = True
        payload["discovery_mode"] = "canonical_pumpswap_pool"
    elif not supported_pair:
        payload["unsupported_pair"] = True
        payload["unsupported_pair_detail"] = (
            "PumpSwap direct coverage currently supports SOL <-> pump-token canonical pools only; "
            "non-SOL pairs require a composed route that is not implemented yet."
        )
        payload["unsupported_pair_reason"] = "pumpswap_direct_sol_pair_only"

    if not user_public_key:
        payload["skip_reason"] = "wallet_public_key_required_for_pumpswap_quote"

    return payload


def _fetch_pumpswap_quote(payload: dict) -> dict:
    if payload.get("unsupported_pair"):
        raise HTTPException(
            status_code=400,
            detail=payload.get("unsupported_pair_detail") or "Unsupported PumpSwap quote pair",
        )

    if not payload.get("user_public_key"):
        raise HTTPException(status_code=400, detail="PumpSwap quote requires user_public_key")

    helper_path = project_root() / "tools" / "pumpswap_quote_research.mjs"
    if not helper_path.exists():
        raise HTTPException(status_code=502, detail=f"PumpSwap helper missing: {helper_path}")

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
        raise HTTPException(status_code=502, detail=f"PumpSwap helper runtime missing: {e}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="PumpSwap helper timed out")

    stdout = (proc.stdout or "").strip()
    if not stdout:
        stderr = (proc.stderr or "").strip()
        raise HTTPException(
            status_code=502,
            detail=f"PumpSwap helper returned no JSON output: {stderr[-500:]}",
        )

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"PumpSwap helper returned invalid JSON: {e}")

    if proc.returncode != 0 and parsed.get("ok") is not False:
        detail = parsed.get("error") or (proc.stderr or "").strip()
        raise HTTPException(status_code=502, detail=f"PumpSwap helper failed: {detail}")

    return parsed


def _try_fetch_pumpswap_quote(payload: dict) -> dict:
    try:
        data = _fetch_pumpswap_quote(payload)
        if data.get("ok") is True:
            return {"ok": True, "data": data}

        error = data.get("error") if isinstance(data, dict) else None
        return {
            "ok": False,
            "error": {
                "status_code": 502,
                "detail": error.get("message") if isinstance(error, dict) else "PumpSwap quote failed",
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
PHANTOM_BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
PHANTOM_WIF_MINT = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
PHANTOM_POPCAT_MINT = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
PHANTOM_CHAD_MINT = "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump"
PHANTOM_SPX6900_MINT = "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr"


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
        "sell_token_mint": input_mint,
        "buy_token_is_native": output_mint == PHANTOM_SOL_MINT,
        "buy_token_mint": output_mint,
        "amount": str(amount_raw),
        "amount_unit": "base",
        "slippage_bps": int(slippage_bps),
        "taker_address": user_public_key,
    }

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


def _phantom_nested_values(payload, key_names: set[str]):
    found = []
    stack = [payload]
    while stack and len(found) < 20:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                normalized_key = str(key).lower()
                if normalized_key in key_names and value not in (None, ""):
                    found.append(value)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(item[:50])
    return found


def _extract_phantom_actionability_metadata(quote: dict) -> dict:
    quote_response = quote.get("quoteResponse") or {}
    quotes = quote_response.get("quotes") or []
    first_quote = quotes[0] if quotes else {}
    payloads = [quote, quote_response, first_quote]

    transaction_values = []
    route_id_values = []
    quote_id_values = []
    url_values = []
    for payload in payloads:
        transaction_values.extend(_phantom_nested_values(
            payload,
            {
                "transaction",
                "transactionbase64",
                "transaction_base64",
                "base64encodedtx",
                "base64_encoded_tx",
                "swaptransaction",
            },
        ))
        route_id_values.extend(_phantom_nested_values(payload, {"routeid", "route_id"}))
        quote_id_values.extend(_phantom_nested_values(payload, {"quoteid", "quote_id", "id"}))
        url_values.extend(_phantom_nested_values(
            payload,
            {"url", "deeplink", "deep_link", "deeplinkurl", "deeplink_url", "handoffurl", "handoff_url"},
        ))

    return {
        "actionability_status": "benchmark_only",
        "can_build_transaction": False,
        "can_handoff": False,
        "transaction_payload_present": bool(transaction_values),
        "route_id_present": bool(route_id_values),
        "quote_id_present": bool(quote_id_values),
        "handoff_url_present": bool(url_values),
        "reason": "Current Phantom quote response is a benchmark quote only; no safe transaction build or handoff path is wired.",
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
    reference_prices: dict | None = None,
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

    reference_prices = reference_prices or {}
    output_token = option.get("to_token")
    output_price_row = reference_prices.get(output_token) or {}
    output_token_usd_price = _safe_float(output_price_row.get("usd"))
    output_reference_uncertain = (
        output_price_row.get("usd_valuation_reliable") is False
        or (output_price_row.get("pricing_source_detail") or {}).get("external_token_metadata") is True
    )
    estimated_output_usd = (
        quoted_output_amount * output_token_usd_price
        if quoted_output_amount is not None and output_token_usd_price is not None and not output_reference_uncertain
        else None
    )
    execution_cost_amount = _safe_float(trade_cost.get("amount"))
    execution_cost_usd = (
        execution_cost_amount * output_token_usd_price
        if execution_cost_amount is not None and output_token_usd_price is not None and not output_reference_uncertain
        else None
    )

    trade_cost["amount_usd"] = execution_cost_usd
    trade_cost["token_usd_price"] = output_token_usd_price
    trade_cost["pricing_source"] = output_price_row.get("pricing_source")
    trade_cost["usd_reference_uncertain"] = output_reference_uncertain
    option["estimated_output_usd"] = estimated_output_usd
    option["execution_cost_usd"] = execution_cost_usd
    option["usd_reference_uncertain"] = output_reference_uncertain
    option["usd_reference_note"] = (
        "USD estimate unavailable / reference uncertain. External-token market references are comparison-only."
        if output_reference_uncertain
        else None
    )

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
        "execution_status": "executable_capable",
        "supports_current_pair": True,
        "quote_source_type": "venue_trade_api",
        "is_comparison_only": False,
        "is_clickable": True,
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
        "network_fee_detail": "Raydium fee estimation is not available in quote preview.",
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
        "explanation": "Raydium routed quote. Execution prepare is available after Phantom connects.",
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
    helper_route_steps = quote.get("route_steps")
    if isinstance(helper_route_steps, list) and helper_route_steps:
        route_steps = helper_route_steps
    else:
        route_steps = [
            {
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
        ]
    route_shape = quote.get("route_shape") or "single-pool"
    has_pool_address = bool(pool.get("address"))
    has_bin_arrays = isinstance(quote.get("bin_arrays"), list) and bool(quote.get("bin_arrays"))
    single_pool_executable = route_shape == "single-pool" and has_pool_address and has_bin_arrays

    return {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "meteora-dlmm",
        "execution_surface_label": "Meteora",
        "quote_status": "live",
        "execution_status": "executable_capable" if single_pool_executable else "quote_only",
        "supports_current_pair": True,
        "quote_source_type": "venue_native_pool",
        "is_comparison_only": not single_pool_executable,
        "is_clickable": single_pool_executable,
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
        "network_fee_detail": (
            "Meteora DLMM fee estimation is not available in quote preview."
            if single_pool_executable
            else "Meteora DLMM execution is available only for complete single-pool quotes in this preview path."
        ),
        "price_impact_pct": _safe_float(quote.get("price_impact")),
        "slippage_bps": quote.get("slippage_bps"),
        "route_label": "Meteora DLMM",
        "route_labels": ["Meteora DLMM"],
        "route_steps": route_steps,
        "route_step_count": len(route_steps),
        "route_shape": route_shape,
        "protections": {
            "slippage_bps": quote.get("slippage_bps"),
        },
        "explanation": (
            "Meteora DLMM venue-restricted two-hop quote. Execution is not supported for two-hop Meteora routes yet."
            if route_shape == "two-hop"
            else (
                "Meteora DLMM single-pool quote. Execution prepare is available after Phantom connects."
                if single_pool_executable
                else "Meteora DLMM quote is missing pool/bin-array data required for execution prepare."
            )
        ),
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
    helper_route_steps = quote.get("route_steps")
    if isinstance(helper_route_steps, list) and helper_route_steps:
        route_steps = helper_route_steps
    else:
        route_steps = [
            {
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
        ]
    route_shape = quote.get("route_shape") or "single-pool"

    return {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "orca-whirlpool",
        "execution_surface_label": "Orca",
        "quote_status": "live",
        "execution_status": "quote_only" if route_shape == "two-hop" else "executable_capable",
        "supports_current_pair": True,
        "quote_source_type": "venue_native_pool_sdk",
        "is_comparison_only": route_shape == "two-hop",
        "is_clickable": route_shape != "two-hop",
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
        "network_fee_detail": "Orca fee estimation is not available in quote preview.",
        "price_impact_pct": _safe_float(quote.get("price_impact")),
        "slippage_bps": quote.get("slippage_bps"),
        "route_label": "Orca Whirlpool",
        "route_labels": ["Orca"],
        "route_steps": route_steps,
        "route_step_count": len(route_steps),
        "route_shape": route_shape,
        "protections": {
            "slippage_bps": quote.get("slippage_bps"),
        },
        "explanation": (
            "Orca Whirlpool venue-restricted two-hop quote. Execution prepare is not available for two-hop routes yet."
            if route_shape == "two-hop"
            else "Orca Whirlpool single-pool SDK quote. Execution prepare is available after Phantom connects."
        ),
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
        "network_fee_detail": "Phantom routing API is benchmark-only here; no transaction build or handoff path is available yet.",
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
        "actionability": _extract_phantom_actionability_metadata(quote),
        "explanation": "Phantom routing API benchmark quote. Comparison-only; no safe transaction build or handoff path is wired yet.",
        "raw_quote": quote,
        "_sort_out_amount_raw": int(out_amount_raw) if out_amount_raw is not None else -1,
    }


def _extract_pumpswap_route_fees(quote: dict) -> dict:
    return {
        "platform_fee": None,
        "route_fee_items": [],
        "has_explicit_fees": False,
        "note": "PumpSwap helper does not currently expose normalized explicit fee amounts.",
    }


def _normalize_pumpswap_quote_option(
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
    min_out_amount_raw = quote.get("min_out_amount_raw")
    direction = quote.get("direction")
    route_shape = "single-pool"
    is_prepare_supported = (
        variant_id == "pumpswap_quote"
        and direction in {"buy_base_with_quote", "sell_base_for_quote"}
        and bool(pool.get("address"))
        and bool(quote.get("input_mint"))
        and bool(quote.get("output_mint"))
        and out_amount_raw is not None
    )
    route_step = {
        "label": "PumpSwap",
        "pool_address": pool.get("address"),
        "pool_name": pool.get("name"),
        "direction": direction,
        "input_mint": quote.get("input_mint"),
        "output_mint": quote.get("output_mint"),
        "in_amount_raw": quote.get("in_amount_raw"),
        "out_amount_raw": out_amount_raw,
        "base_reserve_raw": quote.get("base_reserve_raw"),
        "quote_reserve_raw": quote.get("quote_reserve_raw"),
    }

    return {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "pumpswap",
        "execution_surface_label": "PumpSwap",
        "quote_status": "live",
        "execution_status": "executable_capable" if is_prepare_supported else "quote_only",
        "supports_current_pair": True,
        "quote_source_type": "venue_native_pool_sdk",
        "is_comparison_only": not is_prepare_supported,
        "is_clickable": is_prepare_supported,
        "is_jupiter_only": False,
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": input_amount,
        "input_amount_raw": str(input_amount_raw),
        "estimated_output": _ui_amount(out_amount_raw, output_decimals),
        "estimated_output_raw": out_amount_raw,
        "min_received": _ui_amount(min_out_amount_raw, output_decimals),
        "min_received_raw": min_out_amount_raw,
        "estimated_total_swap_cost": None,
        "estimated_trade_execution_cost": None,
        "execution_cost": None,
        "cost_scope": "not_computed_yet",
        "cost_transparency": _build_cost_transparency(
            network_fee_scope="unavailable_for_quote_only_preview",
        ),
        "explicit_route_fees": _extract_pumpswap_route_fees(quote),
        "estimated_network_fee": None,
        "network_fee_scope": "not_estimated_in_preview",
        "network_fee_detail": (
            "PumpSwap execution prepare is available after Phantom connects."
            if is_prepare_supported
            else "PumpSwap is quote-only in this preview path."
        ),
        "price_impact_pct": None,
        "slippage_bps": quote.get("slippage_bps"),
        "route_label": "PumpSwap",
        "route_labels": ["PumpSwap"],
        "route_steps": [route_step],
        "route_step_count": 1,
        "route_shape": route_shape,
        "protections": {
            "slippage_bps": quote.get("slippage_bps"),
        },
        "explanation": (
            "PumpSwap single-pool SDK quote. Execution prepare is available after Phantom connects."
            if is_prepare_supported
            else "PumpSwap single-pool SDK quote. Comparison-only for now."
        ),
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


def _is_benchmark_only_provider(provider: str | None) -> bool:
    return (provider or "").strip().lower() in BENCHMARK_ONLY_SWAP_PROVIDERS


def _is_benchmark_only_quote_option(option: dict | None) -> bool:
    if not option:
        return False
    return _is_benchmark_only_provider(option.get("provider"))


def _is_actionable_recommendation_candidate(option: dict | None) -> bool:
    return _is_executable_quote_option(option) and not _is_benchmark_only_quote_option(option)


def _is_direct_route_candidate(option: dict | None) -> bool:
    return bool(option) and not _is_benchmark_only_quote_option(option)


def _select_direct_route_option(options: list[dict]) -> dict | None:
    candidates = [
        opt
        for opt in _dedupe_options(options)
        if opt.get("supports_current_pair") is not False and _is_direct_route_candidate(opt)
    ]
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


def _with_execution_readiness(
    option: dict | None,
    *,
    input_meta: dict | None,
    output_meta: dict | None,
    network: str = "solana",
) -> dict | None:
    if not option:
        return option

    return {
        **option,
        "execution_readiness": build_swap_execution_readiness(
            option,
            from_resolution=input_meta,
            to_resolution=output_meta,
            network=network,
        ),
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


@app.post("/swap/execute/prepare")
def swap_execute_prepare(payload: dict = Body(...)):
    provider_id = payload.get("provider") or ""
    provider = _normalize_execution_provider(provider_id) or provider_id.strip().lower()
    variant_id = (payload.get("variant_id") or "").strip()
    from_token_query = (payload.get("from_token") or "").strip()
    to_token_query = (payload.get("to_token") or "").strip()
    user_public_key = (payload.get("user_public_key") or "").strip()
    network = (payload.get("network") or "solana").strip().lower()

    if not user_public_key:
        return _swap_execution_error(
            "SWAP_EXECUTION_WALLET_REQUIRED",
            "Connect a wallet before preparing a swap transaction.",
        )

    if network != "solana":
        return _swap_execution_error(
            "SWAP_EXECUTION_UNSUPPORTED_NETWORK",
            "Only Solana swap execution is supported for now.",
        )

    if provider not in SUPPORTED_EXECUTION_PROVIDERS:
        return _provider_not_implemented_error(provider)

    try:
        amount = float(payload.get("amount"))
    except Exception:
        return _swap_execution_error(
            "SWAP_EXECUTION_QUOTE_FAILED",
            "Swap amount must be a valid number.",
        )

    if amount <= 0:
        return _swap_execution_error(
            "SWAP_EXECUTION_QUOTE_FAILED",
            "Swap amount must be greater than zero.",
        )

    try:
        slippage_bps = int(payload.get("slippage_bps", 50))
    except Exception:
        return _swap_execution_error(
            "SWAP_EXECUTION_QUOTE_FAILED",
            "Slippage must be a valid basis-point integer.",
        )

    if slippage_bps < 0:
        return _swap_execution_error(
            "SWAP_EXECUTION_QUOTE_FAILED",
            "Slippage cannot be negative.",
        )

    input_meta = _resolve_swap_token_for_quote(from_token_query)
    output_meta = _resolve_swap_token_for_quote(to_token_query)
    if not input_meta or input_meta.get("resolution_error"):
        return _swap_execution_error(
            "SWAP_EXECUTION_QUOTE_FAILED",
            "Could not resolve input token metadata for swap execution.",
            side="from",
            detail=(input_meta or {}).get("resolution_error"),
        )
    if not output_meta or output_meta.get("resolution_error"):
        return _swap_execution_error(
            "SWAP_EXECUTION_QUOTE_FAILED",
            "Could not resolve output token metadata for swap execution.",
            side="to",
            detail=(output_meta or {}).get("resolution_error"),
        )
    if input_meta["mint"] == output_meta["mint"]:
        return _swap_execution_error(
            "SWAP_EXECUTION_QUOTE_FAILED",
            "Input and output tokens must be different.",
        )

    try:
        amount_raw = to_raw_amount(amount, input_meta["decimals"])
    except HTTPException as e:
        return _swap_execution_error(
            "SWAP_EXECUTION_QUOTE_FAILED",
            "Swap amount is too small after token decimal conversion.",
            detail=e.detail,
        )

    return prepare_swap_transaction_with_provider(
        provider_id=provider,
        input_meta=input_meta,
        output_meta=output_meta,
        amount=amount,
        amount_raw=amount_raw,
        slippage_bps=slippage_bps,
        variant_id=variant_id,
        user_public_key=user_public_key,
        from_token_query=from_token_query,
        to_token_query=to_token_query,
    )


@app.post("/swap/execute/preflight")
def swap_execute_preflight(payload: dict = Body(...)):
    network = (payload.get("network") or "solana").strip().lower()
    provider = (payload.get("provider") or "").strip()
    variant_id = (payload.get("variant_id") or "").strip()
    transaction_base64 = (payload.get("transaction_base64") or "").strip()
    user_public_key = (payload.get("user_public_key") or "").strip()

    if network != "solana":
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "unsupported",
            "message": "Only Solana swap preflight is supported right now.",
            "logs_preview": [],
        }

    if not transaction_base64:
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "unsupported",
            "message": "Prepared transaction is required for preflight.",
            "logs_preview": [],
        }

    if len(transaction_base64) > MAX_SWAP_PREFLIGHT_TRANSACTION_BASE64_CHARS:
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "unsupported",
            "message": "Prepared transaction payload is too large.",
            "logs_preview": [],
        }

    try:
        base64.b64decode(transaction_base64, validate=True)
    except (binascii.Error, ValueError):
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "unsupported",
            "message": "Prepared transaction must be valid base64.",
            "logs_preview": [],
        }

    transaction_diagnostics = _decode_solana_transaction_diagnostics(
        transaction_base64,
        expected_user_public_key=user_public_key,
    )

    rpc_url, _rpc_source = _configured_swap_prepare_rpc_url()
    if not rpc_url:
        return {
            "ok": False,
            "provider": provider or None,
            "variant_id": variant_id or None,
            "simulation_supported": False,
            "error_category": "rpc_unavailable",
            "message": "Could not preflight this route right now.",
            "logs_preview": [],
            "transaction_diagnostics": transaction_diagnostics,
        }

    setup_cost_estimate = _build_swap_setup_cost_estimate(transaction_diagnostics, rpc_url)

    return _fetch_solana_simulate_transaction(
        transaction_base64=transaction_base64,
        rpc_url=rpc_url,
        provider=provider,
        variant_id=variant_id,
        transaction_diagnostics=transaction_diagnostics,
        setup_cost_estimate=setup_cost_estimate,
    )


@app.post("/swap/execute/submit")
def swap_execute_submit(payload: dict = Body(...)):
    network = (payload.get("network") or "solana").strip().lower()
    signed_transaction_base64 = (payload.get("signed_transaction_base64") or "").strip()
    skip_preflight = bool(payload.get("skip_preflight", False))
    preflight_commitment = (payload.get("preflight_commitment") or "confirmed").strip() or "confirmed"

    if network != "solana":
        return _swap_submit_error(
            "SWAP_SUBMIT_UNSUPPORTED_NETWORK",
            "Only Solana signed transaction submission is supported for now.",
        )

    if not signed_transaction_base64:
        return _swap_submit_error(
            "SWAP_SUBMIT_SIGNED_TRANSACTION_REQUIRED",
            "Signed transaction is required for submission.",
        )

    if len(signed_transaction_base64) > MAX_SIGNED_SWAP_TRANSACTION_BASE64_CHARS:
        return _swap_submit_error(
            "SWAP_SUBMIT_FAILED",
            "Signed transaction payload is too large.",
        )

    try:
        base64.b64decode(signed_transaction_base64, validate=True)
    except (binascii.Error, ValueError):
        return _swap_submit_error(
            "SWAP_SUBMIT_FAILED",
            "Signed transaction must be valid base64.",
        )

    rpc_url, rpc_source = _configured_swap_submit_rpc_url()
    if not rpc_url:
        return _swap_submit_error(
            "SWAP_SUBMIT_RPC_CONFIG_MISSING",
            "Set SWAP_SUBMIT_RPC_URL, SOLANA_RPC_URL, SOLANA_MAINNET_RPC_URL, or HELIUS_RPC_URL to submit swaps.",
        )

    result = _fetch_solana_send_transaction(
        signed_transaction_base64=signed_transaction_base64,
        rpc_url=rpc_url,
        skip_preflight=skip_preflight,
        preflight_commitment=preflight_commitment,
    )
    if result.get("ok") is not True:
        return result

    return {
        "ok": True,
        "signature": result.get("signature"),
        "status": "submitted",
        "rpc": {
            "source": rpc_source,
            "url_configured": True,
        },
    }


@app.get("/swap/quote")
def swap_quote(
    from_token: str,
    to_token: str,
    amount: float,
    network: str = "solana",
    user_public_key: str | None = None,
):
    from_token_query = (from_token or "").strip()
    to_token_query = (to_token or "").strip()

    if network != "solana":
        raise HTTPException(status_code=400, detail="only solana is supported for now")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    if from_token_query == to_token_query:
        raise HTTPException(status_code=400, detail="from_token and to_token must be different")

    input_meta = _resolve_swap_token_for_quote(from_token_query)
    output_meta = _resolve_swap_token_for_quote(to_token_query)
    if not input_meta or input_meta.get("resolution_error"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TOKEN_RESOLUTION_FAILED",
                "side": "from",
                "query": from_token_query,
                "error": (input_meta or {}).get("resolution_error"),
            },
        )
    if not output_meta or output_meta.get("resolution_error"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TOKEN_RESOLUTION_FAILED",
                "side": "to",
                "query": to_token_query,
                "error": (output_meta or {}).get("resolution_error"),
            },
        )
    if input_meta["mint"] == output_meta["mint"]:
        raise HTTPException(status_code=400, detail="from_token and to_token must be different")

    from_token = input_meta.get("quote_label") or input_meta.get("symbol") or from_token_query
    to_token = output_meta.get("quote_label") or output_meta.get("symbol") or to_token_query
    external_tokens = [
        item
        for item in (
            _external_token_response_meta("from", input_meta),
            _external_token_response_meta("to", output_meta),
        )
        if item
    ]

    raw_amount = to_raw_amount(amount, input_meta["decimals"])

    base_params = {
        "inputMint": input_meta["mint"],
        "outputMint": output_meta["mint"],
        "amount": str(raw_amount),
        "slippageBps": "50",
        "restrictIntermediateTokens": "true",
        "instructionVersion": "V2",
    }

    diagnostics = []
    variant_candidates = []
    external_other_options = []

    # 1) Recommended/default Jupiter quote. A Jupiter no-route response is a
    # provider miss for this preview, not a reason to skip the rest of the
    # quote universe.
    recommended_raw = None
    recommended = None
    try:
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
    except HTTPException as e:
        diagnostics.append(_jupiter_quote_failure_diagnostic("recommended_default", e))

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
        diagnostics.append(_jupiter_quote_failure_diagnostic("broader_search", broader_result["error"]))

    # 3) Force an alternate venue mix by excluding DEX labels from the recommended route
    recommended_labels = recommended.get("route_labels") if recommended else []
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
                _jupiter_quote_failure_diagnostic(
                    "exclude_recommended_dexes",
                    exclude_result["error"],
                )
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
        diagnostics.append(_jupiter_quote_failure_diagnostic("direct_route_check", direct_result["error"]))

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

    pumpswap_payload = _build_pumpswap_quote_payload(
        input_mint=input_meta["mint"],
        output_mint=output_meta["mint"],
        amount_raw=raw_amount,
        slippage_bps=50,
        rpc_url=SOLANA_MAINNET_RPC_URL,
        user_public_key=user_public_key,
    )
    pumpswap_result = _try_fetch_pumpswap_quote(pumpswap_payload)
    if pumpswap_result["ok"]:
        external_other_options.append(
            _normalize_pumpswap_quote_option(
                variant_id="pumpswap_quote",
                label="Via PumpSwap",
                kind="alternative",
                quote=pumpswap_result["data"],
                from_token=from_token,
                to_token=to_token,
                input_amount=amount,
                input_amount_raw=raw_amount,
                output_decimals=output_meta["decimals"],
            )
        )
    else:
        diagnostics.append({"variant_id": "pumpswap_quote", **pumpswap_result["error"]})

    # Build the ranked Jupiter candidate pool from all successful checked variants.
    # This remains the executable universe for now.
    ranked_jupiter_candidates = [opt for opt in [recommended, *variant_candidates] if opt]
    if direct_route_check:
        ranked_jupiter_candidates.append(direct_route_check)

    ranked_jupiter_candidates = _rank_quote_options(ranked_jupiter_candidates)

    # Rank every normalized universe we can honestly compare. External DEX helpers
    # can win best quote, but they stay comparison-only until execution paths exist.
    ranked_universe_options = _rank_quote_options(
        [*ranked_jupiter_candidates, *external_other_options]
    )
    direct_route_base = _select_direct_route_option(ranked_universe_options)

    try:
        reference_prices = _resolve_quote_reference_prices_usd([from_token, to_token, "SOL"])
    except Exception:
        reference_prices = {}
    reference_prices = _apply_external_token_reference_prices(
        reference_prices,
        {
            from_token: input_meta,
            to_token: output_meta,
        },
    )

    if not ranked_universe_options:
        inline_baseline, inline_baseline_vs_recommended = _build_fresh_quote_reference_baseline(
            from_token=from_token,
            to_token=to_token,
            amount=amount,
            fallback_input_usd_value=None,
            best_output_amount=None,
            reference_prices=reference_prices,
        )
        return {
            "ok": False,
            "no_route": True,
            "network": network,
            "provider": None,
            "from_token": from_token,
            "to_token": to_token,
            "input_amount": amount,
            "input_amount_raw": raw_amount,
            "inline_baseline": inline_baseline,
            "inline_baseline_vs_recommended": inline_baseline_vs_recommended,
            "best_quote_option": None,
            "best_benchmark_quote_option": None,
            "recommended_option": None,
            "recommended_executable_option": None,
            "recommended": None,
            "other_options": [],
            "direct_route_check": None,
            "message": "No executable route found for this token/amount.",
            "user_message": "Reference price is available, but no live route was found.",
            "summary": {
                "selection_basis": "no_live_route_returned",
                "headline_label": "No executable route found",
                "recommended_reason": "Reference pricing is not an executable route.",
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
                    "pumpswap_quote",
                ],
                "uses_external_tokens": bool(external_tokens),
            },
            "external_tokens": external_tokens,
            "debug": {
                "route_debug": None,
                "ranked_jupiter_variants": [],
                "variant_errors": diagnostics,
                "external_tokens": external_tokens,
                "notes": [
                    "Reference pricing is not an executable route.",
                    "No checked provider returned a usable live swap route for this request.",
                ],
            },
        }

    best_quote_base = ranked_universe_options[0]
    best_benchmark_quote_base = next(
        (opt for opt in ranked_universe_options if _is_benchmark_only_quote_option(opt)),
        None,
    )
    best_quote_variant_id = best_quote_base.get("variant_id")
    best_quote_option = _with_quote_role(
        best_quote_base,
        kind="benchmark" if _is_benchmark_only_quote_option(best_quote_base) else "recommended",
        label="Best benchmark quote" if _is_benchmark_only_quote_option(best_quote_base) else "Best quote",
    )

    executable_candidates = [
        opt for opt in ranked_universe_options if _is_actionable_recommendation_candidate(opt)
    ]
    recommended_executable_base = executable_candidates[0] if executable_candidates else None
    recommended_executable_variant_id = (
        recommended_executable_base.get("variant_id") if recommended_executable_base else None
    )
    recommended_executable_option = _with_quote_role(
        recommended_executable_base,
        kind="recommended",
        label=(
            "Recommended executable route"
            if not _same_quote_option(recommended_executable_base, best_quote_base)
            else "Recommended executable route"
        ),
    )
    recommended_base = recommended_executable_base or next(
        (opt for opt in ranked_universe_options if not _is_benchmark_only_quote_option(opt)),
        best_quote_base,
    )

    # Other options = meaningful remaining normalized universe options. Prefer
    # execution surfaces not already represented by the visible best quote or
    # selected executable recommendation, so internal Jupiter variants do not
    # crowd out Raydium.
    ranked_other_options = []
    diverse_other_options = _select_diverse_other_options(
        ranked_universe_options,
        best_quote=best_quote_base if _is_actionable_recommendation_candidate(best_quote_base) else None,
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
            alt_label = "Benchmark-only quote"
        elif variant_id == "pumpswap_quote":
            alt_label = "Via PumpSwap"
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
        "raydium_quote": "Raydium produced the best checked quote for this request and can be prepared for Phantom signing.",
        "meteora_dlmm_quote": "Meteora DLMM produced the best checked quote for this request and can be prepared for Phantom signing when the route is single-pool.",
        "orca_whirlpool_quote": "Orca Whirlpool produced the best checked quote for this request and can be prepared for Phantom signing when the route is single-pool.",
        "phoenix_quote": "Phoenix CLOB produced the best checked quote for this request, but it is comparison-only in this preview path.",
        "phantom_quote": "Phantom routing API produced the best checked benchmark quote, but the recommended route is the best executable route available in this app.",
        "pumpswap_quote": "PumpSwap produced the best checked quote for this request, but it is comparison-only in this preview path.",
    }.get(
        best_quote_variant_id,
        "The best quote had the strongest checked output among the currently available variants."
    )

    best_output_amount = _safe_float(best_quote_option.get("estimated_output"))
    inline_baseline, inline_baseline_vs_recommended = _build_fresh_quote_reference_baseline(
        from_token=from_token,
        to_token=to_token,
        amount=amount,
        fallback_input_usd_value=_safe_float((recommended_raw or {}).get("swapUsdValue")),
        best_output_amount=best_output_amount,
        reference_prices=reference_prices,
    )

    reference_output_amount = _safe_float((inline_baseline or {}).get("ideal_output_amount"))

    best_quote_option = _attach_cost_fields(
        best_quote_option,
        reference_output_amount,
        reference_prices=reference_prices,
    )
    recommended_executable_option = _attach_cost_fields(
        recommended_executable_option,
        reference_output_amount,
        reference_prices=reference_prices,
    )
    ranked_other_options = [
        _attach_cost_fields(opt, reference_output_amount, reference_prices=reference_prices)
        for opt in ranked_other_options
    ] 
    direct_route_output = _attach_cost_fields(
        direct_route_output,
        reference_output_amount,
        reference_prices=reference_prices,
    )

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
    ranked_other_options = [_strip_internal_sort_key(x) for x in ranked_other_options]
    direct_route_output = _strip_internal_sort_key(direct_route_output)

    best_quote_option = _with_execution_readiness(
        best_quote_option,
        input_meta=input_meta,
        output_meta=output_meta,
        network=network,
    )
    if _same_quote_option(recommended_executable_option, best_quote_option):
        recommended_executable_option = best_quote_option
    else:
        recommended_executable_option = _with_execution_readiness(
            recommended_executable_option,
            input_meta=input_meta,
            output_meta=output_meta,
            network=network,
        )
    recommended_option = recommended_executable_option or _with_execution_readiness(
        _strip_internal_sort_key(_with_quote_role(
            recommended_base,
            kind="recommended",
            label="Recommended route",
        )),
        input_meta=input_meta,
        output_meta=output_meta,
        network=network,
    )
    ranked_other_options = [
        _with_execution_readiness(
            opt,
            input_meta=input_meta,
            output_meta=output_meta,
            network=network,
        )
        for opt in ranked_other_options
    ]
    direct_route_output = _with_execution_readiness(
        direct_route_output,
        input_meta=input_meta,
        output_meta=output_meta,
        network=network,
    )

    return {
        "ok": True,
        "network": network,
        "provider": recommended_option.get("provider") or best_quote_option.get("provider") or "jupiter-metis",
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": amount,
        "inline_baseline": inline_baseline,
        "inline_baseline_vs_recommended": inline_baseline_vs_recommended,
        "input_amount_raw": raw_amount,
        "best_quote_option": best_quote_option,
        "best_benchmark_quote_option": (
            _strip_internal_sort_key(_with_quote_role(
                best_benchmark_quote_base,
                kind="benchmark",
                label="Best benchmark quote",
            ))
            if best_benchmark_quote_base
            else None
        ),
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
            "recommended_variant_id": recommended_option.get("variant_id") if recommended_option else None,
            "recommended_executable_variant_id": recommended_executable_variant_id,
            "best_benchmark_variant_id": (
                best_benchmark_quote_base.get("variant_id") if best_benchmark_quote_base else None
            ),
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
                "pumpswap_quote",
            ],
            "available_other_options": len(ranked_other_options),
            "alternatives_show_all_remaining_universes": True,
            "direct_route_available": direct_route_output is not None,
            "ranking_basis": "highest_receive_amount",
            "direct_route_selection_basis": "simplest_meaningful_candidate_across_live_quote_universes",
            "cost_model_scope": "partial_transparency_not_ranking_input",
            "recommendation_scope": "highest_receive_amount_across_live_quote_universes",
            "execution_availability_scope": "separate_from_recommendation",
            "uses_external_tokens": bool(external_tokens),
        },
        "external_tokens": external_tokens,
        "debug": {
            "route_debug": (recommended_raw or {}).get("mostReliableAmmsQuoteReport"),
            "ranked_jupiter_variants": ranked_jupiter_variant_debug,
            "variant_errors": diagnostics,
            "external_tokens": external_tokens,
            "notes": [
                "Recommended is selected by highest receive amount across live quote universes, not by estimated total swap cost.",
                "Execution availability is separate from recommendation. Quote-only routes are not clickable yet.",
                "Direct/simple route is selected across available live quote universes. The Jupiter direct-route quote remains one candidate in that model.",
                "Benchmark gap is a reference comparison, not a fee. Explicit route fees are provider-disclosed fee evidence and may already be reflected in quoted output.",
                "Phantom uses the official Phantom routing API quote surface. It is quote-only and non-clickable in this preview path.",
                "Meteora, Orca, PumpSwap, and Phoenix use standalone SDK helpers. Meteora execution is limited to complete single-pool DLMM routes; Phoenix remains quote-only.",
                "PumpSwap uses a standalone SDK helper only for direct SOL <-> pump-token paths.",
            ],
        },
    }




@app.get("/swap/inline-baseline")
def swap_inline_baseline(from_token: str, to_token: str, amount: float, network: str = "solana"):
    raw_from_token = (from_token or "").strip()
    raw_to_token = (to_token or "").strip()

    if network != "solana":
        raise HTTPException(status_code=400, detail="only solana is supported for now")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than 0")

    if raw_from_token.lower() == raw_to_token.lower():
        raise HTTPException(status_code=400, detail="from_token and to_token must be different")

    input_meta = _resolve_swap_token_for_quote(raw_from_token)
    output_meta = _resolve_swap_token_for_quote(raw_to_token)
    if (
        not input_meta
        or not output_meta
        or input_meta.get("resolution_error")
        or output_meta.get("resolution_error")
    ):
        raise HTTPException(status_code=400, detail="unsupported token for now")

    input_label = (input_meta.get("quote_label") or input_meta.get("symbol") or raw_from_token).strip()
    output_label = (output_meta.get("quote_label") or output_meta.get("symbol") or raw_to_token).strip()
    reference_prices = _resolve_quote_reference_prices_usd([input_label, output_label, "SOL"])
    reference_prices = _apply_external_token_reference_prices(
        reference_prices,
        {
            input_label: input_meta,
            output_label: output_meta,
        },
    )
    inline_baseline, _ = _build_fresh_quote_reference_baseline(
        from_token=input_label,
        to_token=output_label,
        amount=amount,
        fallback_input_usd_value=None,
        best_output_amount=None,
        reference_prices=reference_prices,
    )

    return {
        "ok": True,
        "network": network,
        "from_token": input_label,
        "to_token": output_label,
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
        assets_list = [
            item
            for item in (_normalize_refresh_asset_for_diagnostics(a) for a in requested_assets)
            if item
        ]
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
        include_unpriced=bool(assets) or show_unpriced,  # explicit asset requests need balance rows for swap controls
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
    assets: str | None = Query(None, description="Comma-separated asset keys to refresh, e.g. sol,usdc,spl:<mint>"),
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

        account_config = accounts_map.get(name) or {}
        if assets:
            assets_list = [a.strip() for a in assets.split(",") if a.strip()]
        else:
            assets_list = account_config.get("default_assets") or account_config.get("assets") or []
        normalized_assets = [
            item
            for item in (_normalize_refresh_asset_for_diagnostics(a) for a in assets_list)
            if item
        ]

        cmd = [
            sys.executable, "run_balances_to_db.py",
            "--source", "solana",
            "--address", addr,
            "--account", name,
            "--no-report",
        ]
        if assets_list:
            cmd.extend(["--assets", *assets_list])
        r = _run_cmd(cmd)
        latest_balances = db.get_latest_balances(account=name, assets=normalized_assets) if normalized_assets else {}
        refreshed.append({
            "account": name,
            "requested_assets": assets_list,
            "normalized_requested_assets": normalized_assets,
            "balance_keys_written": sorted(latest_balances.keys()),
            "latest_balances": latest_balances,
            **r,
        })

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
