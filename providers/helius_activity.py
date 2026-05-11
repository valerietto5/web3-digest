from __future__ import annotations

import os
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import requests


DEFAULT_HELIUS_API_BASE_URL = "https://api-mainnet.helius-rpc.com"
DEFAULT_TIMEOUT_SECONDS = 10


def _extract_api_key_from_rpc_url(rpc_url: str | None) -> str | None:
    if not rpc_url:
        return None
    parsed = urlparse(rpc_url)
    values = parse_qs(parsed.query).get("api-key")
    if values and values[0]:
        return values[0]
    return None


def _configured_api_key(api_key: str | None, rpc_url: str | None) -> str | None:
    explicit = (api_key or "").strip()
    if explicit:
        return explicit

    env_key = (os.getenv("HELIUS_API_KEY") or "").strip()
    if env_key:
        return env_key

    return _extract_api_key_from_rpc_url(rpc_url or os.getenv("HELIUS_RPC_URL"))


def _configured_rpc_url(rpc_url: str | None) -> str | None:
    return (rpc_url or os.getenv("HELIUS_RPC_URL") or "").strip() or None


def _activity_base_url(rpc_url: str | None) -> str:
    raw_url = (rpc_url or "").strip()
    if not raw_url:
        return DEFAULT_HELIUS_API_BASE_URL

    parsed = urlparse(raw_url)
    if not parsed.scheme or not parsed.netloc:
        return DEFAULT_HELIUS_API_BASE_URL

    path = parsed.path or ""
    if "/v0" in path:
        path = path.split("/v0", 1)[0]
    else:
        path = ""

    return f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/")


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            **extra,
        },
    }


def _normalize_activity_item(item: dict[str, Any]) -> dict[str, Any]:
    programs = item.get("programs")
    if not isinstance(programs, list):
        programs = []

    if not programs:
        seen_programs = set()
        for instruction in item.get("instructions") or []:
            if not isinstance(instruction, dict):
                continue
            program_id = instruction.get("programId")
            if not program_id or program_id in seen_programs:
                continue
            seen_programs.add(program_id)
            programs.append(program_id)

    return {
        "signature": item.get("signature"),
        "timestamp": item.get("timestamp"),
        "type": item.get("type"),
        "description": item.get("description"),
        "fee": item.get("fee"),
        "native_transfers": item.get("nativeTransfers") or [],
        "token_transfers": item.get("tokenTransfers") or [],
        "programs": programs,
        "raw": item,
    }


def fetch_wallet_activity(
    address: str,
    limit: int = 20,
    api_key: str | None = None,
    rpc_url: str | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    address = (address or "").strip()
    if not address:
        return _error(
            "WALLET_ADDRESS_REQUIRED",
            "Wallet address is required.",
        )

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
        return _error(
            "INVALID_ACTIVITY_LIMIT",
            "Wallet activity limit must be between 1 and 100.",
            address=address,
            limit=limit,
        )

    configured_rpc_url = _configured_rpc_url(rpc_url)
    configured_api_key = _configured_api_key(api_key, configured_rpc_url)
    if not configured_api_key and not configured_rpc_url:
        return _error(
            "HELIUS_NOT_CONFIGURED",
            "Set HELIUS_API_KEY or HELIUS_RPC_URL to enable wallet activity lookup.",
            address=address,
        )

    base_url = _activity_base_url(configured_rpc_url)
    url = f"{base_url}/v0/addresses/{quote(address)}/transactions"
    params: dict[str, Any] = {"limit": limit}
    if configured_api_key:
        params["api-key"] = configured_api_key

    try:
        response = requests.get(url, params=params, timeout=timeout)
    except requests.RequestException as exc:
        return _error(
            "HELIUS_ACTIVITY_LOOKUP_FAILED",
            "Helius wallet activity lookup failed.",
            address=address,
            detail=str(exc),
        )

    if not response.ok:
        return _error(
            "HELIUS_ACTIVITY_HTTP_ERROR",
            "Helius wallet activity lookup returned an HTTP error.",
            address=address,
            status_code=response.status_code,
            detail=(response.text or "")[:500],
        )

    try:
        data = response.json()
    except ValueError as exc:
        return _error(
            "HELIUS_ACTIVITY_INVALID_JSON",
            "Helius wallet activity lookup returned invalid JSON.",
            address=address,
            detail=str(exc),
        )

    if not isinstance(data, list):
        return _error(
            "HELIUS_ACTIVITY_INVALID_JSON",
            "Helius wallet activity lookup returned an unexpected response shape.",
            address=address,
        )

    return {
        "ok": True,
        "source": "helius",
        "address": address,
        "limit": limit,
        "items": [
            _normalize_activity_item(item)
            for item in data
            if isinstance(item, dict)
        ],
    }
