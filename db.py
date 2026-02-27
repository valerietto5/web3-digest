from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from contextlib import contextmanager

@contextmanager
def open_conn(db_path: Path):
    con = get_conn(db_path)
    try:
        yield con
    finally:
        con.close()

DB_PATH = Path("wallet.db")


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Good defaults for a local app
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    with open_conn(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,              -- ISO timestamp string
                asset TEXT NOT NULL,           -- e.g. "btc"
                currency TEXT NOT NULL,        -- e.g. "eur"
                price REAL NOT NULL,
                source TEXT NOT NULL           -- e.g. "coingecko"
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_price_snapshots_lookup
            ON price_snapshots(asset, currency, ts);
            """
        )


        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS balance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                account TEXT NOT NULL,         -- e.g. "val-main" (later: a pubkey)
                asset TEXT NOT NULL,           -- "btc", "eth", "usdc"
                amount REAL NOT NULL,
                source TEXT NOT NULL           -- e.g. "manual", later: "solana-rpc"
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_balance_snapshots_lookup
            ON balance_snapshots(account, asset, ts);
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                account TEXT NOT NULL,
                currency TEXT NOT NULL,
                total_value REAL NOT NULL,
                source TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_lookup
            ON portfolio_snapshots (account, currency, ts);
            """
        )


def insert_price_snapshot(
    ts: str,
    prices: dict[str, float],
    currency: str,
    source: str = "coingecko",
    db_path: Path = DB_PATH,
) -> int:
    """
    Insert one snapshot row per asset. Returns number of rows inserted.
    """
    rows = [(ts, asset, currency, float(price), source) for asset, price in prices.items()]

    with open_conn(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO price_snapshots (ts, asset, currency, price, source)
            VALUES (?, ?, ?, ?, ?);
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def get_latest_prices(
    assets: Iterable[str],
    currency: str,
    db_path: Path = DB_PATH,
) -> dict[str, float]:
    """
    Returns latest known price per asset for the given currency.
    """
    assets = list(assets)
    if not assets:
        return {}

    placeholders = ",".join(["?"] * len(assets))
    params = [currency, *assets]

    sql = f"""
        SELECT ps.asset, ps.price
        FROM price_snapshots ps
        JOIN (
            SELECT asset, currency, MAX(ts) AS max_ts
            FROM price_snapshots
            WHERE currency = ?
              AND asset IN ({placeholders})
            GROUP BY asset, currency
        ) latest
        ON ps.asset = latest.asset
        AND ps.currency = latest.currency
        AND ps.ts = latest.max_ts;
    """

    out: dict[str, float] = {}
    with get_conn(db_path) as conn:
        for row in conn.execute(sql, params):
            out[row["asset"]] = float(row["price"])
    return out

def get_latest_prices_with_ts(
    assets: Iterable[str],
    currency: str,
    db_path: Path = DB_PATH,
) -> dict[str, tuple[str, float]]:
    assets = list(assets)
    if not assets:
        return {}

    placeholders = ",".join(["?"] * len(assets))
    params = [currency, *assets, currency]

    sql = f"""
        SELECT p.asset, p.ts, p.price
        FROM price_snapshots p
        JOIN (
            SELECT asset, MAX(ts) AS max_ts
            FROM price_snapshots
            WHERE currency = ?
              AND asset IN ({placeholders})
            GROUP BY asset
        ) latest
        ON p.asset = latest.asset
        AND p.ts = latest.max_ts
        WHERE p.currency = ?;
    """

    out: dict[str, tuple[str, float]] = {}
    with open_conn(db_path) as conn:
        for row in conn.execute(sql, params):
            out[row["asset"]] = (row["ts"], float(row["price"]))
    return out


def get_price_history(
    asset: str,
    currency: str,
    limit: int = 10,
    db_path: Path = DB_PATH,
) -> list[tuple[str, float]]:
    """
    Returns (ts, price) newest-first.
    """
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT ts, price
            FROM price_snapshots
            WHERE asset = ?
              AND currency = ?
            ORDER BY ts DESC
            LIMIT ?;
            """,
            (asset, currency, limit),
        ).fetchall()

    return [(r["ts"], float(r["price"])) for r in rows]


def get_portfolio_value_history(
    account: str,
    assets: Iterable[str],
    currency: str = "usd",
    limit: int = 20,
    db_path: Path = DB_PATH,
) -> list[tuple[str, float, int]]:
    """
    Returns rows: (balance_ts, total_value, missing_prices_count)

    total_value is computed using the latest price snapshot at or before balance_ts.
    missing_prices_count tells you how many asset rows had no price available at that time.
    """
    assets = list(assets)
    if not assets:
        return []

    placeholders = ",".join(["?"] * len(assets))

    sql = f"""
        SELECT
            b.ts AS ts,
            SUM(b.amount * (
                SELECT p.price
                FROM price_snapshots p
                WHERE p.asset = b.asset
                  AND p.currency = ?
                  AND p.ts <= b.ts
                ORDER BY p.ts DESC
                LIMIT 1
            )) AS total_value,
            COUNT(*) - COUNT((
                SELECT p.price
                FROM price_snapshots p
                WHERE p.asset = b.asset
                  AND p.currency = ?
                  AND p.ts <= b.ts
                ORDER BY p.ts DESC
                LIMIT 1
            )) AS missing_prices
        FROM balance_snapshots b
        WHERE b.account = ?
          AND b.asset IN ({placeholders})
        GROUP BY b.ts
        ORDER BY b.ts DESC
        LIMIT ?;
    """

    params = [currency, currency, account, *assets, limit]

    out: list[tuple[str, float, int]] = []
    with get_conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        for row in rows:
            ts = row["ts"]
            total = row["total_value"]
            missing = row["missing_prices"]
            out.append((ts, float(total) if total is not None else 0.0, int(missing)))
    return out


def insert_portfolio_snapshot(
    ts: str,
    account: str,
    currency: str,
    total_value: float,
    source: str = "computed",
    db_path: Path = DB_PATH,
) -> int:
    con = get_conn(db_path)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO portfolio_snapshots (ts, account, currency, total_value, source)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ts, account, currency, float(total_value), source),
    )
    con.commit()
    return int(cur.rowcount)


def get_portfolio_snapshot_history(
    account: str,
    currency: str,
    limit: int = 10,
    db_path: Path = DB_PATH,
) -> list[tuple[str, float, str]]:
    """
    Returns list of (ts, total_value, source), newest first.
    """
    con = get_conn(db_path)
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT ts, total_value, source
        FROM portfolio_snapshots
        WHERE account = ? AND currency = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        (account, currency, int(limit)),
    ).fetchall()
    return [(str(ts), float(tv), str(src)) for (ts, tv, src) in rows]




def get_latest_price(asset: str, currency: str, db_path: Path = DB_PATH) -> tuple[str, float] | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT ts, price
            FROM price_snapshots
            WHERE asset = ? AND currency = ?
            ORDER BY ts DESC
            LIMIT 1;
            """,
            (asset, currency),
        ).fetchone()

    if row is None:
        return None
    return (row["ts"], float(row["price"]))


def get_price_at_or_before(
    asset: str,
    currency: str,
    ts: str,
    db_path: Path = DB_PATH,
) -> tuple[str, float] | None:
    """
    Returns the latest (ts, price) where snapshot ts <= given ts.
    Useful for "24h ago" comparisons when you don't have an exact snapshot at that time.
    """
    with open_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT ts, price
            FROM price_snapshots
            WHERE asset = ?
              AND currency = ?
              AND ts <= ?
            ORDER BY ts DESC
            LIMIT 1;
            """,
            (asset, currency, ts),
        ).fetchone()

    if row is None:
        return None
    return (row["ts"], float(row["price"]))



def insert_balance_snapshot(ts: str, account: str, balances: dict[str, float], source: str = "manual", db_path: Path = DB_PATH) -> int:
    rows = [(ts, account, asset, float(amount), source) for asset, amount in balances.items()]
    with open_conn(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO balance_snapshots (ts, account, asset, amount, source)
            VALUES (?, ?, ?, ?, ?);
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def get_latest_balances(account: str, assets: Iterable[str], db_path: Path = DB_PATH) -> dict[str, float]:
    assets = list(assets)
    if not assets:
        return {}

    placeholders = ",".join(["?"] * len(assets))
    params = [account, *assets]

    sql = f"""
        SELECT bs.asset, bs.amount
        FROM balance_snapshots bs
        JOIN (
            SELECT account, asset, MAX(ts) AS max_ts
            FROM balance_snapshots
            WHERE account = ?
              AND asset IN ({placeholders})
            GROUP BY account, asset
        ) latest
        ON bs.account = latest.account
        AND bs.asset = latest.asset
        AND bs.ts = latest.max_ts;
    """

    out: dict[str, float] = {}
    with get_conn(db_path) as conn:
        for row in conn.execute(sql, params):
            out[row["asset"]] = float(row["amount"])
    return out


def get_latest_balances_with_ts(
    account: str,
    assets: Iterable[str],
    db_path: Path = DB_PATH,
) -> dict[str, tuple[str, float]]:
    assets = list(assets)
    if not assets:
        return {}

    placeholders = ",".join(["?"] * len(assets))
    params = [account, *assets, account]

    sql = f"""
        SELECT b.asset, b.ts, b.amount
        FROM balance_snapshots b
        JOIN (
            SELECT asset, MAX(ts) AS max_ts
            FROM balance_snapshots
            WHERE account = ?
              AND asset IN ({placeholders})
            GROUP BY asset
        ) latest
        ON b.asset = latest.asset
        AND b.ts = latest.max_ts
        WHERE b.account = ?;
    """

    out: dict[str, tuple[str, float]] = {}
    with open_conn(db_path) as conn:
        for row in conn.execute(sql, params):
            out[row["asset"]] = (row["ts"], float(row["amount"]))
    return out



def get_latest_balance(account: str, asset: str, db_path: Path = DB_PATH) -> tuple[str, float] | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT ts, amount
            FROM balance_snapshots
            WHERE account = ? AND asset = ?
            ORDER BY ts DESC
            LIMIT 1;
            """,
            (account, asset),
        ).fetchone()

    if row is None:
        return None
    return (row["ts"], float(row["amount"]))

