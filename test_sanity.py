import unittest
import tempfile
from pathlib import Path
from api.main import (
    _is_executable_quote_option,
    _normalize_raydium_quote_option,
    _rank_quote_options,
    _select_diverse_other_options,
)

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

    def test_normalize_raydium_quote_option_marks_comparison_only(self):
        quote = {
            "success": True,
            "data": {
                "inputMint": "So11111111111111111111111111111111111111112",
                "inputAmount": "1000000000",
                "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "outputAmount": "13738391",
                "otherAmountThreshold": "13669699",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [
                    {
                        "inputMint": "So11111111111111111111111111111111111111112",
                        "inputAmount": "1000000000",
                        "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                        "outputAmount": "13738391",
                        "feeMint": "So11111111111111111111111111111111111111112",
                        "feeAmount": "10000",
                    }
                ],
            },
        }

        option = _normalize_raydium_quote_option(
            variant_id="raydium_quote",
            label="Via Raydium",
            kind="alternative",
            quote=quote,
            from_token="SOL",
            to_token="USDC",
            input_amount=1.0,
            input_amount_raw=1000000000,
            output_decimals=6,
        )

        self.assertEqual(option["provider"], "raydium-trade-api")
        self.assertEqual(option["execution_surface_label"], "Raydium")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertEqual(option["route_label"], "Raydium")
        self.assertEqual(option["route_step_count"], 1)
        self.assertEqual(option["estimated_output_raw"], "13738391")
        self.assertEqual(option["min_received_raw"], "13669699")

    def test_rank_quote_options_allows_comparison_only_best_quote(self):
        jupiter_option = {
            "variant_id": "recommended_default",
            "provider": "jupiter-metis",
            "execution_surface_label": "Jupiter",
            "is_comparison_only": False,
            "is_clickable": True,
            "estimated_output_raw": "100",
            "route_labels": ["Orca"],
            "protections": {"only_direct_routes": False, "restrict_intermediate_tokens": True},
            "_sort_out_amount_raw": 100,
        }
        raydium_option = {
            "variant_id": "raydium_quote",
            "provider": "raydium-trade-api",
            "execution_surface_label": "Raydium",
            "is_comparison_only": True,
            "is_clickable": False,
            "estimated_output_raw": "110",
            "route_labels": ["Raydium"],
            "protections": {"slippage_bps": 50},
            "_sort_out_amount_raw": 110,
        }

        ranked = _rank_quote_options([jupiter_option, raydium_option])

        self.assertEqual(ranked[0]["variant_id"], "raydium_quote")
        self.assertFalse(_is_executable_quote_option(ranked[0]))
        self.assertTrue(_is_executable_quote_option(ranked[1]))

    def test_diverse_other_options_do_not_crowd_out_raydium(self):
        recommended_jupiter = {
            "variant_id": "recommended_default",
            "provider": "jupiter-metis",
            "execution_surface_label": "Jupiter",
            "estimated_output_raw": "120",
            "route_labels": ["Orca"],
            "protections": {"restrict_intermediate_tokens": True},
            "_sort_out_amount_raw": 120,
        }
        better_jupiter_variant = {
            "variant_id": "broader_search",
            "provider": "jupiter-metis",
            "execution_surface_label": "Jupiter",
            "estimated_output_raw": "119",
            "route_labels": ["Meteora DLMM"],
            "protections": {"restrict_intermediate_tokens": False},
            "_sort_out_amount_raw": 119,
        }
        another_jupiter_variant = {
            "variant_id": "exclude_recommended_dexes",
            "provider": "jupiter-metis",
            "execution_surface_label": "Jupiter",
            "estimated_output_raw": "118",
            "route_labels": ["Lifinity"],
            "protections": {"restrict_intermediate_tokens": True},
            "_sort_out_amount_raw": 118,
        }
        raydium_option = {
            "variant_id": "raydium_quote",
            "provider": "raydium-trade-api",
            "execution_surface_label": "Raydium",
            "estimated_output_raw": "117",
            "route_labels": ["Raydium"],
            "protections": {"slippage_bps": 50},
            "_sort_out_amount_raw": 117,
        }

        ranked = _rank_quote_options(
            [
                recommended_jupiter,
                better_jupiter_variant,
                another_jupiter_variant,
                raydium_option,
            ]
        )
        other_options = _select_diverse_other_options(
            ranked,
            best_quote=recommended_jupiter,
            recommended=recommended_jupiter,
            limit=2,
        )

        self.assertEqual(other_options[0]["variant_id"], "raydium_quote")
        self.assertEqual(
            len({(opt["provider"], opt["execution_surface_label"]) for opt in other_options}),
            len(other_options),
        )

if __name__ == "__main__":
    unittest.main()
