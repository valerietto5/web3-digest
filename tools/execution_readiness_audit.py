#!/usr/bin/env python3
"""Non-live swap execution readiness audit.

This tool checks quote and prepare readiness only. It never signs transactions.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


DEFAULT_PAIRS = [
    "SOL:USDC",
    "SOL:BONK",
    "SOL:WIF",
    "WIF:USDC",
    "USDC:POPCAT",
]


@dataclass
class AuditPair:
    from_token: str
    to_token: str

    @property
    def label(self) -> str:
        return f"{self.from_token}:{self.to_token}"


def parse_pair(value: str) -> AuditPair:
    if ":" not in value:
        raise argparse.ArgumentTypeError("Pairs must use FROM:TO format.")
    from_token, to_token = [part.strip() for part in value.split(":", 1)]
    if not from_token or not to_token:
        raise argparse.ArgumentTypeError("Pairs must include both FROM and TO.")
    return AuditPair(from_token=from_token, to_token=to_token)


def build_pairs(args: argparse.Namespace) -> list[AuditPair]:
    pairs = list(args.pair or [])
    if args.custom_from:
        pairs.append(AuditPair(from_token=args.custom_from, to_token=args.to))
    if not pairs:
        pairs = [parse_pair(value) for value in DEFAULT_PAIRS]
    return pairs


def should_check_prepare(args: argparse.Namespace) -> bool:
    return bool(args.check_prepare and args.user_public_key)


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as response:
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "data": json.loads(response.read().decode("utf-8")),
            }
    except error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            data = {"ok": False, "error": {"code": "HTTP_ERROR", "message": str(exc.code)}}
        return {"ok": False, "status": exc.code, "data": data}
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "data": {"ok": False, "error": {"code": "REQUEST_FAILED", "message": str(exc)}},
        }


def quote_url(server_url: str, pair: AuditPair, amount: float) -> str:
    query = parse.urlencode(
        {
            "from_token": pair.from_token,
            "to_token": pair.to_token,
            "amount": amount,
        }
    )
    return f"{server_url.rstrip('/')}/swap/quote?{query}"


def prepare_payload(pair: AuditPair, option: dict[str, Any], amount: float, user_public_key: str) -> dict[str, Any]:
    return {
        "provider": "jupiter-metis",
        "variant_id": option.get("variant_id") or "recommended_default",
        "from_token": pair.from_token,
        "to_token": pair.to_token,
        "amount": amount,
        "slippage_bps": 50,
        "user_public_key": user_public_key,
        "network": "solana",
    }


def _best_option(data: dict[str, Any]) -> dict[str, Any] | None:
    option = data.get("recommended_executable_option") or data.get("recommended_option")
    if isinstance(option, dict):
        return option
    return None


def audit_pair(args: argparse.Namespace, pair: AuditPair) -> dict[str, Any]:
    quote_result = _request_json("GET", quote_url(args.server_url, pair, args.amount))
    quote_data = quote_result.get("data") or {}
    quote_ok = bool(quote_result.get("ok") and quote_data.get("ok") is not False)
    option = _best_option(quote_data) if quote_ok else None
    readiness = (option or {}).get("execution_readiness") or {}
    jupiter_ready = bool(readiness.get("execution_ready"))

    row = {
        "pair": pair.label,
        "quote_ok": quote_ok,
        "best_surface": (option or {}).get("execution_surface_label"),
        "jupiter_ready": jupiter_ready,
        "stage": readiness.get("execution_stage") or "quote_only",
        "provider_status": readiness.get("provider_status"),
        "provider_label": readiness.get("provider_label"),
        "prepare_capable": bool(readiness.get("prepare_capable")),
        "submit_capable": bool(readiness.get("submit_capable")),
        "prepare_checked": False,
        "prepare_ok": None,
        "error_code": None,
        "external": bool((quote_data.get("summary") or {}).get("uses_external_tokens")),
    }

    if not quote_ok:
        row["error_code"] = ((quote_data.get("error") or {}).get("code") or "QUOTE_FAILED")
        return row

    if should_check_prepare(args) and jupiter_ready and option:
        payload = prepare_payload(pair, option, args.amount, args.user_public_key)
        prepare_result = _request_json(
            "POST",
            f"{args.server_url.rstrip('/')}/swap/execute/prepare",
            payload,
        )
        prepare_data = prepare_result.get("data") or {}
        row["prepare_checked"] = True
        row["prepare_ok"] = bool(prepare_result.get("ok") and prepare_data.get("ok"))
        if not row["prepare_ok"]:
            row["error_code"] = ((prepare_data.get("error") or {}).get("code") or "PREPARE_FAILED")

    return row


def render_text_report(rows: list[dict[str, Any]]) -> str:
    header = (
        "pair | quote_ok | best_surface | jupiter_ready | stage | provider_status | "
        "provider_label | prepare_capable | submit_capable | prepare_checked | "
        "prepare_ok | error_code | external"
    )
    lines = [header]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    str(row.get("pair")),
                    str(row.get("quote_ok")),
                    str(row.get("best_surface") or ""),
                    str(row.get("jupiter_ready")),
                    str(row.get("stage") or ""),
                    str(row.get("provider_status") or ""),
                    str(row.get("provider_label") or ""),
                    str(row.get("prepare_capable")),
                    str(row.get("submit_capable")),
                    str(row.get("prepare_checked")),
                    str(row.get("prepare_ok")),
                    str(row.get("error_code") or ""),
                    str(row.get("external")),
                ]
            )
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit non-live swap execution readiness.")
    parser.add_argument("--server-url", default="http://127.0.0.1:8000")
    parser.add_argument("--pair", action="append", type=parse_pair)
    parser.add_argument("--custom-from")
    parser.add_argument("--to", default="USDC")
    parser.add_argument("--amount", type=float, default=1.0)
    parser.add_argument("--user-public-key")
    parser.add_argument("--check-prepare", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pairs = build_pairs(args)
    rows = [audit_pair(args, pair) for pair in pairs]

    if args.json:
        print(json.dumps({"ok": True, "rows": rows}, indent=2, sort_keys=True))
    else:
        print(render_text_report(rows))

    if args.check_prepare and not args.user_public_key:
        print("Prepare check skipped: --user-public-key is required.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
