from db import init_db, get_portfolio_value_history

def main() -> None:
    init_db()

    account = "val-main"
    assets = ["btc", "eth", "usdc"]

    rows = get_portfolio_value_history(account=account, assets=assets, currency="usd", limit=10)

    print("== PORTFOLIO VALUE HISTORY (latest first) ==")
    print("ts | total_usd | missing_prices")
    print("--------------------------------")
    for ts, total, missing in rows:
        print(ts, "|", round(total, 2), "|", missing)

if __name__ == "__main__":
    main()
