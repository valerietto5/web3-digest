from __future__ import annotations

import re
from typing import Any

from token_registry import NATIVE_TOKENS, TOKENS


_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


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


def resolve_token(query: str) -> dict[str, Any]:
    """
    Resolve a swap token query without guessing.

    V1 intentionally resolves only existing curated registry entries. Unknown
    Solana mints return a structured not-resolved result so later Jupiter,
    DexScreener, or Helius metadata lookups can fill the same shape.
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
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_METADATA_LOOKUP_NOT_IMPLEMENTED",
                "message": "Token is not in the local registry. External token metadata lookup is required.",
                "query": normalized,
            },
            "token": {
                "source": "unresolved_mint",
                "symbol": None,
                "name": None,
                "display_name": None,
                "mint": normalized,
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

    return {
        "ok": False,
        "error": {
            "code": "TOKEN_NOT_FOUND",
            "message": "Token symbol is not in the local registry.",
            "query": normalized,
        },
    }
