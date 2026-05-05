#!/usr/bin/env python3
"""
Run live quote-universe coverage checks for supported swap token pairs.

This script intentionally calls the same api.main quote/helper functions used by
/swap/quote, but it does not invoke ranking, execution, or UI code.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.main import (  # noqa: E402
    SOLANA_MAINNET_RPC_URL,
    _build_meteora_dlmm_quote_payload,
    _build_orca_whirlpool_quote_payload,
    _build_phantom_quote_payload,
    _build_phoenix_quote_payload,
    _build_pumpswap_quote_payload,
    _build_raydium_quote_params,
    _resolve_swap_token_meta,
    _try_fetch_jupiter_quote,
    _try_fetch_meteora_dlmm_quote,
    _try_fetch_orca_whirlpool_quote,
    _try_fetch_phantom_quote,
    _try_fetch_phoenix_quote,
    _try_fetch_pumpswap_quote,
    _try_fetch_raydium_quote,
    to_raw_amount,
)


DEFAULT_TO_TOKENS = ["USDC", "BONK", "WIF", "POPCAT", "SPX6900", "CHAD", "FIGURE"]
UNIVERSES = ["Jupiter", "Raydium", "Meteora", "Orca", "Phoenix", "Phantom", "PumpSwap"]
DEFAULT_USER_PUBLIC_KEY = "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL"


def classify_coverage(success_count: int) -> str:
    if success_count >= 5:
        return "strong"
    if success_count == 4:
        return "good"
    if 2 <= success_count <= 3:
        return "thin"
    return "weak"


def short_detail(value: Any, *, max_len: int = 180) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def nested_get(data: dict, path: list[str]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def output_amount_for_universe(universe: str, data: dict) -> str | None:
    if universe == "Jupiter":
        return data.get("outAmount")
    if universe == "Raydium":
        return nested_get(data, ["data", "outputAmount"])
    if universe == "Phantom":
        first_quote = ((data.get("quoteResponse") or {}).get("quotes") or [{}])[0]
        return data.get("first_quote_buyAmount") or first_quote.get("buyAmount")
    return data.get("out_amount_raw")


def failure_kind(universe: str, status_code: int | None, code: str | None, detail: str | None) -> str:
    text = " ".join(part for part in [code, detail] if part).lower()
    if status_code == 400 and (
        "unsupported" in text
        or "sol -> usdc only" in text
        or "figure docs-token pool only" in text
        or "curated sol -> spl" in text
        or "default-enabled registry token pairs" in text
    ):
        return "expected_unsupported"
    if code in {"NO_DISCOVERED_POOL", "NO_USABLE_DISCOVERED_POOL"}:
        return "expected_no_usable_pool"
    if "insufficient_liquidity" in text:
        return "expected_low_liquidity"
    if "too many requests" in text or status_code == 429:
        return "unexpected_rate_limited"
    if universe == "Phoenix" and status_code == 400:
        return "expected_unsupported"
    if universe == "PumpSwap" and status_code == 400:
        return "expected_unsupported"
    return "unexpected"


def summarize_result(universe: str, result: dict) -> dict:
    if result.get("ok"):
        data = result.get("data") or {}
        return {
            "universe": universe,
            "success": True,
            "estimated_output_raw": output_amount_for_universe(universe, data),
            "fail_code": None,
            "fail_reason": None,
            "failure_kind": None,
        }

    error = result.get("error") or {}
    helper_error = error.get("helper_error") if isinstance(error.get("helper_error"), dict) else None
    code = error.get("code") or (helper_error or {}).get("code")
    detail = error.get("detail") or (helper_error or {}).get("message")
    status_code = error.get("status_code")
    return {
        "universe": universe,
        "success": False,
        "estimated_output_raw": None,
        "fail_code": code,
        "fail_reason": short_detail(detail),
        "failure_kind": failure_kind(universe, status_code, code, detail),
    }


def quote_universe(
    universe: str,
    *,
    input_mint: str,
    output_mint: str,
    amount_raw: int,
    user_public_key: str | None,
) -> dict:
    if universe == "Jupiter":
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_raw),
            "slippageBps": "50",
            "restrictIntermediateTokens": "true",
            "instructionVersion": "V2",
        }
        return _try_fetch_jupiter_quote(params)

    if universe == "Raydium":
        params = _build_raydium_quote_params(
            input_mint=input_mint,
            output_mint=output_mint,
            amount_raw=amount_raw,
            slippage_bps=50,
        )
        return _try_fetch_raydium_quote(params)

    if universe == "Meteora":
        payload = _build_meteora_dlmm_quote_payload(
            input_mint=input_mint,
            output_mint=output_mint,
            amount_raw=amount_raw,
            slippage_bps=50,
            rpc_url=SOLANA_MAINNET_RPC_URL,
        )
        return _try_fetch_meteora_dlmm_quote(payload)

    if universe == "Orca":
        payload = _build_orca_whirlpool_quote_payload(
            input_mint=input_mint,
            output_mint=output_mint,
            amount_raw=amount_raw,
            slippage_bps=50,
            rpc_url=SOLANA_MAINNET_RPC_URL,
        )
        return _try_fetch_orca_whirlpool_quote(payload)

    if universe == "Phoenix":
        payload = _build_phoenix_quote_payload(
            input_mint=input_mint,
            output_mint=output_mint,
            amount_raw=amount_raw,
            slippage_bps=50,
            rpc_url=SOLANA_MAINNET_RPC_URL,
        )
        return _try_fetch_phoenix_quote(payload)

    if universe == "Phantom":
        payload = _build_phantom_quote_payload(
            input_mint=input_mint,
            output_mint=output_mint,
            amount_raw=amount_raw,
            slippage_bps=50,
            user_public_key=user_public_key,
        )
        return _try_fetch_phantom_quote(payload)

    if universe == "PumpSwap":
        payload = _build_pumpswap_quote_payload(
            input_mint=input_mint,
            output_mint=output_mint,
            amount_raw=amount_raw,
            slippage_bps=50,
            rpc_url=SOLANA_MAINNET_RPC_URL,
            user_public_key=user_public_key,
        )
        return _try_fetch_pumpswap_quote(payload)

    return {
        "ok": False,
        "error": {
            "status_code": 400,
            "detail": f"Unknown quote universe: {universe}",
        },
    }


def parse_pair(value: str) -> tuple[str, str]:
    raw = (value or "").strip().upper()
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"Pair must use FROM:TO format: {value}")
    left, right = [part.strip() for part in raw.split(":", 1)]
    if not left or not right:
        raise argparse.ArgumentTypeError(f"Pair must include both FROM and TO symbols: {value}")
    if left == right:
        raise argparse.ArgumentTypeError(f"Pair symbols must be different: {value}")
    return left, right


def audit_pair(
    from_symbol: str,
    to_symbol: str,
    *,
    amount: float,
    user_public_key: str | None,
    request_delay: float,
) -> dict:
    input_meta = _resolve_swap_token_meta(from_symbol)
    output_meta = _resolve_swap_token_meta(to_symbol)
    if not input_meta or not output_meta:
        raise ValueError(f"Unsupported audit pair: {from_symbol} -> {to_symbol}")

    amount_raw = to_raw_amount(amount, input_meta["decimals"])
    universes = []
    for index, universe in enumerate(UNIVERSES):
        result = quote_universe(
            universe,
            input_mint=input_meta["mint"],
            output_mint=output_meta["mint"],
            amount_raw=amount_raw,
            user_public_key=user_public_key,
        )
        universes.append(summarize_result(universe, result))
        if request_delay > 0 and index < len(UNIVERSES) - 1:
            time.sleep(request_delay)

    success_count = sum(1 for item in universes if item["success"])
    return {
        "pair": f"{from_symbol}->{to_symbol}",
        "from_token": from_symbol,
        "to_token": to_symbol,
        "amount": amount,
        "amount_raw": str(amount_raw),
        "success_count": success_count,
        "classification": classify_coverage(success_count),
        "universes": universes,
    }


def audit_pairs(
    pairs_to_audit: list[tuple[str, str]],
    *,
    amount: float,
    user_public_key: str | None,
    request_delay: float,
) -> dict:
    pairs = []
    for index, (from_symbol, to_symbol) in enumerate(pairs_to_audit):
        pairs.append(
            audit_pair(
                from_symbol.upper().strip(),
                to_symbol.upper().strip(),
                amount=amount,
                user_public_key=user_public_key,
                request_delay=request_delay,
            )
        )
        if request_delay > 0 and index < len(pairs_to_audit) - 1:
            time.sleep(request_delay)
    return {
        "universes": UNIVERSES,
        "pairs": pairs,
    }


def audit(tokens: list[str], *, amount: float, user_public_key: str | None, request_delay: float) -> dict:
    return audit_pairs(
        [("SOL", token.upper().strip()) for token in tokens],
        amount=amount,
        user_public_key=user_public_key,
        request_delay=request_delay,
    )


def status_cell(item: dict) -> str:
    if item["success"]:
        return "OK"
    code = item.get("fail_code") or item.get("failure_kind") or "FAIL"
    return code


def print_text_report(result: dict) -> None:
    headers = ["Pair", "Count", "Class", *result["universes"]]
    rows = []
    for pair in result["pairs"]:
        by_universe = {item["universe"]: item for item in pair["universes"]}
        rows.append(
            [
                pair["pair"],
                str(pair["success_count"]),
                pair["classification"],
                *[status_cell(by_universe[universe]) for universe in result["universes"]],
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    print("Coverage matrix")
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))

    print("\nFailed universe diagnostics")
    for pair in result["pairs"]:
        failures = [item for item in pair["universes"] if not item["success"]]
        if not failures:
            continue
        print(f"{pair['pair']}:")
        for item in failures:
            reason = item.get("fail_reason") or item.get("failure_kind") or "failed"
            code = item.get("fail_code") or item.get("failure_kind") or "FAIL"
            print(f"  - {item['universe']}: {code} - {reason} ({item.get('failure_kind')})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit quote-universe coverage for supported token pairs.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--amount", type=float, default=1.0, help="SOL amount to quote. Default: 1.0")
    parser.add_argument(
        "--tokens",
        nargs="+",
        default=DEFAULT_TO_TOKENS,
        help="Output token symbols to audit as SOL -> token. Ignored when --pairs is provided.",
    )
    parser.add_argument(
        "--pairs",
        nargs="+",
        type=parse_pair,
        help="Explicit FROM:TO pairs to audit, for example WIF:SOL POPCAT:WIF USDC:POPCAT.",
    )
    parser.add_argument(
        "--user-public-key",
        default=DEFAULT_USER_PUBLIC_KEY,
        help="Wallet public key used for Phantom/PumpSwap quote previews.",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.75,
        help="Seconds to sleep between quote requests to reduce rate limits. Default: 0.75",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.pairs:
        result = audit_pairs(
            args.pairs,
            amount=args.amount,
            user_public_key=args.user_public_key,
            request_delay=args.request_delay,
        )
    else:
        result = audit(
            args.tokens,
            amount=args.amount,
            user_public_key=args.user_public_key,
            request_delay=args.request_delay,
        )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_text_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
