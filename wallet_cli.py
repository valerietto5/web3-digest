from __future__ import annotations

import argparse
from typing import List
import json
from pathlib import Path
import csv


from portfolio import compute_portfolio_report

def load_accounts(path: str = "accounts.json") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Error: {path} is not valid JSON: {e}")

def save_accounts(data: dict, path: str = "accounts.json") -> None:
    p = Path(path)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")




def display_asset(asset: str) -> str:
    """
    Convert internal asset keys into human-friendly labels.
    """
    if asset == "sol":
        return "SOL"
    if asset == "usdc":
        return "USDC"

    if asset.startswith("spl:"):
        mint = asset.split(":", 1)[1]
        try:
            from token_registry import TOKENS
            meta = TOKENS.get(mint)
            if meta and meta.get("symbol"):
                return str(meta["symbol"])
        except Exception:
            pass

        # fallback: shorten mint
        return f"SPL:{mint[:4]}…{mint[-4:]}"

    return asset.upper()



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
    p.add_argument("--list-accounts", action="store_true", help="List saved accounts and exit")
    p.add_argument("--account", default="val-main", help="Account id (e.g. val-main)")
    p.add_argument("--currency", default="usd", help="Currency (usd/eur/...)")
    p.add_argument("--assets", nargs="*", default=None, help="Assets to include (default: from accounts.json)")
    p.add_argument("--show-unpriced", action="store_true", help="List unpriced SPL tokens")
    p.add_argument("--swap-from", help="Generate a Jupiter swap link (from asset)")
    p.add_argument("--swap-to", help="Generate a Jupiter swap link (to asset)")
    p.add_argument("--save-account", help="Save/update an account in accounts.json and exit")
    p.add_argument("--address", help="Wallet address (used with --save-account)")
    p.add_argument("--chain", default="solana", help="Chain label for saved account (default: solana)")
    p.add_argument("--history", type=int, help="Print last N portfolio snapshots and exit")
    p.add_argument("--json", action="store_true", help="Export latest portfolio report to exports/portfolio_latest.json")
    p.add_argument("--csv", action="store_true", help="Export latest positions to exports/portfolio_latest.csv")
    p.add_argument("--outdir", default="exports", help="Output folder for exports (default: exports)")


    args = p.parse_args(argv)

    if args.list_accounts:
        accounts = load_accounts()
        if not accounts:
            print("No saved accounts. Create accounts.json first.")
            return

        print("Saved accounts:")
        for name, meta in accounts.items():
            chain = meta.get("chain", "?")
            addr = meta.get("address")
            addr_short = addr[:4] + "…" + addr[-4:] if isinstance(addr, str) and len(addr) > 10 else str(addr)
            defaults = meta.get("default_assets", [])
            print(f"  - {name}  chain={chain}  address={addr_short}  default_assets={defaults}")
        return

    if args.save_account:
        if not args.address:
            raise SystemExit("Error: --address is required with --save-account")

        accounts = load_accounts()
        accounts[args.save_account] = {
            "chain": args.chain,
            "address": args.address,
            "default_assets": args.assets if args.assets else ["sol", "usdc"],
        }
        save_accounts(accounts)
        print(f"Saved account '{args.save_account}' to accounts.json")
        return

    if args.history:
        from db import get_portfolio_snapshot_history
        rows = get_portfolio_snapshot_history(account=args.account, currency=args.currency, limit=args.history)
        if not rows:
            print("No portfolio snapshots yet. Run run_portfolio_history.py first.")
            return
        print(f"Portfolio history (last {args.history}) for {args.account} {args.currency}:")
        for ts, total, src in rows:
            print(f"  {ts}  total={fmt_money(total, args.currency)}  source={src}")
        return
    


    if args.swap_from and args.swap_to:
        url = f"https://jup.ag/swap/{args.swap_from.upper()}-{args.swap_to.upper()}"

        accounts = load_accounts()
        meta = accounts.get(args.account, {})
        addr = meta.get("address")

        print("Swap (V0 redirect):", url)
        if addr:
            print("Account address:", addr)
        return



    assets = args.assets
    assets_source = "CLI"

    if assets is None or len(assets) == 0:
        accounts = load_accounts()
        meta = accounts.get(args.account, {})
        assets = meta.get("default_assets", [])
        assets_source = "accounts.json"
        if not assets:
            raise SystemExit("Error: no --assets provided and no default_assets found for this account.")

    print(f"Assets: {', '.join(assets)}  (source: {assets_source})")


    report = compute_portfolio_report(
        account=args.account,
        assets=assets,
        currency=args.currency,
    )

    # Exports
    if args.json or args.csv:
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)

        # JSON export (full report)
        if args.json:
            payload = {
                "generated_at": report.generated_at,
                "account": report.account,
                "currency": report.currency,
                "total_value": report.total_value,
                "balances_updated": report.balances_updated,
                "prices_updated": report.prices_updated,
                "stale_prices": report.stale_prices,
                "missing_balances": report.missing_balances,
                "missing_prices": report.missing_prices,
                "missing_24h_baseline": getattr(report, "missing_24h_prices", []),
                "positions": [
                    {
                        "asset": a,
                        "label": display_asset(a),
                        "amount": p.amount,
                        "price": p.price,
                        "value": p.value,
                        "balance_ts": p.balance_ts,
                        "price_ts": p.price_ts,
                        "price_change_pct_24h": p.price_change_pct_24h,
                        "baseline_24h_valid": getattr(p, "baseline_24h_valid", False),
                    }
                    for a, p in report.positions.items()
                ],
            }

            json_path = outdir / "portfolio_latest.json"
            json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Exported JSON: {json_path}")

        # CSV export (positions table)
        if args.csv:
            csv_path = outdir / "portfolio_latest.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "asset",
                        "label",
                        "amount",
                        "price",
                        "value",
                        "balance_ts",
                        "price_ts",
                        "price_change_pct_24h",
                        "baseline_24h_valid",
                    ]
                )
                for a, p in report.positions.items():
                    w.writerow(
                        [
                            a,
                            display_asset(a),
                            p.amount,
                            p.price,
                            p.value,
                            p.balance_ts,
                            p.price_ts,
                            p.price_change_pct_24h,
                            getattr(p, "baseline_24h_valid", False),
                        ]
                    )
            print(f"Exported CSV: {csv_path}")
    

    print(f"Account: {report.account} | Currency: {report.currency}")
    print(f"Generated: {report.generated_at}")
    print(f"Balances updated: {report.balances_updated} | Prices updated: {report.prices_updated}")

    if report.stale_prices:
        pretty_stale = [display_asset(a) for a in report.stale_prices]
        print("Stale prices:", ", ".join(pretty_stale))
        print("Tip: run run_prices_to_db.py to refresh price snapshots.")

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
        label = display_asset(asset)
        line = (
            f"{label:>5}  amt={pos.amount:<12g} "
            f"px={pos.price:<12g}  value={fmt_money(pos.value, report.currency)}"
        )

        # per-asset 24h (optional)
        if pos.price_change_pct_24h is None:
            line += "  | 24h: n/a"
        else:
            line += f"  | 24h: {fmt_pct(pos.price_change_pct_24h)}"

        print(line)

    if report.missing_balances:
        pretty_missing = [display_asset(a) for a in report.missing_balances]
        print("\nMissing balances:", ", ".join(pretty_missing))
    if report.missing_prices:
        unpriced_spl = [a for a in report.missing_prices if a.startswith("spl:")]
        missing_other = [a for a in report.missing_prices if not a.startswith("spl:")]

        if missing_other:
            print("Missing prices:", ", ".join(missing_other))

        if unpriced_spl:
            if args.show_unpriced:
                pretty_unpriced = [display_asset(a) for a in unpriced_spl]
                print("Unpriced SPL tokens:", ", ".join(pretty_unpriced))

            else:
                print(f"Unpriced SPL tokens: {len(unpriced_spl)} (use --show-unpriced to list)")



    if getattr(report, "missing_24h_prices", None):
        if report.missing_24h_prices:
            pretty_24h = [display_asset(a) for a in report.missing_24h_prices]
            print("Missing 24h baseline:", ", ".join(pretty_24h))


if __name__ == "__main__":
    main()
