from __future__ import annotations

from datetime import datetime, timezone
import argparse
from typing import List

from db import init_db, insert_portfolio_snapshot
from portfolio import compute_portfolio_report


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Write a portfolio total snapshot into SQLite")
    p.add_argument("--account", default="val-main", help="Account id (default: val-main)")
    p.add_argument("--currency", default="usd", help="Currency (default: usd)")
    p.add_argument("--assets", nargs="+", required=True, help="Assets list (e.g. btc eth usdc)")
    p.add_argument("--source", default="computed", help="Source label (default: computed)")
    args = p.parse_args(argv)

    init_db()

    report = compute_portfolio_report(account=args.account, assets=args.assets, currency=args.currency)
    ts = datetime.now(timezone.utc).isoformat()

    insert_portfolio_snapshot(
        ts=ts,
        account=args.account,
        currency=args.currency,
        total_value=report.total_value,
        source=args.source,
    )

    print(f"Inserted portfolio snapshot: {args.account} {report.total_value:.2f} {args.currency} at {ts}")


if __name__ == "__main__":
    main()