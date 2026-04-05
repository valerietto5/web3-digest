from __future__ import annotations

from datetime import datetime, timezone
import argparse
from typing import List

from db import (
    init_db,
    insert_price_snapshot,
    get_latest_prices,
    get_price_history,
    get_latest_price,
)
from wallet_helpers import fetch_prices


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Fetch prices and insert a price snapshot into SQLite")
    p.add_argument("--currency", default="usd", help="Currency (e.g. usd, eur)")
    p.add_argument("--assets", nargs="+", default=["btc", "eth", "usdc"], help="Assets (e.g. btc eth usdc)")
    p.add_argument("--source", default="coingecko", help="Source label to store in DB (default: coingecko)")
    p.add_argument("--limit", type=int, default=5, help="History rows to print for BTC (default: 5)")
    p.add_argument("--quiet", action="store_true", help="Only print insert confirmation")
    p.add_argument("--dex", action="store_true", help="Allow DexScreener fallback for allowlisted SPL tokens (USD only)")
    p.add_argument("--min-liquidity-usd", type=float, default=5000.0, help="Min liquidity (USD) for DexScreener fallback")
    args = p.parse_args(argv)

    init_db()

    currency = args.currency.lower()
    assets = []
    for a in args.assets:
        s = a.strip()
        if s.lower().startswith("spl:"):
            assets.append("spl:" + s.split(":", 1)[1])  # keep mint case
        else:
            assets.append(s.lower())


    prices_raw = fetch_prices(
        assets,
        currency=currency,
        allow_dexscreener=args.dex,
        min_liquidity_usd=args.min_liquidity_usd,
)

    # Flatten if it’s nested like {"btc": {"usd": 123}}
    prices = {}
    for asset, v in prices_raw.items():
        if isinstance(v, dict):
            prices[asset] = v.get(currency)
        else:
            prices[asset] = v

    # Drop missing values
    prices = {a: p for a, p in prices.items() if p is not None}

    if not prices:
        raise RuntimeError("No prices to insert (API failed, mapping issue, or currency mismatch).")

    ts = datetime.now(timezone.utc).isoformat()

    source_label = args.source
    if args.dex and args.source == "coingecko":
        source_label = "coingecko+dexscreener"

    n = insert_price_snapshot(ts=ts, prices=prices, currency=currency, source=source_label)
    print(f"Inserted {n} rows at {ts}")

    if args.quiet:
        return


    latest = get_latest_prices(assets, currency=currency)
    print("Latest:", latest)

    btc_latest = get_latest_price("btc", currency=currency)
    print("BTC latest (ts, price):", btc_latest)

    hist = get_price_history("btc", currency=currency, limit=args.limit)
    print("BTC history (latest first):")
    for t, pr in hist:
        print(" ", t, pr)


if __name__ == "__main__":
    main()
