from __future__ import annotations

from decimal import Decimal, InvalidOperation
import os
from typing import Any
from urllib.parse import quote

import requests


DEFAULT_SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
DEFAULT_TIMEOUT_SECONDS = 10
WARNINGS = [
    "token_accounts_are_not_wallet_clusters",
    "concentration_is_not_safety_score",
    "solana_rpc_top_accounts_only",
]


def _configured_rpc_url() -> tuple[str, dict[str, Any]]:
    env_priority = (
        "TOKEN_HOLDER_CONCENTRATION_RPC_URL",
        "SOLANA_RPC_URL",
        "SOLANA_MAINNET_RPC_URL",
        "HELIUS_RPC_URL",
    )
    for name in env_priority:
        value = (os.getenv(name) or "").strip()
        if value:
            return value, {"source": name, "url_configured": True}

    return DEFAULT_SOLANA_RPC_URL, {
        "source": "public_solana_rpc",
        "url_configured": False,
    }


def _resolve_rpc_url(rpc_url: str | None) -> tuple[str, dict[str, Any]]:
    explicit = (rpc_url or "").strip()
    if explicit:
        return explicit, {"source": "explicit", "url_configured": True}
    return _configured_rpc_url()


def build_bubblemaps_url(mint: str) -> str:
    return f"https://v2.bubblemaps.io/map?address={quote((mint or '').strip())}&chain=solana"


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            **extra,
        },
    }


def _is_rate_limited(value: Any) -> bool:
    text = str(value or "").lower()
    return "too many requests" in text or "rate limit" in text or "rate-limited" in text


def _rate_limited_error(method: str, mint: str, **extra: Any) -> dict[str, Any]:
    return _error(
        "TOKEN_HOLDER_CONCENTRATION_RATE_LIMITED",
        "Solana RPC is rate-limited right now.",
        provider="solana_rpc",
        mint=mint,
        method=method,
        **extra,
    )


def _with_known_mint_context(
    result: dict[str, Any],
    mint: str,
    rpc_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if result.get("ok") is False and mint:
        result.setdefault("links", {})
        result["links"].setdefault("bubblemaps", build_bubblemaps_url(mint))
        result.setdefault("warnings", list(WARNINGS))
        if rpc_meta:
            result.setdefault("rpc", dict(rpc_meta))
    return result


def _decimal_from_value(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if decimal < 0:
        return None
    return decimal


def _rpc_post(
    url: str,
    method: str,
    params: list[Any],
    *,
    timeout: int,
    mint: str,
    lookup_error_code: str,
) -> dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        return _error(
            lookup_error_code,
            "Solana RPC token holder concentration lookup failed.",
            provider="solana_rpc",
            mint=mint,
            method=method,
            detail=str(exc),
        )

    if response.status_code == 429:
        return _rate_limited_error(
            method,
            mint,
            status_code=response.status_code,
            detail=(response.text or "")[:500],
        )

    if not response.ok:
        return _error(
            "TOKEN_HOLDER_CONCENTRATION_HTTP_ERROR",
            "Solana RPC token holder concentration lookup returned an HTTP error.",
            provider="solana_rpc",
            mint=mint,
            method=method,
            status_code=response.status_code,
            detail=(response.text or "")[:500],
        )

    try:
        data = response.json()
    except ValueError as exc:
        return _error(
            "TOKEN_HOLDER_CONCENTRATION_INVALID_JSON",
            "Solana RPC token holder concentration lookup returned invalid JSON.",
            provider="solana_rpc",
            mint=mint,
            method=method,
            detail=str(exc),
        )

    if not isinstance(data, dict):
        return _error(
            "TOKEN_HOLDER_CONCENTRATION_INVALID_JSON",
            "Solana RPC token holder concentration lookup returned an unexpected response shape.",
            provider="solana_rpc",
            mint=mint,
            method=method,
        )

    if data.get("error"):
        if _is_rate_limited(data.get("error")):
            return _rate_limited_error(
                method,
                mint,
                status_code=429,
                rpc_error=data.get("error"),
            )
        return _error(
            lookup_error_code,
            "Solana RPC token holder concentration lookup returned an RPC error.",
            provider="solana_rpc",
            mint=mint,
            method=method,
            rpc_error=data.get("error"),
        )

    return {"ok": True, "data": data}


def _percent(part: Decimal, whole: Decimal) -> float | None:
    if whole <= 0:
        return None
    return float((part / whole) * Decimal("100"))


def _rounded_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def _sum_top(accounts: list[dict[str, Any]], count: int) -> Decimal:
    total = Decimal("0")
    for account in accounts[:count]:
        amount = _decimal_from_value(account.get("amount"))
        if amount is not None:
            total += amount
    return total


def _concentration_level(top_account_pct: float | None, top_10_accounts_pct: float | None) -> str:
    if top_account_pct is None or top_10_accounts_pct is None:
        return "unknown"
    if top_account_pct >= 5 or top_10_accounts_pct >= 50:
        return "high"
    if top_account_pct >= 3 or top_10_accounts_pct >= 30:
        return "medium"
    return "low"


def _top_account_severity(top_account_pct: float | None) -> str:
    if top_account_pct is None:
        return "info"
    if top_account_pct >= 5:
        return "caution"
    if top_account_pct >= 3:
        return "notice"
    return "info"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "unknown"
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{text}%"


def fetch_token_holder_concentration(
    mint: str,
    rpc_url: str | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    mint = (mint or "").strip()
    if not mint:
        return _error(
            "TOKEN_MINT_REQUIRED",
            "Token mint is required.",
        )

    url, rpc_meta = _resolve_rpc_url(rpc_url)
    supply_result = _rpc_post(
        url,
        "getTokenSupply",
        [mint, {"commitment": "confirmed"}],
        timeout=timeout,
        mint=mint,
        lookup_error_code="TOKEN_SUPPLY_LOOKUP_FAILED",
    )
    if not supply_result.get("ok"):
        return _with_known_mint_context(supply_result, mint, rpc_meta)

    supply_value = (
        ((supply_result.get("data") or {}).get("result") or {}).get("value")
        if isinstance(supply_result.get("data"), dict)
        else None
    )
    supply_amount = _decimal_from_value(
        (supply_value or {}).get("amount") if isinstance(supply_value, dict) else None
    )
    if supply_amount is None or supply_amount <= 0:
        return _with_known_mint_context(
            _error(
                "TOKEN_SUPPLY_NOT_FOUND",
                "Solana RPC did not return a usable token supply.",
                provider="solana_rpc",
                mint=mint,
            ),
            mint,
            rpc_meta,
        )

    accounts_result = _rpc_post(
        url,
        "getTokenLargestAccounts",
        [mint, {"commitment": "confirmed"}],
        timeout=timeout,
        mint=mint,
        lookup_error_code="TOKEN_LARGEST_ACCOUNTS_LOOKUP_FAILED",
    )
    if not accounts_result.get("ok"):
        return _with_known_mint_context(accounts_result, mint, rpc_meta)

    account_values = (
        ((accounts_result.get("data") or {}).get("result") or {}).get("value")
        if isinstance(accounts_result.get("data"), dict)
        else None
    )
    if not isinstance(account_values, list) or not account_values:
        return _with_known_mint_context(
            _error(
                "TOKEN_LARGEST_ACCOUNTS_NOT_FOUND",
                "Solana RPC did not return largest token accounts.",
                provider="solana_rpc",
                mint=mint,
            ),
            mint,
            rpc_meta,
        )

    accounts = [account for account in account_values if isinstance(account, dict)]
    if not accounts:
        return _with_known_mint_context(
            _error(
                "TOKEN_LARGEST_ACCOUNTS_NOT_FOUND",
                "Solana RPC did not return usable largest token accounts.",
                provider="solana_rpc",
                mint=mint,
            ),
            mint,
            rpc_meta,
        )

    top_account_pct = _rounded_percent(_percent(_sum_top(accounts, 1), supply_amount))
    top_3_accounts_pct = _rounded_percent(_percent(_sum_top(accounts, 3), supply_amount))
    top_5_accounts_pct = _rounded_percent(_percent(_sum_top(accounts, 5), supply_amount))
    top_10_accounts_pct = _rounded_percent(_percent(_sum_top(accounts, 10), supply_amount))
    concentration_level = _concentration_level(top_account_pct, top_10_accounts_pct)
    severity = _top_account_severity(top_account_pct)

    return {
        "ok": True,
        "source": "solana_rpc",
        "chain": "solana",
        "mint": mint,
        "summary": {
            "top_account_pct": top_account_pct,
            "top_3_accounts_pct": top_3_accounts_pct,
            "top_5_accounts_pct": top_5_accounts_pct,
            "top_10_accounts_pct": top_10_accounts_pct,
            "sampled_account_count": len(accounts),
            "concentration_level": concentration_level,
        },
        "signals": [
            {
                "label": "Largest visible token account",
                "value": _format_pct(top_account_pct),
                "severity": severity,
                "explanation": (
                    f"One visible token account controls {_format_pct(top_account_pct)} of supply."
                ),
            }
        ],
        "links": {
            "bubblemaps": build_bubblemaps_url(mint),
        },
        "rpc": dict(rpc_meta),
        "warnings": list(WARNINGS),
        "raw": {
            "supply": supply_value,
            "largest_accounts": accounts,
        },
    }
