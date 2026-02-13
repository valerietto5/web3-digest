from __future__ import annotations

import argparse
from typing import List

from portfolio import compute_portfolio_report


def fmt_money(x: float | None, cur: str) -> str:
    if x is None:
        return "n/a"
    return f"{x:,.2f} {cur}"


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x:.2f}%"


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Wallet portfolio CLI")
    p.add_argument("--account", default="val-main", help="Account id (e.g. val-main)")
    p.add_argument("--currency", default="usd", help="Currency (usd/eur/...)")
    p.add_argument("--assets", nargs="+", default=["btc", "eth"], help="Assets list (e.g. btc eth usdc)")
    args = p.parse_args(argv)

    report = compute_portfolio_report(
        account=args.account,
        assets=args.assets,
        currency=args.currency,
    )

    print(f"Account: {report.account} | Currency: {report.currency}")
    print(f"Generated: {report.generated_at}")
    print(f"Balances updated: {report.balances_updated} | Prices updated: {report.prices_updated}")

    if report.stale_prices:
        print("Stale prices:", ", ".join(report.stale_prices))

    print("-" * 60)
    print("Total:", fmt_money(report.total_value, report.currency))

    # 24h portfolio
    if report.mtm_total_change_24h is None:
        print("24h change: n/a")
        if report.missing_24h_prices:
            print("24h note: need a baseline snapshot near 24h ago (within 30h tolerance).")

    else:
        sign = "+" if report.mtm_total_change_24h >= 0 else ""
        print(
            f"24h change: {sign}{fmt_money(report.mtm_total_change_24h, report.currency)} "
            f"({fmt_pct(report.mtm_total_change_pct_24h)})"
        )

    print("-" * 60)
    print("Positions:")
    for asset, pos in report.positions.items():
        line = (
            f"{asset:>5}  amt={pos.amount:<12g} "
            f"px={pos.price:<12g}  value={fmt_money(pos.value, report.currency)}"
        )

        # per-asset 24h (optional)
        if pos.price_change_pct_24h is None:
            line += "  | 24h: n/a"
        else:
            line += f"  | 24h: {fmt_pct(pos.price_change_pct_24h)}"

        print(line)

    if report.missing_balances:
        print("\nMissing balances:", ", ".join(report.missing_balances))
    if report.missing_prices:
        print("Missing prices:", ", ".join(report.missing_prices))
    if getattr(report, "missing_24h_prices", None):
        if report.missing_24h_prices:
            print("Missing 24h baseline:", ", ".join(report.missing_24h_prices))


if __name__ == "__main__":
    main()
