import unittest
import tempfile
from pathlib import Path

from db import (
    init_db,
    insert_price_snapshot,
    get_latest_prices_with_ts,
    get_price_at_or_before,
    insert_balance_snapshot,
    get_latest_balances_with_ts,
)

class TestSanity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_wallet.db"
        init_db(db_path=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_insert_and_get_latest_prices_with_ts(self):
        t1 = "2026-02-25T00:00:00+00:00"
        t2 = "2026-02-25T01:00:00+00:00"
        insert_price_snapshot(ts=t1, prices={"btc": 100.0}, currency="usd", source="test", db_path=self.db_path)
        insert_price_snapshot(ts=t2, prices={"btc": 110.0}, currency="usd", source="test", db_path=self.db_path)

        latest = get_latest_prices_with_ts(assets=["btc"], currency="usd", db_path=self.db_path)
        self.assertIn("btc", latest)
        ts, px = latest["btc"]
        self.assertEqual(ts, t2)
        self.assertEqual(px, 110.0)

    def test_get_price_at_or_before(self):
        t1 = "2026-02-25T00:00:00+00:00"
        t2 = "2026-02-25T01:00:00+00:00"
        insert_price_snapshot(ts=t1, prices={"btc": 100.0}, currency="usd", source="test", db_path=self.db_path)
        insert_price_snapshot(ts=t2, prices={"btc": 110.0}, currency="usd", source="test", db_path=self.db_path)

        target = "2026-02-25T00:30:00+00:00"
        row = get_price_at_or_before("btc", "usd", target, db_path=self.db_path)
        self.assertIsNotNone(row)
        ts, px = row
        self.assertEqual(ts, t1)
        self.assertEqual(px, 100.0)

    def test_insert_and_get_latest_balances_with_ts(self):
        t1 = "2026-02-25T00:00:00+00:00"
        insert_balance_snapshot(ts=t1, account="test", balances={"btc": 0.5}, source="manual", db_path=self.db_path)

        latest = get_latest_balances_with_ts(account="test", assets=["btc"], db_path=self.db_path)
        self.assertIn("btc", latest)
        ts, amt = latest["btc"]
        self.assertEqual(ts, t1)
        self.assertEqual(amt, 0.5)

if __name__ == "__main__":
    unittest.main()