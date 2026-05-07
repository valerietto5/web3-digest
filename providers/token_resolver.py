from __future__ import annotations

import re
from typing import Any

import requests

from providers.solana_token_metadata import fetch_solana_mint_decimals
from token_registry import NATIVE_TOKENS, TOKENS


_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
DEXSCREENER_TIMEOUT_SECONDS = 8


def _is_probable_solana_mint(value: str) -> bool:
    return bool(_BASE58_RE.fullmatch(value or ""))


def _public_token(meta: dict[str, Any], *, source: str) -> dict[str, Any]:
    symbol = (meta.get("symbol") or "").strip()
    display_name = (meta.get("display_name") or meta.get("name") or symbol).strip()
    mint = (meta.get("mint") or "").strip()

    return {
        "source": source,
        "symbol": symbol,
        "name": meta.get("name") or display_name or symbol,
        "display_name": display_name or symbol,
        "mint": mint,
        "decimals": meta.get("decimals"),
        "logo_uri": meta.get("logo_uri") or meta.get("image") or meta.get("image_url"),
        "verified": bool(meta.get("verified")),
        "default_enabled": bool(meta.get("default_enabled")),
        "tags": meta.get("tags") or [],
        "coingecko_id": meta.get("coingecko_id"),
        "dexscreener_chain_id": meta.get("dexscreener_chain_id"),
        "warnings": [],
    }


def _registry_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for symbol, meta in NATIVE_TOKENS.items():
        row = dict(meta)
        row.setdefault("symbol", symbol)
        row.setdefault("mint", meta.get("mint"))
        entries.append(row)

    for mint, meta in TOKENS.items():
        row = dict(meta)
        row.setdefault("mint", mint)
        entries.append(row)

    return entries


def _resolve_registry_token(query: str) -> dict[str, Any] | None:
    wanted_symbol = query.strip().upper()
    wanted_mint = query.strip()

    for meta in _registry_entries():
        symbol = (meta.get("symbol") or "").strip().upper()
        mint = (meta.get("mint") or "").strip()
        if symbol == wanted_symbol or mint == wanted_mint:
            return _public_token(meta, source="registry")

    return None


def _to_float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _pair_liquidity_usd(pair: dict[str, Any]) -> float:
    return _to_float_or_none((pair.get("liquidity") or {}).get("usd")) or 0.0


def _extract_pair_token(pair: dict[str, Any], mint: str) -> dict[str, Any] | None:
    for key in ("baseToken", "quoteToken"):
        token = pair.get(key)
        if not isinstance(token, dict):
            continue
        if (token.get("address") or "").strip() == mint:
            return token
    return None


def _dexscreener_token_from_pair(mint: str, pair: dict[str, Any]) -> dict[str, Any] | None:
    pair_token = _extract_pair_token(pair, mint)
    if not pair_token:
        return None

    symbol = (pair_token.get("symbol") or "").strip() or None
    name = (pair_token.get("name") or "").strip() or None
    if not symbol and not name:
        return None

    info = pair.get("info") if isinstance(pair.get("info"), dict) else {}
    liquidity_usd = _to_float_or_none((pair.get("liquidity") or {}).get("usd"))
    price_usd = _to_float_or_none(pair.get("priceUsd"))

    return {
        "source": "dexscreener",
        "symbol": symbol,
        "name": name or symbol,
        "display_name": name or symbol,
        "mint": mint,
        "decimals": None,
        "logo_uri": info.get("imageUrl"),
        "verified": False,
        "default_enabled": False,
        "tags": ["external", "dexscreener"],
        "coingecko_id": None,
        "dexscreener_chain_id": pair.get("chainId") or "solana",
        "liquidity_usd": liquidity_usd,
        "price_usd": price_usd,
        "pair_address": pair.get("pairAddress"),
        "pair_url": pair.get("url"),
        "warnings": ["external_metadata_unverified", "decimals_unresolved"],
    }


def fetch_dexscreener_token_metadata(mint: str, *, timeout: int = DEXSCREENER_TIMEOUT_SECONDS) -> dict[str, Any]:
    urls = [
        f"https://api.dexscreener.com/token-pairs/v1/solana/{mint}",
        f"https://api.dexscreener.com/latest/dex/tokens/{mint}",
    ]
    pairs: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for url in urls:
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"accept": "application/json", "user-agent": "web3-digest/0.1"},
            )
        except requests.RequestException as exc:
            failures.append({"url": url, "error": str(exc)})
            continue

        if not response.ok:
            failures.append({"url": url, "status_code": response.status_code})
            continue

        try:
            data = response.json()
        except ValueError as exc:
            failures.append({"url": url, "error": f"invalid JSON: {exc}"})
            continue

        if isinstance(data, list):
            pairs.extend([pair for pair in data if isinstance(pair, dict)])
        elif isinstance(data, dict) and isinstance(data.get("pairs"), list):
            pairs.extend([pair for pair in data["pairs"] if isinstance(pair, dict)])

    if pairs:
        pairs.sort(key=_pair_liquidity_usd, reverse=True)
        for pair in pairs:
            token = _dexscreener_token_from_pair(mint, pair)
            if token:
                return {"ok": True, "token": token}

        return {
            "ok": False,
            "error": {
                "code": "TOKEN_METADATA_NOT_FOUND",
                "message": "DexScreener returned pairs, but none contained usable token metadata for this mint.",
                "provider": "dexscreener",
                "mint": mint,
            },
        }

    if failures:
        return {
            "ok": False,
            "error": {
                "code": "EXTERNAL_TOKEN_LOOKUP_FAILED",
                "message": "DexScreener token metadata lookup failed.",
                "provider": "dexscreener",
                "mint": mint,
                "failures": failures,
            },
        }

    return {
        "ok": False,
        "error": {
            "code": "TOKEN_METADATA_NOT_FOUND",
            "message": "DexScreener returned no token pairs for this mint.",
            "provider": "dexscreener",
            "mint": mint,
        },
    }


def _with_decimals_lookup(token: dict[str, Any]) -> dict[str, Any]:
    mint = (token.get("mint") or "").strip()
    if not mint:
        return token

    decimals_result = fetch_solana_mint_decimals(mint)
    if decimals_result.get("ok") is True:
        token["decimals"] = decimals_result.get("decimals")
        token["decimals_source"] = decimals_result.get("source") or "solana_rpc"
        if decimals_result.get("owner"):
            token["mint_account_owner"] = decimals_result.get("owner")
        token["warnings"] = [
            warning
            for warning in (token.get("warnings") or [])
            if warning != "decimals_unresolved"
        ]
        return token

    token["decimals_error"] = decimals_result.get("error") or {
        "code": "TOKEN_DECIMALS_LOOKUP_FAILED",
        "message": "Token decimals lookup failed.",
    }
    warnings = list(token.get("warnings") or [])
    if "decimals_unresolved" not in warnings:
        warnings.append("decimals_unresolved")
    token["warnings"] = warnings
    return token


def _unresolved_mint_response(mint: str, *, code: str = "TOKEN_METADATA_LOOKUP_NOT_IMPLEMENTED") -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": "Token is not in the local registry. External token metadata lookup is required.",
            "query": mint,
        },
        "token": {
            "source": "unresolved_mint",
            "symbol": None,
            "name": None,
            "display_name": None,
            "mint": mint,
            "decimals": None,
            "logo_uri": None,
            "verified": False,
            "default_enabled": False,
            "tags": [],
            "coingecko_id": None,
            "dexscreener_chain_id": "solana",
            "warnings": ["external_lookup_required"],
        },
    }


def resolve_token(query: str, *, allow_external: bool = True) -> dict[str, Any]:
    """
    Resolve a swap token query without guessing.

    V1 intentionally resolves only existing curated registry entries. Unknown
    Solana mints can optionally use external metadata lookup. V1 keeps registry
    entries authoritative and does not add unknown mints to the quote registry.
    """
    normalized = (query or "").strip()
    if not normalized:
        return {
            "ok": False,
            "error": {
                "code": "EMPTY_QUERY",
                "message": "query must be a non-empty token symbol or Solana mint address.",
            },
        }

    registry_token = _resolve_registry_token(normalized)
    if registry_token:
        return {
            "ok": True,
            "token": registry_token,
        }

    if _is_probable_solana_mint(normalized):
        if not allow_external:
            return _unresolved_mint_response(normalized)

        external = fetch_dexscreener_token_metadata(normalized)
        if external.get("ok") is True:
            token = external.get("token")
            if isinstance(token, dict):
                external["token"] = _with_decimals_lookup(token)
            return external
        return external

    return {
        "ok": False,
        "error": {
            "code": "TOKEN_NOT_FOUND",
            "message": "Token symbol is not in the local registry.",
            "query": normalized,
        },
    }
