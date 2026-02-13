import sqlite3
from pathlib import Path

DB_PATH = Path("wallet.db")

def print_rows(rows, max_rows=20):
    rows = list(rows)
    if not rows:
        print("(no rows)")
        return
    cols = rows[0].keys()
    print(" | ".join(cols))
    print("-" * (len(" | ".join(cols))))
    for r in rows[:max_rows]:
        print(" | ".join(str(r[c]) for c in cols))

def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB file not found: {DB_PATH.resolve()}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1) List tables
    print("\n== TABLES ==")
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()
    for t in tables:
        print("-", t["name"])

    # 2) Show schema for price_snapshots
    print("\n== SCHEMA: price_snapshots ==")
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='price_snapshots';"
    ).fetchone()
    print(schema["sql"] if schema else "(missing table)")

    print("\n== SCHEMA: balance_snapshots ==")
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='balance_snapshots';"
    ).fetchone()
    print(schema["sql"] if schema else "(missing table)")


    # 3) Show last 10 price rows
    print("\n== LAST 10 ROWS: price_snapshots ==")
    rows = conn.execute(
        """
        SELECT ts, asset, currency, price, source
        FROM price_snapshots
        ORDER BY ts DESC
        LIMIT 10;
        """
    ).fetchall()
    print_rows(rows)

    # 4) Counts per asset/currency (quick sanity)
    print("\n== COUNTS BY asset/currency ==")
    rows = conn.execute(
        """
        SELECT asset, currency, COUNT(*) AS n
        FROM price_snapshots
        GROUP BY asset, currency
        ORDER BY n DESC;
        """
    ).fetchall()
    print_rows(rows)

    print("\n== LAST 10 ROWS: balance_snapshots ==")
    rows = conn.execute(
        """
        SELECT ts, account, asset, amount, source
        FROM balance_snapshots
        ORDER BY ts DESC
        LIMIT 10;
        """
    ).fetchall()
    print_rows(rows)

    print("\n== COUNTS BY account/asset ==")
    rows = conn.execute(
        """
        SELECT account, asset, COUNT(*) AS n
        FROM balance_snapshots
        GROUP BY account, asset
        ORDER BY n DESC;
        """
    ).fetchall()
    print_rows(rows)

    print("\n== BTC USD PRICE HISTORY (latest 8) ==")
    rows = conn.execute(
        """
        SELECT ts, price
        FROM price_snapshots
        WHERE asset = 'btc' AND currency = 'usd'
        ORDER BY ts DESC
        LIMIT 8;
        """
    ).fetchall()
    print_rows(rows)

    print("\n== BALANCES for val-main (latest 9 rows) ==")
    rows = conn.execute(
        """
        SELECT ts, asset, amount
        FROM balance_snapshots
        WHERE account = 'val-main'
        ORDER BY ts DESC
        LIMIT 9;
        """
    ).fetchall()
    print_rows(rows)

    print("\n== BALANCE SNAPSHOT MOMENTS (count distinct ts) ==")
    rows = conn.execute(
        """
        SELECT account, COUNT(DISTINCT ts) AS snapshot_moments
        FROM balance_snapshots
        GROUP BY account;
        """
    ).fetchall()
    print_rows(rows)




    conn.close()

if __name__ == "__main__":
    main()
