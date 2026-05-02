import unittest
import tempfile
import json
import subprocess
from pathlib import Path
from unittest.mock import patch
from api.main import (
    METEORA_DLMM_SOL_MINT,
    METEORA_DLMM_USDC_MINT,
    _build_meteora_dlmm_quote_payload,
    _build_orca_whirlpool_quote_payload,
    _build_phantom_quote_payload,
    _build_phoenix_quote_payload,
    _fetch_meteora_dlmm_quote,
    _fetch_orca_whirlpool_quote,
    _fetch_phantom_quote,
    _fetch_phoenix_quote,
    _is_executable_quote_option,
    _normalize_meteora_dlmm_quote_option,
    _normalize_orca_whirlpool_quote_option,
    _normalize_phantom_quote_option,
    _normalize_phoenix_quote_option,
    _normalize_raydium_quote_option,
    _rank_quote_options,
    _build_reference_baseline_from_resolved_prices,
    _resolve_quote_benchmark_prices_usd,
    _resolve_swap_token_meta,
    _select_direct_route_option,
    _select_diverse_other_options,
    _try_fetch_meteora_dlmm_quote,
    _try_fetch_orca_whirlpool_quote,
    _try_fetch_phantom_quote,
    _try_fetch_phoenix_quote,
    swap_quote,
    swap_tokens,
)
from api.ui_page import build_ui_html

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

    def test_swap_registry_resolves_sol_usdc_and_bonk(self):
        sol = _resolve_swap_token_meta("SOL")
        usdc = _resolve_swap_token_meta("USDC")
        bonk = _resolve_swap_token_meta("BONK")

        self.assertEqual(sol["mint"], "So11111111111111111111111111111111111111112")
        self.assertEqual(sol["decimals"], 9)
        self.assertEqual(usdc["mint"], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.assertEqual(usdc["decimals"], 6)
        self.assertEqual(bonk["mint"], "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
        self.assertEqual(bonk["decimals"], 5)
        self.assertEqual(bonk["coingecko_id"], "bonk")

    def test_swap_tokens_returns_default_enabled_registry_tokens(self):
        response = swap_tokens()
        self.assertTrue(response["ok"])

        by_symbol = {token["symbol"]: token for token in response["tokens"]}
        self.assertEqual(by_symbol["SOL"]["decimals"], 9)
        self.assertEqual(by_symbol["USDC"]["decimals"], 6)
        self.assertEqual(by_symbol["BONK"]["mint"], "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
        self.assertEqual(by_symbol["BONK"]["display_name"], "Bonk")
        self.assertTrue(by_symbol["BONK"]["default_enabled"])
        self.assertTrue(by_symbol["BONK"]["verified"])
        self.assertNotIn("USDT", by_symbol)

    def test_bonk_reference_prices_prefer_dexscreener(self):
        class Pair:
            price_usd = 0.000006
            liquidity_usd = 100000.0
            url = "https://dexscreener.com/solana/example"

        with (
            patch("dexscreener.fetch_best_pair_price_usd_solana", return_value=Pair()),
            patch("api.main._fetch_jupiter_price_v3_reference_prices_usd", return_value={}),
            patch("api.main._fetch_coingecko_reference_prices_usd", return_value={}),
        ):
            prices = _resolve_quote_benchmark_prices_usd(["BONK"])

        self.assertEqual(prices["BONK"]["usd"], 0.000006)
        self.assertEqual(prices["BONK"]["pricing_source"], "dexscreener_solana")

    def test_reference_baseline_delta_includes_token_and_usd_difference(self):
        baseline, delta = _build_reference_baseline_from_resolved_prices(
            from_token="SOL",
            to_token="BONK",
            amount=10.0,
            best_output_amount=134778455.36,
            from_row={"usd": 83.61077, "pricing_source": "coingecko_simple_price"},
            to_row={"usd": 0.00000619385, "pricing_source": "dexscreener_solana"},
        )

        self.assertEqual(baseline["pricing_source"], "dexscreener_solana")
        self.assertEqual(delta["output_token"], "BONK")
        self.assertEqual(delta["pricing_source"], "dexscreener_solana")
        self.assertAlmostEqual(
            delta["output_diff_usd"],
            delta["output_diff_abs"] * 0.00000619385,
            places=9,
        )

    def test_swap_ui_reference_delta_renders_source_token_and_usd_labels(self):
        html = build_ui_html()

        self.assertIn("Best executable output vs ", html)
        self.assertIn("DexScreener reference", html)
        self.assertIn("CoinGecko reference", html)
        self.assertIn("Jupiter reference", html)
        self.assertIn("fmtUsdCost(rawUsd)", html)
        self.assertIn("fmtUsdCost(tradeCostUsd)", html)

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
        self.assertEqual(option["quote_status"], "live")
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_trade_api")
        self.assertEqual(option["cost_transparency"]["ranking_basis"], "highest_receive_amount")
        self.assertEqual(
            option["cost_transparency"]["network_fee_scope"],
            "unavailable_for_quote_only_preview",
        )
        self.assertTrue(option["cost_transparency"]["explicit_fees_may_be_reflected_in_output"])
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

    def test_build_meteora_dlmm_quote_payload_adds_sol_usdc_candidate(self):
        payload = _build_meteora_dlmm_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_USDC_MINT,
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["rpc_url"], "https://example.invalid")
        self.assertEqual(payload["amount_raw"], "1000000000")
        self.assertEqual(len(payload["pool_candidates"]), 1)
        self.assertEqual(
            payload["pool_candidates"][0]["address"],
            "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
        )

    def test_fetch_meteora_dlmm_quote_uses_subprocess_json_contract(self):
        helper_output = {
            "ok": True,
            "provider": "meteora_dlmm",
            "out_amount_raw": "84000000",
        }

        def fake_run(cmd, **kwargs):
            self.assertIn("tools/meteora_dlmm_quote.mjs", cmd[1])
            self.assertEqual(json.loads(kwargs["input"])["amount_raw"], "1000000000")
            self.assertFalse(kwargs.get("shell", False))
            self.assertGreater(kwargs["timeout"], 0)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(helper_output), "")

        with patch("api.main.subprocess.run", side_effect=fake_run):
            result = _fetch_meteora_dlmm_quote({"amount_raw": "1000000000"})

        self.assertEqual(result, helper_output)

    def test_try_fetch_meteora_dlmm_quote_handles_timeout(self):
        with patch("api.main.subprocess.run", side_effect=subprocess.TimeoutExpired("node", 20)):
            result = _try_fetch_meteora_dlmm_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 504)

    def test_build_orca_whirlpool_quote_payload_supports_sol_usdc_only(self):
        payload = _build_orca_whirlpool_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_USDC_MINT,
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["rpc_url"], "https://example.invalid")
        self.assertEqual(payload["amount_raw"], "1000000000")
        self.assertEqual(payload["pool_candidates"], [])
        self.assertNotIn("unsupported_pair", payload)

    def test_fetch_orca_whirlpool_quote_uses_subprocess_json_contract(self):
        helper_output = {
            "ok": True,
            "provider": "orca_whirlpool",
            "out_amount_raw": "84000000",
        }

        def fake_run(cmd, **kwargs):
            self.assertIn("tools/orca_whirlpool_quote_research.mjs", cmd[1])
            self.assertEqual(json.loads(kwargs["input"])["amount_raw"], "1000000000")
            self.assertFalse(kwargs.get("shell", False))
            self.assertGreater(kwargs["timeout"], 0)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(helper_output), "")

        with patch("api.main.subprocess.run", side_effect=fake_run):
            result = _fetch_orca_whirlpool_quote({"amount_raw": "1000000000"})

        self.assertEqual(result, helper_output)

    def test_try_fetch_orca_whirlpool_quote_handles_timeout(self):
        with patch("api.main.subprocess.run", side_effect=subprocess.TimeoutExpired("node", 20)):
            result = _try_fetch_orca_whirlpool_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 504)

    def test_try_fetch_orca_whirlpool_quote_handles_missing_helper(self):
        with patch("api.main.Path.exists", return_value=False):
            result = _try_fetch_orca_whirlpool_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 502)
        self.assertIn("helper missing", result["error"]["detail"])

    def test_build_phoenix_quote_payload_adds_sol_usdc_market(self):
        payload = _build_phoenix_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_USDC_MINT,
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["rpc_url"], "https://example.invalid")
        self.assertEqual(payload["amount_raw"], "1000000000")
        self.assertEqual(len(payload["market_candidates"]), 1)
        self.assertEqual(
            payload["market_candidates"][0]["address"],
            "4DoNfFBfF7UokCC2FQzriy7yHK6DY6NVdYpuekQ5pRgg",
        )

    def test_fetch_phoenix_quote_uses_subprocess_json_contract(self):
        helper_output = {
            "ok": True,
            "provider": "phoenix",
            "out_amount_raw": "83000000",
        }

        def fake_run(cmd, **kwargs):
            self.assertIn("tools/phoenix_quote_research.mjs", cmd[1])
            self.assertEqual(json.loads(kwargs["input"])["amount_raw"], "1000000000")
            self.assertFalse(kwargs.get("shell", False))
            self.assertGreater(kwargs["timeout"], 0)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(helper_output), "")

        with patch("api.main.subprocess.run", side_effect=fake_run):
            result = _fetch_phoenix_quote({"amount_raw": "1000000000"})

        self.assertEqual(result, helper_output)

    def test_try_fetch_phoenix_quote_handles_timeout(self):
        with patch("api.main.subprocess.run", side_effect=subprocess.TimeoutExpired("node", 20)):
            result = _try_fetch_phoenix_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 504)

    def test_try_fetch_phoenix_quote_handles_missing_helper(self):
        with patch("api.main.Path.exists", return_value=False):
            result = _try_fetch_phoenix_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 502)
        self.assertIn("helper missing", result["error"]["detail"])

    def test_build_phantom_quote_payload_uses_wallet_as_taker(self):
        payload = _build_phantom_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_USDC_MINT,
            amount_raw=1000000000,
            slippage_bps=50,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertEqual(payload["sell_chain_id"], "solana:mainnet")
        self.assertTrue(payload["sell_token_is_native"])
        self.assertEqual(payload["buy_token_mint"], METEORA_DLMM_USDC_MINT)
        self.assertEqual(payload["amount"], "1000000000")
        self.assertEqual(payload["amount_unit"], "base")
        self.assertEqual(payload["slippage_bps"], 50)
        self.assertEqual(payload["taker_address"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertNotIn("unsupported_pair", payload)
        self.assertNotIn("skip_reason", payload)

    def test_fetch_phantom_quote_uses_subprocess_json_contract(self):
        helper_output = {
            "ok": True,
            "status_code": 200,
            "quoteRequest": {"sellAmount": "1000000000"},
            "quoteResponse": {
                "quotes": [
                    {
                        "buyAmount": "83843388",
                        "baseProvider": {"id": "okx", "name": "OKX"},
                    }
                ]
            },
            "first_quote_buyAmount": "83843388",
        }

        def fake_run(cmd, **kwargs):
            self.assertIn("tools/phantom_quote_research.mjs", cmd[1])
            self.assertEqual(json.loads(kwargs["input"])["taker_address"], "wallet")
            self.assertFalse(kwargs.get("shell", False))
            self.assertGreater(kwargs["timeout"], 0)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(helper_output), "")

        with patch("api.main.subprocess.run", side_effect=fake_run):
            result = _fetch_phantom_quote(
                {
                    "sell_chain_id": "solana:mainnet",
                    "sell_token_is_native": True,
                    "buy_token_mint": METEORA_DLMM_USDC_MINT,
                    "amount": "1000000000",
                    "amount_unit": "base",
                    "slippage_bps": 50,
                    "taker_address": "wallet",
                }
            )

        self.assertEqual(result["first_quote_buyAmount"], "83843388")
        self.assertEqual(result["quoteResponse"]["quotes"][0]["baseProvider"]["name"], "OKX")

    def test_try_fetch_phantom_quote_skips_without_wallet(self):
        payload = _build_phantom_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_USDC_MINT,
            amount_raw=1000000000,
            user_public_key=None,
        )

        result = _try_fetch_phantom_quote(payload)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 400)
        self.assertIn("user_public_key", result["error"]["detail"])

    def test_try_fetch_phantom_quote_handles_timeout(self):
        payload = {
            "sell_chain_id": "solana:mainnet",
            "sell_token_is_native": True,
            "buy_token_mint": METEORA_DLMM_USDC_MINT,
            "amount": "1000000000",
            "amount_unit": "base",
            "slippage_bps": 50,
            "taker_address": "wallet",
        }

        with patch("api.main.subprocess.run", side_effect=subprocess.TimeoutExpired("node", 20)):
            result = _try_fetch_phantom_quote(payload)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 504)

    def test_normalize_phantom_quote_option_marks_quote_only_non_clickable(self):
        quote = {
            "ok": True,
            "status_code": 200,
            "first_quote_buyAmount": "83843388",
            "quoteResponse": {
                "quotes": [
                    {
                        "buyAmount": "83843388",
                        "sellAmount": "1000000000",
                        "priceImpact": 0,
                        "baseProvider": {"id": "okx", "name": "OKX"},
                        "sources": [{"name": "ZeroFi via OKX", "proportion": "1"}],
                        "fees": [
                            {
                                "amount": 718778,
                                "name": "Phantom fee",
                                "percentage": 0.0085,
                                "type": "phantom",
                                "token": {
                                    "address": METEORA_DLMM_USDC_MINT,
                                    "chainId": "solana:101",
                                    "resourceType": "address",
                                },
                            }
                        ],
                    }
                ]
            },
        }

        option = _normalize_phantom_quote_option(
            variant_id="phantom_quote",
            label="Via Phantom",
            kind="alternative",
            quote=quote,
            from_token="SOL",
            to_token="USDC",
            input_amount=1.0,
            input_amount_raw=1000000000,
            output_decimals=6,
        )

        self.assertEqual(option["provider"], "phantom-routing-api")
        self.assertEqual(option["execution_surface_label"], "Phantom")
        self.assertEqual(option["quote_status"], "live")
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "wallet_routing_api")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertTrue(option["is_official_quote"])
        self.assertEqual(option["estimated_output_raw"], "83843388")
        self.assertEqual(option["estimated_output"], 83.843388)
        self.assertEqual(option["route_label"], "OKX")
        self.assertEqual(option["route_labels"], ["ZeroFi via OKX"])
        self.assertEqual(option["route_shape"], "wallet-routing")
        self.assertTrue(option["explicit_route_fees"]["has_explicit_fees"])

    def test_normalize_meteora_dlmm_quote_option_marks_comparison_only(self):
        quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {
                "address": "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
                "name": "SOL-USDC",
                "bin_step": 4,
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "84019465",
            "min_out_amount_raw": "83599367",
            "fee_raw": "401920",
            "protocol_fee_raw": "40192",
            "price_impact": "0",
            "bin_arrays": ["8CRkBdY5RkDRDBAZFKwRBpfe2JSWoPqM8jfr14KUXMpF"],
        }

        option = _normalize_meteora_dlmm_quote_option(
            variant_id="meteora_dlmm_quote",
            label="Via Meteora",
            kind="alternative",
            quote=quote,
            from_token="SOL",
            to_token="USDC",
            input_amount=1.0,
            input_amount_raw=1000000000,
            output_decimals=6,
        )

        self.assertEqual(option["provider"], "meteora-dlmm")
        self.assertEqual(option["execution_surface_label"], "Meteora")
        self.assertEqual(option["quote_status"], "live")
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_native_pool")
        self.assertEqual(option["cost_transparency"]["benchmark_gap_scope"], "reference_comparison_not_fee")
        self.assertEqual(option["cost_transparency"]["cost_completeness"], "partial")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertEqual(option["route_label"], "Meteora DLMM")
        self.assertEqual(option["route_shape"], "single-pool")
        self.assertEqual(option["estimated_output"], 84.019465)
        self.assertEqual(option["min_received"], 83.599367)
        self.assertEqual(option["explicit_route_fees"]["route_fee_items"][0]["fee_token"], "SOL")
        self.assertEqual(option["route_steps"][0]["pool_address"], quote["pool"]["address"])
        self.assertEqual(option["_sort_out_amount_raw"], 84019465)

    def test_normalize_orca_whirlpool_quote_option_marks_quote_only_non_clickable(self):
        quote = {
            "ok": True,
            "provider": "orca_whirlpool",
            "pool": {
                "address": "FpCMFDFGYotvufJ7HrFHsWEiiQCGbkLCtwHiDnh7o28Q",
                "tick_spacing": 2,
                "fee_rate": 200,
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "84050000",
            "min_out_amount_raw": "83629750",
            "fee_raw": "200002",
            "slippage_bps": 50,
        }

        option = _normalize_orca_whirlpool_quote_option(
            variant_id="orca_whirlpool_quote",
            label="Via Orca",
            kind="alternative",
            quote=quote,
            from_token="SOL",
            to_token="USDC",
            input_amount=1.0,
            input_amount_raw=1000000000,
            output_decimals=6,
        )

        self.assertEqual(option["provider"], "orca-whirlpool")
        self.assertEqual(option["execution_surface_label"], "Orca")
        self.assertEqual(option["quote_status"], "live")
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_native_pool_sdk")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertEqual(option["estimated_output"], 84.05)
        self.assertEqual(option["min_received"], 83.62975)
        self.assertEqual(option["route_shape"], "single-pool")
        self.assertEqual(option["route_steps"][0]["pool_address"], quote["pool"]["address"])
        self.assertEqual(option["route_steps"][0]["tick_spacing"], 2)
        self.assertTrue(option["explicit_route_fees"]["has_explicit_fees"])

    def test_normalize_phoenix_quote_option_marks_quote_only_non_clickable(self):
        quote = {
            "ok": True,
            "provider": "phoenix",
            "market": {
                "address": "4DoNfFBfF7UokCC2FQzriy7yHK6DY6NVdYpuekQ5pRgg",
                "name": "SOL/USDC",
                "base_mint": METEORA_DLMM_SOL_MINT,
                "quote_mint": METEORA_DLMM_USDC_MINT,
                "taker_fee_bps": 2,
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "83008055",
            "min_out_amount_raw": "82593014",
            "slippage_bps": 50,
            "taker_fee_bps": 2,
            "top_bid": {"price": 83.039, "quantity": 0.1},
            "top_ask": {"price": 83.069, "quantity": 0.005},
            "fill_status": "full",
            "fully_filled": True,
        }

        option = _normalize_phoenix_quote_option(
            variant_id="phoenix_quote",
            label="Via Phoenix",
            kind="alternative",
            quote=quote,
            from_token="SOL",
            to_token="USDC",
            input_amount=1.0,
            input_amount_raw=1000000000,
            output_decimals=6,
        )

        self.assertEqual(option["provider"], "phoenix-clob")
        self.assertEqual(option["execution_surface_label"], "Phoenix")
        self.assertEqual(option["quote_status"], "live")
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_clob_sdk")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertEqual(option["estimated_output"], 83.008055)
        self.assertEqual(option["min_received"], 82.593014)
        self.assertEqual(option["route_shape"], "single-clob-market")
        self.assertEqual(option["route_steps"][0]["market_address"], quote["market"]["address"])
        self.assertEqual(option["route_steps"][0]["fill_status"], "full")
        self.assertTrue(option["explicit_route_fees"]["has_explicit_fees"])

    def test_diverse_other_options_can_include_raydium_and_meteora(self):
        recommended_jupiter = {
            "variant_id": "recommended_default",
            "provider": "jupiter-metis",
            "execution_surface_label": "Jupiter",
            "estimated_output_raw": "120",
            "route_labels": ["Orca"],
            "protections": {"restrict_intermediate_tokens": True},
            "_sort_out_amount_raw": 120,
        }
        raydium_option = {
            "variant_id": "raydium_quote",
            "provider": "raydium-trade-api",
            "execution_surface_label": "Raydium",
            "estimated_output_raw": "118",
            "route_labels": ["Raydium"],
            "protections": {"slippage_bps": 50},
            "_sort_out_amount_raw": 118,
        }
        meteora_option = {
            "variant_id": "meteora_dlmm_quote",
            "provider": "meteora-dlmm",
            "execution_surface_label": "Meteora",
            "estimated_output_raw": "117",
            "route_labels": ["Meteora DLMM"],
            "protections": {"slippage_bps": 50},
            "_sort_out_amount_raw": 117,
        }

        ranked = _rank_quote_options([recommended_jupiter, raydium_option, meteora_option])
        other_options = _select_diverse_other_options(
            ranked,
            best_quote=recommended_jupiter,
            recommended=recommended_jupiter,
            limit=2,
        )

        self.assertEqual(
            [opt["variant_id"] for opt in other_options],
            ["raydium_quote", "meteora_dlmm_quote"],
        )

    def test_diverse_other_options_can_include_more_than_two_remaining_universes(self):
        def option(variant_id, provider, surface, output):
            return {
                "variant_id": variant_id,
                "provider": provider,
                "execution_surface_label": surface,
                "supports_current_pair": True,
                "estimated_output_raw": str(output),
                "route_labels": [surface],
                "_sort_out_amount_raw": output,
            }

        recommended = option("recommended_default", "jupiter-metis", "Jupiter", 900)
        direct = option("orca_whirlpool_quote", "orca-whirlpool", "Orca", 880)
        raydium = option("raydium_quote", "raydium-trade-api", "Raydium", 870)
        meteora = option("meteora_dlmm_quote", "meteora-dlmm", "Meteora", 860)
        phantom = option("phantom_quote", "phantom-routing-api", "Phantom", 850)
        phoenix = option("phoenix_quote", "phoenix-clob", "Phoenix", 840)

        ranked = _rank_quote_options([recommended, direct, raydium, meteora, phantom, phoenix])
        other_options = _select_diverse_other_options(
            ranked,
            best_quote=recommended,
            recommended=recommended,
            direct=direct,
        )

        self.assertEqual(
            [opt["variant_id"] for opt in other_options],
            ["raydium_quote", "meteora_dlmm_quote", "phantom_quote", "phoenix_quote"],
        )
        self.assertNotIn("recommended_default", [opt["variant_id"] for opt in other_options])
        self.assertNotIn("orca_whirlpool_quote", [opt["variant_id"] for opt in other_options])
        self.assertGreater(len(other_options), 2)

    def test_diverse_other_options_excludes_featured_execution_surfaces(self):
        def option(variant_id, provider, surface, output):
            return {
                "variant_id": variant_id,
                "provider": provider,
                "execution_surface_label": surface,
                "supports_current_pair": True,
                "estimated_output_raw": str(output),
                "route_labels": [surface],
                "_sort_out_amount_raw": output,
            }

        recommended = option("recommended_default", "jupiter-metis", "Jupiter", 900)
        jupiter_broader = option("broader_search", "jupiter-metis", "Jupiter", 890)
        direct = option("meteora_dlmm_quote", "meteora-dlmm", "Meteora", 880)
        meteora_extra = option("meteora_backup", "meteora-dlmm", "Meteora", 875)
        orca = option("orca_whirlpool_quote", "orca-whirlpool", "Orca", 870)
        raydium = option("raydium_quote", "raydium-trade-api", "Raydium", 860)
        phoenix = option("phoenix_quote", "phoenix-clob", "Phoenix", 850)
        phantom = option("phantom_quote", "phantom-routing-api", "Phantom", 840)

        ranked = _rank_quote_options(
            [recommended, jupiter_broader, direct, meteora_extra, orca, raydium, phoenix, phantom]
        )
        other_options = _select_diverse_other_options(
            ranked,
            best_quote=recommended,
            recommended=recommended,
            direct=direct,
        )

        variant_ids = [opt["variant_id"] for opt in other_options]
        self.assertNotIn("broader_search", variant_ids)
        self.assertNotIn("meteora_backup", variant_ids)
        self.assertEqual(
            variant_ids,
            ["orca_whirlpool_quote", "raydium_quote", "phoenix_quote", "phantom_quote"],
        )

    def test_select_direct_route_prefers_simpler_shape_then_output(self):
        meteora_option = {
            "variant_id": "meteora_dlmm_quote",
            "provider": "meteora-dlmm",
            "execution_surface_label": "Meteora",
            "supports_current_pair": True,
            "route_shape": "single-pool",
            "route_step_count": 1,
            "estimated_output_raw": "90",
            "_sort_out_amount_raw": 90,
        }
        jupiter_direct_option = {
            "variant_id": "direct_route_check",
            "provider": "jupiter-metis",
            "execution_surface_label": "Jupiter",
            "supports_current_pair": True,
            "route_shape": "direct",
            "route_step_count": 1,
            "estimated_output_raw": "100",
            "_sort_out_amount_raw": 100,
        }

        selected = _select_direct_route_option([jupiter_direct_option, meteora_option])

        self.assertEqual(selected["variant_id"], "meteora_dlmm_quote")

    def test_swap_quote_adds_meteora_as_comparison_only_other_option(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "85000000",
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Orca",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": "85000000",
                    },
                    "percent": 100,
                }
            ],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": METEORA_DLMM_USDC_MINT,
                "outputAmount": "83000000",
                "otherAmountThreshold": "82585000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }
        meteora_quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {
                "address": "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
                "name": "SOL-USDC",
                "bin_step": 4,
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "84000000",
            "min_out_amount_raw": "83580000",
            "fee_raw": "400000",
            "protocol_fee_raw": "40000",
            "price_impact": "0",
            "bin_arrays": ["8CRkBdY5RkDRDBAZFKwRBpfe2JSWoPqM8jfr14KUXMpF"],
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote) as fetch_jupiter,
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": meteora_quote}),
            patch(
                "api.main._try_fetch_orca_whirlpool_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock orca"}},
            ),
            patch(
                "api.main._try_fetch_phoenix_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock phoenix"}},
            ),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        self.assertEqual(response["recommended_option"]["provider"], "jupiter-metis")
        self.assertEqual(response["recommended_option"]["quote_status"], "live")
        self.assertEqual(response["recommended_option"]["execution_status"], "executable_capable")
        self.assertTrue(response["recommended_option"]["supports_current_pair"])
        self.assertEqual(response["recommended_option"]["quote_source_type"], "aggregator")
        self.assertEqual(response["recommended_option"]["cost_transparency"]["ranking_basis"], "highest_receive_amount")
        self.assertEqual(
            response["recommended_option"]["cost_transparency"]["network_fee_scope"],
            "estimated_for_executable_when_available",
        )
        self.assertEqual(response["recommended_executable_option"], response["recommended_option"])
        self.assertEqual(response["summary"]["ranking_basis"], "highest_receive_amount")
        self.assertEqual(response["summary"]["cost_model_scope"], "partial_transparency_not_ranking_input")
        other_providers = [opt["provider"] for opt in response["other_options"]]
        self.assertIn("raydium-trade-api", other_providers)

        meteora_option = response["direct_route_check"]
        self.assertEqual(meteora_option["provider"], "meteora-dlmm")
        self.assertTrue(meteora_option["is_comparison_only"])
        self.assertFalse(meteora_option["is_clickable"])
        self.assertEqual(meteora_option["route_shape"], "single-pool")
        self.assertIn("meteora_dlmm_quote", response["summary"]["checked_variants"])

    def test_swap_quote_accepts_sol_to_bonk_and_skips_unsupported_universes(self):
        sol_mint = "So11111111111111111111111111111111111111112"
        bonk_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        jupiter_quote = {
            "inputMint": sol_mint,
            "inAmount": "1000000000",
            "outputMint": bonk_mint,
            "outAmount": "1350000000000",
            "otherAmountThreshold": "1343250000000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Raydium",
                        "inputMint": sol_mint,
                        "outputMint": bonk_mint,
                        "inAmount": "1000000000",
                        "outAmount": "1350000000000",
                    },
                    "percent": 100,
                }
            ],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": sol_mint,
                "inputAmount": "1000000000",
                "outputMint": bonk_mint,
                "outputAmount": "1340000000000",
                "otherAmountThreshold": "1333300000000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }

        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote) as fetch_jupiter,
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}) as fetch_raydium,
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported) as fetch_meteora,
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported) as fetch_orca,
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported) as fetch_phoenix,
            patch("api.main._try_fetch_phantom_quote", return_value=unsupported) as fetch_phantom,
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "BONK": {"usd": 0.000006},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="BONK", amount=1.0)

        self.assertEqual(response["from_token"], "SOL")
        self.assertEqual(response["to_token"], "BONK")
        self.assertEqual(response["input_amount_raw"], 1000000000)
        self.assertEqual(response["recommended_option"]["provider"], "jupiter-metis")
        self.assertEqual(fetch_jupiter.call_args.args[0]["outputMint"], bonk_mint)
        self.assertEqual(fetch_raydium.call_args.args[0]["outputMint"], bonk_mint)
        fetch_meteora.assert_called_once()
        fetch_orca.assert_called_once()
        fetch_phoenix.assert_called_once()
        fetch_phantom.assert_called_once()

        providers = [opt["provider"] for opt in response["other_options"]]
        self.assertIn("raydium-trade-api", providers)
        self.assertNotIn("meteora-dlmm", providers)
        self.assertNotIn("orca-whirlpool", providers)
        self.assertNotIn("phoenix-clob", providers)
        self.assertNotIn("phantom-routing-api", providers)

        diagnostic_variants = {
            item["variant_id"] for item in response["debug"]["variant_errors"]
        }
        self.assertIn("meteora_dlmm_quote", diagnostic_variants)
        self.assertIn("orca_whirlpool_quote", diagnostic_variants)
        self.assertIn("phoenix_quote", diagnostic_variants)
        self.assertIn("phantom_quote", diagnostic_variants)

        self.assertAlmostEqual(
            response["recommended_option"]["estimated_trade_execution_cost"]["amount"],
            500000.0,
        )
        self.assertAlmostEqual(
            response["recommended_option"]["estimated_trade_execution_cost"]["amount_usd"],
            3.0,
        )
        raydium_option = next(
            opt for opt in response["other_options"] if opt["provider"] == "raydium-trade-api"
        )
        self.assertAlmostEqual(raydium_option["estimated_trade_execution_cost"]["amount"], 600000.0)
        self.assertAlmostEqual(raydium_option["estimated_trade_execution_cost"]["amount_usd"], 3.6)
        self.assertNotEqual(
            raydium_option["estimated_trade_execution_cost"]["amount"],
            raydium_option["estimated_trade_execution_cost"]["amount_usd"],
        )

    def test_swap_quote_sol_usdc_still_uses_registry_metadata(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "85000000",
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [],
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch(
                "api.main._try_fetch_raydium_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock raydium"}},
            ),
            patch(
                "api.main._try_fetch_meteora_dlmm_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock meteora"}},
            ),
            patch(
                "api.main._try_fetch_orca_whirlpool_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock orca"}},
            ),
            patch(
                "api.main._try_fetch_phoenix_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock phoenix"}},
            ),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        self.assertEqual(response["from_token"], "SOL")
        self.assertEqual(response["to_token"], "USDC")
        self.assertEqual(response["input_amount_raw"], 1000000000)
        self.assertEqual(response["recommended_option"]["estimated_output"], 85.0)

    def test_swap_quote_recommends_meteora_when_it_has_best_output(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "85000000",
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Orca",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": "85000000",
                    },
                    "percent": 100,
                }
            ],
        }
        broader_jupiter_quote = {
            **jupiter_quote,
            "outAmount": "84500000",
            "otherAmountThreshold": "84077500",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Lifinity",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": "84500000",
                    },
                    "percent": 100,
                }
            ],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": METEORA_DLMM_USDC_MINT,
                "outputAmount": "83000000",
                "otherAmountThreshold": "82585000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }
        meteora_quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {
                "address": "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
                "name": "SOL-USDC",
                "bin_step": 4,
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "86000000",
            "min_out_amount_raw": "85570000",
            "fee_raw": "400000",
            "protocol_fee_raw": "40000",
            "price_impact": "0",
            "bin_arrays": ["8CRkBdY5RkDRDBAZFKwRBpfe2JSWoPqM8jfr14KUXMpF"],
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                side_effect=[
                    {"ok": True, "data": broader_jupiter_quote},
                    {"ok": False, "error": {"status_code": 502, "detail": "mock exclude"}},
                    {"ok": False, "error": {"status_code": 502, "detail": "mock direct"}},
                ],
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": meteora_quote}),
            patch(
                "api.main._try_fetch_orca_whirlpool_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock orca"}},
            ),
            patch(
                "api.main._try_fetch_phoenix_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock phoenix"}},
            ),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        self.assertEqual(response["best_quote_option"]["provider"], "meteora-dlmm")
        self.assertEqual(response["recommended_option"]["provider"], "meteora-dlmm")
        self.assertEqual(response["recommended"]["provider"], "meteora-dlmm")
        self.assertTrue(response["recommended_option"]["is_comparison_only"])
        self.assertFalse(response["recommended_option"]["is_clickable"])
        self.assertEqual(response["recommended_option"]["execution_status"], "quote_only")
        self.assertEqual(response["recommended_executable_option"]["provider"], "jupiter-metis")
        self.assertEqual(
            response["recommended_executable_option"]["execution_status"],
            "executable_capable",
        )
        self.assertEqual(response["summary"]["recommended_variant_id"], "meteora_dlmm_quote")
        self.assertEqual(
            response["summary"]["recommended_executable_variant_id"],
            "recommended_default",
        )
        self.assertEqual(
            response["summary"]["recommendation_scope"],
            "highest_receive_amount_across_live_quote_universes",
        )
        self.assertEqual(
            response["summary"]["execution_availability_scope"],
            "separate_from_recommendation",
        )

        other_providers = [opt["provider"] for opt in response["other_options"]]
        self.assertIn("raydium-trade-api", other_providers)
        self.assertNotIn("jupiter-metis", other_providers)
        self.assertNotIn("meteora-dlmm", other_providers)

    def test_swap_quote_recommends_orca_when_it_has_best_output(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "85000000",
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Raydium",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": "85000000",
                    },
                    "percent": 100,
                }
            ],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": METEORA_DLMM_USDC_MINT,
                "outputAmount": "83000000",
                "otherAmountThreshold": "82585000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }
        meteora_quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {"address": "meteora_pool", "name": "SOL-USDC", "bin_step": 4},
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "84000000",
            "min_out_amount_raw": "83580000",
            "fee_raw": "400000",
            "protocol_fee_raw": "40000",
        }
        orca_quote = {
            "ok": True,
            "provider": "orca_whirlpool",
            "pool": {"address": "orca_pool", "tick_spacing": 2, "fee_rate": 200},
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "86000000",
            "min_out_amount_raw": "85570000",
            "fee_raw": "200000",
            "slippage_bps": 50,
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": meteora_quote}),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value={"ok": True, "data": orca_quote}),
            patch(
                "api.main._try_fetch_phoenix_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock phoenix"}},
            ),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        self.assertEqual(response["recommended_option"]["provider"], "orca-whirlpool")
        self.assertEqual(response["recommended_option"]["variant_id"], "orca_whirlpool_quote")
        self.assertTrue(response["recommended_option"]["is_comparison_only"])
        self.assertFalse(response["recommended_option"]["is_clickable"])
        self.assertEqual(response["summary"]["recommended_variant_id"], "orca_whirlpool_quote")
        self.assertIn("orca_whirlpool_quote", response["summary"]["checked_variants"])

    def test_swap_quote_can_show_phantom_and_phoenix_as_alternatives(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "90000000",
            "otherAmountThreshold": "89550000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Raydium",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": "90000000",
                    },
                    "percent": 100,
                }
            ],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": METEORA_DLMM_USDC_MINT,
                "outputAmount": "83000000",
                "otherAmountThreshold": "82585000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }
        meteora_quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {"address": "meteora_pool", "name": "SOL-USDC", "bin_step": 4},
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "82000000",
            "min_out_amount_raw": "81590000",
            "fee_raw": "400000",
            "protocol_fee_raw": "40000",
        }
        orca_quote = {
            "ok": True,
            "provider": "orca_whirlpool",
            "pool": {"address": "orca_pool", "tick_spacing": 2, "fee_rate": 200},
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "88000000",
            "min_out_amount_raw": "87560000",
            "fee_raw": "200000",
            "slippage_bps": 50,
        }
        phoenix_quote = {
            "ok": True,
            "provider": "phoenix",
            "market": {
                "address": "4DoNfFBfF7UokCC2FQzriy7yHK6DY6NVdYpuekQ5pRgg",
                "name": "SOL/USDC",
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "87000000",
            "min_out_amount_raw": "86565000",
            "slippage_bps": 50,
            "taker_fee_bps": 2,
            "top_bid": {"price": 87, "quantity": 10},
            "top_ask": {"price": 87.1, "quantity": 10},
            "fill_status": "full",
            "fully_filled": True,
        }
        phantom_quote = {
            "ok": True,
            "status_code": 200,
            "first_quote_buyAmount": "86500000",
            "quoteResponse": {
                "quotes": [
                    {
                        "buyAmount": "86500000",
                        "sellAmount": "1000000000",
                        "priceImpact": 0,
                        "baseProvider": {"id": "okx", "name": "OKX"},
                        "sources": [{"name": "ZeroFi via OKX", "proportion": "1"}],
                        "fees": [],
                    }
                ]
            },
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": meteora_quote}),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value={"ok": True, "data": orca_quote}),
            patch("api.main._try_fetch_phoenix_quote", return_value={"ok": True, "data": phoenix_quote}),
            patch("api.main._try_fetch_phantom_quote", return_value={"ok": True, "data": phantom_quote}),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        other_providers = [opt["provider"] for opt in response["other_options"]]
        self.assertIn("phoenix-clob", other_providers)
        self.assertIn("phantom-routing-api", other_providers)
        self.assertIn("raydium-trade-api", other_providers)
        self.assertIn("meteora-dlmm", other_providers)
        self.assertNotIn("jupiter-metis", other_providers)
        self.assertNotIn("orca-whirlpool", other_providers)
        self.assertGreater(len(response["other_options"]), 2)
        phoenix_option = next(opt for opt in response["other_options"] if opt["provider"] == "phoenix-clob")
        self.assertEqual(phoenix_option["label"], "Via Phoenix")
        self.assertTrue(phoenix_option["is_comparison_only"])
        self.assertFalse(phoenix_option["is_clickable"])
        phantom_option = next(opt for opt in response["other_options"] if opt["provider"] == "phantom-routing-api")
        self.assertEqual(phantom_option["label"], "Via Phantom")
        self.assertTrue(phantom_option["is_comparison_only"])
        self.assertFalse(phantom_option["is_clickable"])
        self.assertTrue(response["summary"]["alternatives_show_all_remaining_universes"])
        self.assertIn("phoenix_quote", response["summary"]["checked_variants"])
        self.assertIn("phantom_quote", response["summary"]["checked_variants"])

    def test_swap_quote_selects_meteora_single_pool_as_direct_route(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "85000000",
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Orca",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": "85000000",
                    },
                    "percent": 100,
                }
            ],
        }
        jupiter_direct_quote = {
            **jupiter_quote,
            "outAmount": "84900000",
            "otherAmountThreshold": "84475500",
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": METEORA_DLMM_USDC_MINT,
                "outputAmount": "83000000",
                "otherAmountThreshold": "82585000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }
        meteora_quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {
                "address": "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
                "name": "SOL-USDC",
                "bin_step": 4,
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "84000000",
            "min_out_amount_raw": "83580000",
            "fee_raw": "400000",
            "protocol_fee_raw": "40000",
            "price_impact": "0",
            "bin_arrays": ["8CRkBdY5RkDRDBAZFKwRBpfe2JSWoPqM8jfr14KUXMpF"],
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                side_effect=[
                    {"ok": False, "error": {"status_code": 502, "detail": "mock broader"}},
                    {"ok": False, "error": {"status_code": 502, "detail": "mock exclude"}},
                    {"ok": True, "data": jupiter_direct_quote},
                ],
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": meteora_quote}),
            patch(
                "api.main._try_fetch_orca_whirlpool_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock orca"}},
            ),
            patch(
                "api.main._try_fetch_phoenix_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock phoenix"}},
            ),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        self.assertEqual(response["direct_route_check"]["provider"], "meteora-dlmm")
        self.assertEqual(response["direct_route_check"]["route_shape"], "single-pool")
        self.assertTrue(response["direct_route_check"]["is_comparison_only"])
        self.assertFalse(response["direct_route_check"]["is_clickable"])
        self.assertEqual(response["summary"]["direct_route_variant_id"], "meteora_dlmm_quote")
        self.assertEqual(
            response["summary"]["direct_route_selection_basis"],
            "simplest_meaningful_candidate_across_live_quote_universes",
        )

    def test_swap_quote_allows_jupiter_direct_to_win_simple_route_tiebreak(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "85000000",
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Orca",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": "85000000",
                    },
                    "percent": 100,
                }
            ],
        }
        jupiter_direct_quote = {
            **jupiter_quote,
            "outAmount": "88000000",
            "otherAmountThreshold": "87560000",
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": METEORA_DLMM_USDC_MINT,
                "outputAmount": "83000000",
                "otherAmountThreshold": "82585000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                side_effect=[
                    {"ok": False, "error": {"status_code": 502, "detail": "mock broader"}},
                    {"ok": False, "error": {"status_code": 502, "detail": "mock exclude"}},
                    {"ok": True, "data": jupiter_direct_quote},
                ],
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch(
                "api.main._try_fetch_meteora_dlmm_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock meteora"}},
            ),
            patch(
                "api.main._try_fetch_orca_whirlpool_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock orca"}},
            ),
            patch(
                "api.main._try_fetch_phoenix_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock phoenix"}},
            ),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        self.assertEqual(response["direct_route_check"]["provider"], "jupiter-metis")
        self.assertEqual(response["direct_route_check"]["variant_id"], "direct_route_check")
        self.assertEqual(response["summary"]["direct_route_variant_id"], "direct_route_check")

    def test_swap_quote_recommends_phantom_when_it_has_best_output(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "85000000",
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Orca",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": "85000000",
                    },
                    "percent": 100,
                }
            ],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": METEORA_DLMM_USDC_MINT,
                "outputAmount": "83000000",
                "otherAmountThreshold": "82585000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }
        phantom_quote = {
            "ok": True,
            "status_code": 200,
            "first_quote_buyAmount": "90000000",
            "quoteResponse": {
                "quotes": [
                    {
                        "buyAmount": "90000000",
                        "sellAmount": "1000000000",
                        "priceImpact": 0,
                        "baseProvider": {"id": "okx", "name": "OKX"},
                        "sources": [{"name": "ZeroFi via OKX", "proportion": "1"}],
                        "fees": [
                            {
                                "amount": 765000,
                                "name": "Phantom fee",
                                "percentage": 0.0085,
                                "type": "phantom",
                                "token": {
                                    "address": METEORA_DLMM_USDC_MINT,
                                    "chainId": "solana:101",
                                    "resourceType": "address",
                                },
                            }
                        ],
                    }
                ]
            },
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch(
                "api.main._try_fetch_meteora_dlmm_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock meteora"}},
            ),
            patch(
                "api.main._try_fetch_orca_whirlpool_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock orca"}},
            ),
            patch(
                "api.main._try_fetch_phoenix_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock phoenix"}},
            ),
            patch("api.main._try_fetch_phantom_quote", return_value={"ok": True, "data": phantom_quote}),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(
                from_token="SOL",
                to_token="USDC",
                amount=1.0,
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(response["recommended_option"]["provider"], "phantom-routing-api")
        self.assertEqual(response["recommended_option"]["variant_id"], "phantom_quote")
        self.assertTrue(response["recommended_option"]["is_comparison_only"])
        self.assertFalse(response["recommended_option"]["is_clickable"])
        self.assertEqual(response["recommended_option"]["execution_status"], "quote_only")
        self.assertEqual(response["recommended_option"]["estimated_output_raw"], "90000000")
        self.assertEqual(response["summary"]["recommended_variant_id"], "phantom_quote")
        self.assertFalse(response["summary"]["recommended_is_executable"])
        self.assertEqual(response["recommended_executable_option"]["provider"], "jupiter-metis")
        self.assertTrue(response["recommended_executable_option"]["is_clickable"])
        self.assertIn("phantom_quote", response["summary"]["checked_variants"])

    def test_swap_quote_missing_user_public_key_adds_phantom_diagnostic(self):
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "85000000",
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [],
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch(
                "api.main._try_fetch_raydium_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock raydium"}},
            ),
            patch(
                "api.main._try_fetch_meteora_dlmm_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock meteora"}},
            ),
            patch(
                "api.main._try_fetch_orca_whirlpool_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock orca"}},
            ),
            patch(
                "api.main._try_fetch_phoenix_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock phoenix"}},
            ),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        self.assertEqual(response["recommended_option"]["provider"], "jupiter-metis")
        phantom_errors = [
            err for err in response["debug"]["variant_errors"]
            if err.get("variant_id") == "phantom_quote"
        ]
        self.assertEqual(len(phantom_errors), 1)
        self.assertEqual(phantom_errors[0]["status_code"], 400)
        self.assertIn("user_public_key", phantom_errors[0]["detail"])

if __name__ == "__main__":
    unittest.main()
