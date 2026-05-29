from __future__ import annotations

import os
import base64
import re
from typing import Any

import requests


DEFAULT_SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
DEFAULT_TIMEOUT_SECONDS = 10
_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


def _default_rpc_url() -> str:
    return (
        os.getenv("SWAP_PREPARE_RPC_URL")
        or os.getenv("SWAP_SUBMIT_RPC_URL")
        or os.getenv("SOLANA_RPC_URL")
        or os.getenv("SOLANA_MAINNET_RPC_URL")
        or os.getenv("HELIUS_RPC_URL")
        or DEFAULT_SOLANA_RPC_URL
    )


def _extract_decimals(result: dict[str, Any]) -> int | None:
    value = result.get("value") if isinstance(result, dict) else None
    if not isinstance(value, dict):
        return None

    account = value.get("data")
    parsed = account.get("parsed") if isinstance(account, dict) else None
    info = parsed.get("info") if isinstance(parsed, dict) else None
    decimals = info.get("decimals") if isinstance(info, dict) else None

    if isinstance(decimals, bool):
        return None
    if isinstance(decimals, int) and decimals >= 0:
        return decimals
    return None


def _extract_raw_mint_decimals(result: dict[str, Any]) -> int | None:
    value = result.get("value") if isinstance(result, dict) else None
    if not isinstance(value, dict):
        return None

    account_data = value.get("data")
    encoded = None
    if isinstance(account_data, list) and account_data:
        encoded = account_data[0]
    elif isinstance(account_data, str):
        encoded = account_data
    if not isinstance(encoded, str) or not encoded:
        return None

    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception:
        return None

    # SPL Token mint layout stores decimals at byte offset 44.
    if len(raw) <= 44:
        return None
    decimals = raw[44]
    return int(decimals) if 0 <= decimals <= 255 else None


def fetch_solana_mint_decimals(
    mint: str,
    rpc_url: str | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    mint = (mint or "").strip()
    if not _BASE58_RE.fullmatch(mint):
        return {
            "ok": False,
            "error": {
                "code": "INVALID_SOLANA_MINT",
                "message": "mint must look like a Solana public key.",
                "provider": "solana_rpc",
                "mint": mint,
            },
        }

    url = rpc_url or _default_rpc_url()
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [
            mint,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
            },
        ],
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_DECIMALS_LOOKUP_FAILED",
                "message": "Solana RPC mint decimals lookup failed.",
                "provider": "solana_rpc",
                "mint": mint,
                "detail": exc.__class__.__name__,
            },
        }

    if not response.ok:
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_DECIMALS_LOOKUP_FAILED",
                "message": "Solana RPC mint decimals lookup returned an HTTP error.",
                "provider": "solana_rpc",
                "mint": mint,
                "status_code": response.status_code,
            },
        }

    try:
        data = response.json()
    except ValueError as exc:
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_DECIMALS_LOOKUP_FAILED",
                "message": "Solana RPC mint decimals lookup returned invalid JSON.",
                "provider": "solana_rpc",
                "mint": mint,
                "detail": exc.__class__.__name__,
            },
        }

    if isinstance(data, dict) and data.get("error"):
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_DECIMALS_LOOKUP_FAILED",
                "message": "Solana RPC mint decimals lookup returned an RPC error.",
                "provider": "solana_rpc",
                "mint": mint,
                "rpc_error": data.get("error"),
            },
        }

    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict) or result.get("value") is None:
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_DECIMALS_NOT_FOUND",
                "message": "Solana RPC did not return a parsed mint account for this token.",
                "provider": "solana_rpc",
                "mint": mint,
            },
        }

    decimals = _extract_decimals(result)
    if decimals is None:
        decimals = _extract_raw_mint_decimals(result)
    if decimals is None:
        return {
            "ok": False,
            "error": {
                "code": "TOKEN_DECIMALS_NOT_FOUND",
                "message": "Solana RPC parsed mint account did not include decimals.",
                "provider": "solana_rpc",
                "mint": mint,
            },
        }

    owner = None
    value = result.get("value")
    if isinstance(value, dict):
        owner = value.get("owner")

    return {
        "ok": True,
        "decimals": decimals,
        "source": "solana_rpc_mint_account",
        "mint": mint,
        "owner": owner,
    }
