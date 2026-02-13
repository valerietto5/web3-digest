from __future__ import annotations

from datetime import datetime, timezone
import argparse
from typing import Dict, List

from db import init_db, insert_balance_snapshot, get_latest_balances
from portfolio import compute_portfolio_report


def parse_set_kv(pairs: List[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for item in pairs:
        if "=" not in item:
            raise ValueError(f"Invalid --set '{item}'. Use like btc=0.01")
        k, v = item.split("=", 1)
        k = k.strip().lower()
        out[k] = float(v)
    return out


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Insert balance snapshot into SQLite (manual source)")
    p.add_argument("--account", default="val-main", help="Account id (default: val-main)")
    p.add_argument("--assets", nargs="+", default=["btc", "eth", "usdc"], help="Assets list")
    p.add_argument("--source", default="manual", help="Source label (default: manual)")
    p.add_argument(
        "--set",
        nargs="*",
        default=[],
        help="Override balances as key=value pairs, e.g. --set btc=0.01 eth=0.2 usdc=150",
    )
    p.add_argument("--currency", default="usd", help="Currency for portfolio report (default: usd)")
    p.add_argument("--no-report", action="store_true", help="Only insert balances; skip portfolio report print")
    args = p.parse_args(argv)

    init_db()

    account = args.account
    assets = [a.lower() for a in args.assets]

    # Default balances (used if --set not provided for a given asset)
    balances: Dict[str, float] = {
        "btc": 0.01,
        "eth": 0.2,
        "usdc": 150.0,
    }

    overrides = parse_set_kv(args.set) if args.set else {}
    balances.update(overrides)

    # Only insert balances for selected assets
    balances = {a: balances[a] for a in assets if a in balances}

    if not balances:
        raise RuntimeError("No balances to insert. Provide assets that exist in defaults or pass --set pairs.")

    ts = datetime.now(timezone.utc).isoformat()
    n = insert_balance_snapshot(ts=ts, account=account, balances=balances, source=args.source)
    print(f"Inserted {n} balance rows at {ts} for account={account}")

    latest = get_latest_balances(account=account, assets=assets)
    print("Latest balances:", latest)

    if args.no_report:
        return

    report = compute_portfolio_report(account=account, assets=assets, currency=args.currency)

    print(f"\nPortfolio positions ({args.currency.upper()}):")
    for a, pos in report.positions.items():
        print(
            " ", a,
            "amount=", round(pos.amount, 8),
            "price=", round(pos.price, 6),
            "value=", round(pos.value, 2),
            "balance_ts=", pos.balance_ts,
            "price_ts=", pos.price_ts,
        )

    if report.missing_prices:
        print("Missing prices for:", report.missing_prices)
    if report.missing_balances:
        print("Missing balances for:", report.missing_balances)

    print("Portfolio value:", round(report.total_value, 2), report.currency)
    print("Report generated_at:", report.generated_at)
    print("Balances updated:", report.balances_updated)
    print("Prices updated:", report.prices_updated)

    print("\nPer-asset change (since previous price snapshot):")
    for a, pos in report.positions.items():
        if pos.price_change is None:
            print(f"  {a}: n/a (need at least 2 price points)")
        else:
            print(f"  {a} price Δ: {pos.price_change:.4f} ({pos.price_change_pct:.2f}%) | value Δ: {pos.value_change:.2f}")

    if report.stale_prices:
        print("Stale prices:", report.stale_prices)

    print("Change label:", report.change_label)
    if report.total_change is None:
        print("Portfolio change: n/a (need at least 2 price points for all assets)")
    else:
        print(f"Portfolio change: {report.total_change:.2f} ({report.total_change_pct:.2f}%)")


if __name__ == "__main__":
    main()
