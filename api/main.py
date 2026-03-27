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


def _fetch_jupiter_quote(params: dict) -> dict:
    url = "https://lite-api.jup.ag/swap/v1/quote?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
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

    option = {
        "variant_id": variant_id,
        "label": label,
        "kind": kind,
        "provider": "jupiter-metis",
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
        "execution_cost": None,
        "cost_scope": "not_computed_yet",
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


def _dedupe_options(options: list[dict]) -> list[dict]:
    out = []
    seen = set()

    for opt in options:
        if not opt:
            continue

        key = (
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

    # Build the ranked candidate pool from all successful checked variants
    ranked_candidates = [recommended, *variant_candidates]
    if direct_route_check:
        ranked_candidates.append(direct_route_check)

    ranked_candidates = _dedupe_options(ranked_candidates)
    ranked_candidates.sort(key=lambda x: x.get("_sort_out_amount_raw", -1), reverse=True)

    # Best checked option becomes the true recommended option
    best_option = ranked_candidates[0] if ranked_candidates else recommended

    best_variant_id = best_option.get("variant_id")
    best_option = {
        **best_option,
        "kind": "recommended",
        "label": "Recommended",
    }

    # Other options = next best checked variants, excluding the best one
    ranked_other_options = []
    for opt in ranked_candidates[1:]:
        if opt.get("variant_id") == "direct_route_check":
            continue

        variant_id = opt.get("variant_id")
        alt_label = opt.get("label") or "Alternative"

        if variant_id == "recommended_default":
            alt_label = "Default Jupiter route"
        elif variant_id == "exclude_recommended_dexes":
            alt_label = "Alternate venue mix"
        elif variant_id == "broader_search":
            alt_label = "Broader search"

        ranked_other_options.append({
            **opt,
            "kind": "alternative",
            "label": alt_label,
        })

    ranked_other_options = ranked_other_options[:2]

    # Keep direct route available as its own block too
    direct_route_output = None
    if direct_route_check:
        direct_route_output = {
            **direct_route_check,
            "kind": "direct",
            "label": "Direct route check",
        }

    best_option = _strip_internal_sort_key(best_option)
    ranked_other_options = [_strip_internal_sort_key(x) for x in ranked_other_options]
    direct_route_output = _strip_internal_sort_key(direct_route_output)

    recommended_reason = {
        "recommended_default": "The default Jupiter quote had the best checked output for this request.",
        "exclude_recommended_dexes": "An alternate venue mix produced the best checked output for this request.",
        "direct_route_check": "The direct-route-only check produced the best checked output for this request.",
        "broader_search": "A broader routing search produced the best checked output for this request.",
    }.get(
        best_variant_id,
        "The recommended option had the strongest checked output among the currently available variants."
    )

    best_output_amount = _safe_float(best_option.get("estimated_output"))

    inline_baseline, inline_baseline_vs_recommended = _build_inline_baseline(
        from_token=from_token,
        to_token=to_token,
        amount=amount,
        fallback_input_usd_value=_safe_float(recommended_raw.get("swapUsdValue")),
        best_output_amount=best_output_amount,
    )




    return {
        "ok": True,
        "network": network,
        "provider": "jupiter-metis",
        "from_token": from_token,
        "to_token": to_token,
        "input_amount": amount,
        "inline_baseline": inline_baseline,
        "inline_baseline_vs_recommended": inline_baseline_vs_recommended,
        "input_amount_raw": raw_amount,
        "recommended": best_option,
        "other_options": ranked_other_options,
        "direct_route_check": direct_route_output,
        "summary": {
            "selection_basis": "highest_output_amount_among_checked_variants",
            "headline_label": "Estimated total swap cost",
            "cost_scope": "not_computed_yet",
            "recommended_reason": recommended_reason,
            "checked_variants": [
                "recommended_default",
                "broader_search",
                "exclude_recommended_dexes",
                "direct_route_check",
            ],
            "available_other_options": len(ranked_other_options),
            "direct_route_available": direct_route_output is not None,
        },
        "debug": {
            "route_debug": recommended_raw.get("mostReliableAmmsQuoteReport"),
            "variant_errors": diagnostics,
            "notes": [
                "This is a Jupiter-first comparison surface, not a full multi-provider ranking engine yet.",
                "Estimated total swap cost is not computed yet in this backend version.",
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

    if from_token not in TOKEN_META or to_token not in TOKEN_META:
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
