#!/usr/bin/env python3
"""
Audit pasted Solana token mints for possible future curated-registry promotion.

The tool resolves token metadata, runs /swap/quote-style previews for standard
pairs, and reports quote coverage without mutating TOKEN_META.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.main import swap_quote  # noqa: E402
from providers.token_resolver import resolve_token  # noqa: E402


UNIVERSES = ["Jupiter", "Raydium", "Meteora", "Orca", "Phoenix", "Phantom", "PumpSwap"]
DEFAULT_USER_PUBLIC_KEY = "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL"
STANDARD_PAIR_TEMPLATES = [
    ("SOL", "TOKEN"),
    ("TOKEN", "SOL"),
    ("USDC", "TOKEN"),
    ("TOKEN", "USDC"),
]
VARIANT_UNIVERSE_LABELS = {
    "recommended_default": "Jupiter",
    "broader_search": "Jupiter",
    "exclude_recommended_dexes": "Jupiter",
    "direct_route_check": "Jupiter",
    "raydium_quote": "Raydium",
    "meteora_dlmm_quote": "Meteora",
    "orca_whirlpool_quote": "Orca",
    "phoenix_quote": "Phoenix",
    "phantom_quote": "Phantom",
    "pumpswap_quote": "PumpSwap",
}
LOW_LIQUIDITY_USD = 25_000.0


def classify_pair_coverage(success_count: int) -> str:
    if success_count >= 4:
        return "strong"
    if success_count == 3:
        return "good"
    if success_count == 2:
        return "thin"
    return "weak"


def dedupe_reasons(reasons: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for reason in reasons:
        key = str(reason or "").strip()
        if not key:
            continue
        if key.startswith("warning:"):
            warning_key = key.removeprefix("warning:")
            if warning_key in seen:
                continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _short(value: Any, *, max_len: int = 220) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def is_rate_limited_error(value: Any) -> bool:
    status_code = getattr(value, "status_code", None)
    detail = getattr(value, "detail", value)
    text = str(detail).lower()
    return status_code == 429 or "429" in text or "too many requests" in text or "rate limit" in text


def _surface_label(option: dict | None) -> str | None:
    if not option:
        return None
    return option.get("execution_surface_label") or option.get("provider") or option.get("route_label")


def visible_live_surfaces(response: dict) -> list[str]:
    candidates = [
        response.get("recommended_option"),
        response.get("direct_route_check"),
        response.get("recommended_executable_option"),
        *(response.get("other_options") or []),
    ]
    labels: list[str] = []
    seen = set()
    for option in candidates:
        if not option or option.get("quote_status") != "live":
            continue
        label = _surface_label(option)
        if not label:
            continue
        key = label.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(label.strip())
    return labels


def _failure_kind(universe: str, error: dict | None) -> str:
    error = error or {}
    status_code = error.get("status_code")
    helper_error = error.get("helper_error") if isinstance(error.get("helper_error"), dict) else {}
    code = error.get("code") or helper_error.get("code")
    detail = error.get("detail") or helper_error.get("message") or error.get("message")
    text = " ".join(str(part).lower() for part in (code, detail) if part)

    if status_code == 429 or "too many requests" in text or "rate limit" in text:
        return "rate_limited"
    if code == "NO_PUMPSWAP_POOL":
        return "no_pumpswap_pool"
    if code in {"NO_DISCOVERED_POOL", "NO_USABLE_DISCOVERED_POOL"}:
        return "expected_no_usable_pool"
    if "unsupported" in text or status_code == 400 and universe in {"Phoenix", "Phantom", "PumpSwap"}:
        return "expected_unsupported"
    if "low_liquidity" in text or "insufficient_liquidity" in text:
        return "expected_low_liquidity"
    return "provider_failure"


def provider_diagnostics(response: dict, visible_surfaces: list[str]) -> list[dict]:
    visible_keys = {label.lower() for label in visible_surfaces}
    diagnostics = {
        universe: {
            "universe": universe,
            "status": "success" if universe.lower() in visible_keys else "not_attempted",
            "fail_code": None,
            "fail_reason": None,
        }
        for universe in UNIVERSES
    }

    for item in ((response.get("debug") or {}).get("variant_errors") or []):
        universe = VARIANT_UNIVERSE_LABELS.get(item.get("variant_id"))
        if not universe or diagnostics[universe]["status"] == "success":
            continue
        helper_error = item.get("helper_error") if isinstance(item.get("helper_error"), dict) else {}
        diagnostics[universe] = {
            "universe": universe,
            "status": _failure_kind(universe, item),
            "fail_code": item.get("code") or helper_error.get("code"),
            "fail_reason": _short(item.get("detail") or helper_error.get("message") or item.get("message")),
        }

    return [diagnostics[universe] for universe in UNIVERSES]


def standard_pairs_for_mint(mint: str) -> list[tuple[str, str, str]]:
    pairs = []
    for left, right in STANDARD_PAIR_TEMPLATES:
        from_token = mint if left == "TOKEN" else left
        to_token = mint if right == "TOKEN" else right
        pairs.append((from_token, to_token, f"{left}->{right}"))
    return pairs


def audit_pair(
    from_token: str,
    to_token: str,
    label: str,
    *,
    amount: float,
    request_delay: float,
    user_public_key: str | None,
) -> dict:
    attempts = 0
    while True:
        attempts += 1
        try:
            response = swap_quote(
                from_token=from_token,
                to_token=to_token,
                amount=amount,
                network="solana",
                user_public_key=user_public_key,
            )
            surfaces = visible_live_surfaces(response)
            diagnostics = provider_diagnostics(response, surfaces)
            return {
                "pair": label,
                "from_token": response.get("from_token"),
                "to_token": response.get("to_token"),
                "amount": amount,
                "ok": True,
                "live_surfaces": surfaces,
                "success_count": len(surfaces),
                "classification": classify_pair_coverage(len(surfaces)),
                "recommended_surface": _surface_label(response.get("recommended_option")),
                "recommended_estimated_output": (response.get("recommended_option") or {}).get("estimated_output"),
                "recommended_estimated_output_usd": (response.get("recommended_option") or {}).get("estimated_output_usd"),
                "universes": diagnostics,
            }
        except Exception as exc:
            rate_limited = is_rate_limited_error(exc)
            if rate_limited and attempts == 1:
                time.sleep(10)
                continue

            detail = getattr(exc, "detail", str(exc))
            status_code = getattr(exc, "status_code", None)
            status = "rate_limited" if rate_limited else "provider_failure"
            if isinstance(exc, HTTPException) and status_code == 400:
                status = "quote_failed"
            return {
                "pair": label,
                "from_token": from_token,
                "to_token": to_token,
                "amount": amount,
                "ok": False,
                "live_surfaces": [],
                "success_count": 0,
                "classification": "weak",
                "recommended_surface": None,
                "recommended_estimated_output": None,
                "recommended_estimated_output_usd": None,
                "error": {
                    "status": status,
                    "status_code": status_code,
                    "detail": detail,
                    "attempts": attempts,
                },
                "universes": [
                    {
                        "universe": universe,
                        "status": "not_attempted",
                        "fail_code": None,
                        "fail_reason": None,
                    }
                    for universe in UNIVERSES
                ],
            }


def classify_promotion(token: dict, pairs: list[dict]) -> tuple[str, str, list[str]]:
    reasons: list[str] = []
    decimals = token.get("decimals")
    if not isinstance(decimals, int):
        return "do_not_promote_yet", "Token decimals are missing; quote preview is not safe.", ["missing_decimals"]

    if not token.get("symbol") and not token.get("display_name"):
        return "do_not_promote_yet", "Token display metadata is missing.", ["missing_metadata"]

    pair_by_name = {pair["pair"]: pair for pair in pairs}
    sol_forward = pair_by_name.get("SOL->TOKEN", {})
    sol_reverse = pair_by_name.get("TOKEN->SOL", {})
    sol_directions_work = sol_forward.get("success_count", 0) > 0 and sol_reverse.get("success_count", 0) > 0
    strong_or_good = [pair for pair in pairs if pair.get("classification") in {"strong", "good"}]

    if not sol_directions_work:
        reasons.append("missing_sol_direction_coverage")
    if len(strong_or_good) < 2:
        reasons.append("insufficient_strong_or_good_pairs")

    if not sol_directions_work or len(strong_or_good) < 2:
        weak_count = sum(1 for pair in pairs if pair.get("classification") == "weak")
        if weak_count:
            reasons.append("weak_pair_coverage")
        return "do_not_promote_yet", "Coverage is not strong enough for curated promotion.", reasons

    liquidity_usd = _safe_float(token.get("liquidity_usd"))
    warnings = list(token.get("warnings") or [])
    if not token.get("verified"):
        reasons.append("external_metadata_unverified")
    if liquidity_usd is not None and liquidity_usd < LOW_LIQUIDITY_USD:
        reasons.append("low_liquidity")
    if warnings:
        reasons.extend([f"warning:{warning}" for warning in warnings])
    reasons = dedupe_reasons(reasons)

    if reasons:
        return "manual_review", "Strong route coverage; review metadata before registry promotion.", reasons

    return "promote_candidate", "Token has enough route coverage for curated-registry consideration.", []


def audit_mint(
    mint: str,
    *,
    amount: float,
    request_delay: float,
    user_public_key: str | None = DEFAULT_USER_PUBLIC_KEY,
) -> dict:
    resolved = resolve_token(mint, allow_external=True)
    if resolved.get("ok") is not True:
        return {
            "ok": False,
            "mint": mint,
            "resolver_error": resolved.get("error"),
            "promotion_status": "do_not_promote_yet",
            "recommendation": "Token metadata could not be resolved.",
            "pairs": [],
        }

    token = resolved.get("token") or {}
    if not isinstance(token.get("decimals"), int):
        status, recommendation, reasons = classify_promotion(token, [])
        return {
            "ok": True,
            "token": token,
            "pairs": [],
            "promotion_status": status,
            "promotion_reasons": reasons,
            "recommendation": recommendation,
        }

    pairs = []
    for index, (from_token, to_token, label) in enumerate(standard_pairs_for_mint(token.get("mint") or mint)):
        pairs.append(
            audit_pair(
                from_token,
                to_token,
                label,
                amount=amount,
                request_delay=request_delay,
                user_public_key=user_public_key,
            )
        )
        if request_delay > 0 and index < 3:
            time.sleep(request_delay)

    status, recommendation, reasons = classify_promotion(token, pairs)
    return {
        "ok": True,
        "token": token,
        "pairs": pairs,
        "promotion_status": status,
        "promotion_reasons": reasons,
        "recommendation": recommendation,
    }


def audit_mints(
    mints: list[str],
    *,
    amount: float,
    request_delay: float,
    user_public_key: str | None = DEFAULT_USER_PUBLIC_KEY,
) -> dict:
    reports = []
    for index, mint in enumerate(mints):
        reports.append(
            audit_mint(
                mint,
                amount=amount,
                request_delay=request_delay,
                user_public_key=user_public_key,
            )
        )
        if request_delay > 0 and index < len(mints) - 1:
            time.sleep(request_delay)
    return {
        "ok": True,
        "universes": UNIVERSES,
        "reports": reports,
    }


def print_text_report(result: dict) -> None:
    for report_index, report in enumerate(result.get("reports") or []):
        if report_index:
            print()
        if not report.get("ok"):
            print(f"Mint: {report.get('mint')}")
            print("Status: do_not_promote_yet")
            print(f"Resolver error: {report.get('resolver_error')}")
            continue

        token = report.get("token") or {}
        print(f"Token: {token.get('symbol') or 'unknown'} / {token.get('display_name') or token.get('name') or 'unknown'}")
        print(f"Mint: {token.get('mint')}")
        print(f"Decimals: {token.get('decimals')}")
        print(f"Source: {token.get('source')}")
        print(f"Liquidity USD: {token.get('liquidity_usd')}")
        print(f"Price USD: {token.get('price_usd')}")
        print(f"Warnings: {', '.join(token.get('warnings') or []) or 'none'}")

        pairs = report.get("pairs") or []
        if pairs:
            print("\nPair coverage")
            print("Pair        | Count | Class  | Live surfaces")
            print("------------+-------+--------+----------------")
            for pair in pairs:
                surfaces = ", ".join(pair.get("live_surfaces") or []) or "none"
                print(
                    f"{pair.get('pair', '').ljust(11)} | "
                    f"{str(pair.get('success_count', 0)).ljust(5)} | "
                    f"{pair.get('classification', '').ljust(6)} | "
                    f"{surfaces}"
                )

            diagnostics = []
            for pair in pairs:
                for universe in pair.get("universes") or []:
                    if universe.get("status") == "success":
                        continue
                    diagnostics.append((pair.get("pair"), universe))

            if diagnostics:
                print("\nUniverse diagnostics")
                for pair_name, universe in diagnostics:
                    bits = [
                        f"{pair_name} {universe.get('universe')}: {universe.get('status')}",
                    ]
                    if universe.get("fail_code"):
                        bits.append(str(universe.get("fail_code")))
                    if universe.get("fail_reason"):
                        bits.append(str(universe.get("fail_reason")))
                    print("  - " + " - ".join(bits))

        print(f"\nPromotion score: {report.get('promotion_status')}")
        print(f"Recommendation: {report.get('recommendation')}")
        reasons = report.get("promotion_reasons") or []
        if reasons:
            print(f"Reasons: {', '.join(reasons)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit pasted Solana mints for future token-registry promotion.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--mint", help="Single Solana token mint to audit.")
    group.add_argument("--mints", nargs="+", help="One or more Solana token mints to audit.")
    parser.add_argument("--request-delay", type=float, default=3.0, help="Seconds between quote requests. Default: 3.")
    parser.add_argument("--amount", type=float, default=1.0, help="Amount to use for each standard pair. Default: 1.")
    parser.add_argument(
        "--user-public-key",
        default=DEFAULT_USER_PUBLIC_KEY,
        help="Wallet public key used for wallet-routing quote previews. Default: deterministic audit wallet.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mints = [args.mint] if args.mint else args.mints
    result = audit_mints(
        mints,
        amount=args.amount,
        request_delay=args.request_delay,
        user_public_key=args.user_public_key,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_text_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
