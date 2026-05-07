import unittest
import tempfile
import json
import subprocess
import requests
from pathlib import Path
from unittest.mock import patch
from api.main import (
    METEORA_DLMM_SOL_MINT,
    METEORA_DLMM_USDC_MINT,
    METEORA_DLMM_BONK_MINT,
    TOKEN_META,
    _build_meteora_dlmm_quote_payload,
    _build_orca_whirlpool_quote_payload,
    _build_phantom_quote_payload,
    _build_phoenix_quote_payload,
    _build_pumpswap_quote_payload,
    _fetch_meteora_dlmm_quote,
    _fetch_orca_whirlpool_quote,
    _fetch_phantom_quote,
    _fetch_phoenix_quote,
    _fetch_pumpswap_quote,
    _is_executable_quote_option,
    _normalize_meteora_dlmm_quote_option,
    _normalize_orca_whirlpool_quote_option,
    _normalize_phantom_quote_option,
    _normalize_phoenix_quote_option,
    _normalize_pumpswap_quote_option,
    _normalize_raydium_quote_option,
    _rank_quote_options,
    _build_reference_baseline_from_resolved_prices,
    _resolve_quote_benchmark_prices_usd,
    _resolve_swap_token_meta,
    _resolve_swap_token_for_quote,
    _select_direct_route_option,
    _select_diverse_other_options,
    _try_fetch_meteora_dlmm_quote,
    _try_fetch_orca_whirlpool_quote,
    _try_fetch_phantom_quote,
    _try_fetch_phoenix_quote,
    _try_fetch_pumpswap_quote,
    swap_quote,
    swap_tokens,
    token_resolve,
)
from api.ui_page import build_ui_html
from providers.token_resolver import resolve_token
from providers.solana_token_metadata import fetch_solana_mint_decimals

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

    def test_token_resolver_resolves_known_symbol(self):
        with (
            patch("providers.token_resolver.fetch_dexscreener_token_metadata") as fetch_external,
            patch("providers.token_resolver.fetch_solana_mint_decimals") as fetch_decimals,
        ):
            result = resolve_token("WIF")

        self.assertTrue(result["ok"])
        self.assertEqual(result["token"]["source"], "registry")
        self.assertEqual(result["token"]["symbol"], "WIF")
        self.assertEqual(result["token"]["name"], "dogwifhat")
        self.assertEqual(result["token"]["mint"], "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm")
        self.assertEqual(result["token"]["decimals"], 6)
        self.assertTrue(result["token"]["verified"])
        self.assertEqual(result["token"]["warnings"], [])
        fetch_external.assert_not_called()
        fetch_decimals.assert_not_called()

    def test_token_resolver_resolves_known_mint(self):
        with (
            patch("providers.token_resolver.fetch_dexscreener_token_metadata") as fetch_external,
            patch("providers.token_resolver.fetch_solana_mint_decimals") as fetch_decimals,
        ):
            result = resolve_token("7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")

        self.assertTrue(result["ok"])
        self.assertEqual(result["token"]["source"], "registry")
        self.assertEqual(result["token"]["symbol"], "POPCAT")
        self.assertEqual(result["token"]["display_name"], "Popcat")
        self.assertEqual(result["token"]["decimals"], 9)
        fetch_external.assert_not_called()
        fetch_decimals.assert_not_called()

    def test_token_resolver_rejects_empty_query(self):
        result = resolve_token("  ")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "EMPTY_QUERY")

    def test_token_resolver_unknown_mint_returns_external_lookup_required(self):
        unknown_mint = "11111111111111111111111111111112"
        result = resolve_token(unknown_mint, allow_external=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TOKEN_METADATA_LOOKUP_NOT_IMPLEMENTED")
        self.assertEqual(result["token"]["source"], "unresolved_mint")
        self.assertEqual(result["token"]["mint"], unknown_mint)
        self.assertIsNone(result["token"]["decimals"])
        self.assertIn("external_lookup_required", result["token"]["warnings"])

    def test_token_resolver_unknown_mint_uses_mocked_dexscreener_success(self):
        unknown_mint = "11111111111111111111111111111112"
        external_result = {
            "ok": True,
            "token": {
                "source": "dexscreener",
                "symbol": "EXT",
                "name": "External Token",
                "display_name": "External Token",
                "mint": unknown_mint,
                "decimals": None,
                "logo_uri": "https://example.invalid/logo.png",
                "verified": False,
                "default_enabled": False,
                "tags": ["external", "dexscreener"],
                "dexscreener_chain_id": "solana",
                "liquidity_usd": 12345.0,
                "price_usd": 0.001,
                "pair_address": "pair",
                "pair_url": "https://dexscreener.com/solana/pair",
                "warnings": ["external_metadata_unverified", "decimals_unresolved"],
            },
        }

        with (
            patch("providers.token_resolver.fetch_dexscreener_token_metadata", return_value=external_result) as fetch_external,
            patch(
                "providers.token_resolver.fetch_solana_mint_decimals",
                return_value={
                    "ok": True,
                    "decimals": 6,
                    "source": "solana_rpc",
                    "mint": unknown_mint,
                    "owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                },
            ) as fetch_decimals,
        ):
            result = resolve_token(unknown_mint)

        self.assertTrue(result["ok"])
        self.assertEqual(result["token"]["source"], "dexscreener")
        self.assertEqual(result["token"]["symbol"], "EXT")
        self.assertEqual(result["token"]["mint"], unknown_mint)
        self.assertEqual(result["token"]["decimals"], 6)
        self.assertEqual(result["token"]["decimals_source"], "solana_rpc")
        self.assertEqual(result["token"]["liquidity_usd"], 12345.0)
        self.assertNotIn("decimals_unresolved", result["token"]["warnings"])
        fetch_external.assert_called_once_with(unknown_mint)
        fetch_decimals.assert_called_once_with(unknown_mint)

    def test_token_resolver_dexscreener_success_keeps_warning_when_decimals_fail(self):
        unknown_mint = "11111111111111111111111111111112"
        external_result = {
            "ok": True,
            "token": {
                "source": "dexscreener",
                "symbol": "EXT",
                "name": "External Token",
                "display_name": "External Token",
                "mint": unknown_mint,
                "decimals": None,
                "logo_uri": None,
                "verified": False,
                "default_enabled": False,
                "tags": ["external", "dexscreener"],
                "dexscreener_chain_id": "solana",
                "liquidity_usd": 12345.0,
                "price_usd": 0.001,
                "warnings": ["external_metadata_unverified", "decimals_unresolved"],
            },
        }

        with (
            patch("providers.token_resolver.fetch_dexscreener_token_metadata", return_value=external_result),
            patch(
                "providers.token_resolver.fetch_solana_mint_decimals",
                return_value={
                    "ok": False,
                    "error": {
                        "code": "TOKEN_DECIMALS_LOOKUP_FAILED",
                        "message": "timeout",
                    },
                },
            ),
        ):
            result = resolve_token(unknown_mint)

        self.assertTrue(result["ok"])
        self.assertIsNone(result["token"]["decimals"])
        self.assertIn("decimals_unresolved", result["token"]["warnings"])
        self.assertEqual(result["token"]["decimals_error"]["code"], "TOKEN_DECIMALS_LOOKUP_FAILED")

    def test_token_resolver_unknown_mint_reports_dexscreener_not_found(self):
        unknown_mint = "11111111111111111111111111111112"
        external_result = {
            "ok": False,
            "error": {
                "code": "TOKEN_METADATA_NOT_FOUND",
                "message": "DexScreener returned no token pairs for this mint.",
                "provider": "dexscreener",
            },
        }

        with patch("providers.token_resolver.fetch_dexscreener_token_metadata", return_value=external_result):
            result = resolve_token(unknown_mint)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TOKEN_METADATA_NOT_FOUND")
        self.assertEqual(result["error"]["provider"], "dexscreener")

    def test_token_resolver_unknown_mint_reports_dexscreener_failure(self):
        unknown_mint = "11111111111111111111111111111112"
        external_result = {
            "ok": False,
            "error": {
                "code": "EXTERNAL_TOKEN_LOOKUP_FAILED",
                "message": "DexScreener token metadata lookup failed.",
                "provider": "dexscreener",
                "failures": [{"error": "timeout"}],
            },
        }

        with patch("providers.token_resolver.fetch_dexscreener_token_metadata", return_value=external_result):
            result = resolve_token(unknown_mint)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "EXTERNAL_TOKEN_LOOKUP_FAILED")
        self.assertEqual(result["error"]["provider"], "dexscreener")
        self.assertEqual(result["error"]["failures"][0]["error"], "timeout")

    def test_token_resolve_endpoint_returns_expected_shape(self):
        result = token_resolve(query="USDC", allow_external=True)

        self.assertTrue(result["ok"])
        self.assertEqual(result["token"]["symbol"], "USDC")
        self.assertEqual(result["token"]["mint"], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.assertEqual(result["token"]["decimals"], 6)

    def test_token_resolve_endpoint_supports_allow_external_parameter(self):
        unknown_mint = "11111111111111111111111111111112"

        with patch("providers.token_resolver.fetch_dexscreener_token_metadata") as fetch_external:
            result = token_resolve(query=unknown_mint, allow_external=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TOKEN_METADATA_LOOKUP_NOT_IMPLEMENTED")
        fetch_external.assert_not_called()

    def test_solana_mint_decimals_rpc_helper_parses_json_parsed_account(self):
        class Response:
            ok = True
            status_code = 200

            def json(self):
                return {
                    "result": {
                        "value": {
                            "owner": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
                            "data": {
                                "parsed": {
                                    "type": "mint",
                                    "info": {"decimals": 8},
                                },
                            },
                        },
                    },
                }

        with patch("providers.solana_token_metadata.requests.post", return_value=Response()) as post:
            result = fetch_solana_mint_decimals("mint", rpc_url="https://example.invalid")

        self.assertTrue(result["ok"])
        self.assertEqual(result["decimals"], 8)
        self.assertEqual(result["source"], "solana_rpc")
        self.assertEqual(result["owner"], "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
        self.assertEqual(post.call_args.kwargs["json"]["method"], "getAccountInfo")
        self.assertEqual(post.call_args.kwargs["json"]["params"][1]["encoding"], "jsonParsed")

    def test_solana_mint_decimals_rpc_helper_reports_not_found(self):
        class MissingResponse:
            ok = True
            status_code = 200

            def json(self):
                return {"result": {"value": None}}

        class MissingDecimalsResponse:
            ok = True
            status_code = 200

            def json(self):
                return {"result": {"value": {"data": {"parsed": {"info": {}}}}}}

        for response in (MissingResponse(), MissingDecimalsResponse()):
            with self.subTest(response=response.__class__.__name__):
                with patch("providers.solana_token_metadata.requests.post", return_value=response):
                    result = fetch_solana_mint_decimals("mint", rpc_url="https://example.invalid")

                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "TOKEN_DECIMALS_NOT_FOUND")

    def test_solana_mint_decimals_rpc_helper_reports_lookup_failure(self):
        class RpcErrorResponse:
            ok = True
            status_code = 200

            def json(self):
                return {"error": {"code": -32000, "message": "bad"}}

        class HttpErrorResponse:
            ok = False
            status_code = 429

            def json(self):
                return {}

        cases = [
            requests.Timeout("timeout"),
            RpcErrorResponse(),
            HttpErrorResponse(),
        ]

        for case in cases:
            with self.subTest(case=case.__class__.__name__):
                if isinstance(case, Exception):
                    side_effect = case
                    return_value = None
                else:
                    side_effect = None
                    return_value = case

                with patch(
                    "providers.solana_token_metadata.requests.post",
                    side_effect=side_effect,
                    return_value=return_value,
                ):
                    result = fetch_solana_mint_decimals("mint", rpc_url="https://example.invalid")

                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "TOKEN_DECIMALS_LOOKUP_FAILED")

    def test_resolve_swap_token_for_quote_keeps_registry_metadata(self):
        with patch("api.main.resolve_token") as resolver:
            meta = _resolve_swap_token_for_quote("WIF")

        self.assertEqual(meta["source"], "registry")
        self.assertFalse(meta["external"])
        self.assertEqual(meta["quote_label"], "WIF")
        self.assertEqual(meta["mint"], "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm")
        self.assertEqual(meta["decimals"], 6)
        resolver.assert_not_called()

    def test_resolve_swap_token_for_quote_accepts_external_mint_with_decimals(self):
        mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        with patch(
            "api.main.resolve_token",
            return_value={
                "ok": True,
                "token": {
                    "source": "dexscreener",
                    "symbol": "JUP",
                    "name": "Jupiter",
                    "display_name": "Jupiter",
                    "mint": mint,
                    "decimals": 6,
                    "verified": False,
                    "default_enabled": False,
                    "tags": ["external", "dexscreener"],
                    "warnings": ["external_metadata_unverified"],
                    "liquidity_usd": 1000000.0,
                    "price_usd": 0.2,
                    "pair_address": "pair",
                    "pair_url": "https://dexscreener.com/solana/pair",
                },
            },
        ):
            meta = _resolve_swap_token_for_quote(mint)

        self.assertTrue(meta["external"])
        self.assertEqual(meta["source"], "external_resolver")
        self.assertEqual(meta["resolver_source"], "dexscreener")
        self.assertEqual(meta["symbol"], "JUP")
        self.assertEqual(meta["quote_label"], "JUP")
        self.assertEqual(meta["mint"], mint)
        self.assertEqual(meta["decimals"], 6)

    def test_resolve_swap_token_for_quote_rejects_external_mint_without_decimals(self):
        mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        with patch(
            "api.main.resolve_token",
            return_value={
                "ok": True,
                "token": {
                    "source": "dexscreener",
                    "symbol": "JUP",
                    "display_name": "Jupiter",
                    "mint": mint,
                    "decimals": None,
                },
            },
        ):
            meta = _resolve_swap_token_for_quote(mint)

        self.assertTrue(meta["external"])
        self.assertEqual(meta["resolution_error"]["code"], "TOKEN_RESOLUTION_INCOMPLETE")

    def test_resolve_swap_token_for_quote_reports_external_not_found(self):
        mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        with patch(
            "api.main.resolve_token",
            return_value={
                "ok": False,
                "error": {"code": "TOKEN_METADATA_NOT_FOUND", "message": "not found"},
            },
        ):
            meta = _resolve_swap_token_for_quote(mint)

        self.assertTrue(meta["external"])
        self.assertEqual(meta["resolution_error"]["code"], "TOKEN_METADATA_NOT_FOUND")

    def test_swap_quote_accepts_external_mint_as_to_token_with_mocked_quotes(self):
        ext_mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        self.assertNotIn(ext_mint, {meta.get("mint") for meta in TOKEN_META.values()})
        jupiter_quote = {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": ext_mint,
            "outAmount": "2000000",
            "otherAmountThreshold": "1990000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": ext_mint,
                "outputAmount": "1900000",
                "otherAmountThreshold": "1890000",
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
            patch(
                "api.main.resolve_token",
                return_value={
                    "ok": True,
                    "token": {
                        "source": "dexscreener",
                        "symbol": "JUP",
                        "name": "Jupiter",
                        "display_name": "Jupiter",
                        "mint": ext_mint,
                        "decimals": 6,
                        "verified": False,
                        "warnings": ["external_metadata_unverified"],
                        "liquidity_usd": 1000000.0,
                        "price_usd": 0.2,
                        "pair_address": "pair",
                        "pair_url": "https://dexscreener.com/solana/pair",
                    },
                },
            ) as resolver,
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote) as fetch_jupiter,
            patch("api.main._try_fetch_jupiter_quote", return_value=unsupported),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
            patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "JUP": {"usd": 0.2},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token=ext_mint, amount=1.0)

        self.assertEqual(response["to_token"], "JUP")
        self.assertEqual(response["recommended_option"]["estimated_output"], 2.0)
        self.assertEqual(response["external_tokens"][0]["side"], "to")
        self.assertEqual(response["external_tokens"][0]["mint"], ext_mint)
        self.assertEqual(response["external_tokens"][0]["source"], "dexscreener")
        self.assertFalse(response["external_tokens"][0]["verified"])
        self.assertTrue(response["summary"]["uses_external_tokens"])
        self.assertNotIn(ext_mint, {meta.get("mint") for meta in TOKEN_META.values()})
        fetch_jupiter.assert_called_once()
        self.assertEqual(fetch_jupiter.call_args.args[0]["outputMint"], ext_mint)
        resolver.assert_called_once_with(ext_mint, allow_external=True)

        raydium_option = next(opt for opt in response["other_options"] if opt["provider"] == "raydium-trade-api")
        self.assertTrue(raydium_option["is_comparison_only"])
        self.assertFalse(raydium_option["is_clickable"])
        diagnostic_variants = {item["variant_id"] for item in response["debug"]["variant_errors"]}
        self.assertIn("phoenix_quote", diagnostic_variants)
        self.assertIn("pumpswap_quote", diagnostic_variants)

    def test_swap_quote_accepts_external_mint_as_from_token_with_mocked_jupiter(self):
        ext_mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        jupiter_quote = {
            "inputMint": ext_mint,
            "inAmount": "2500000",
            "outputMint": METEORA_DLMM_SOL_MINT,
            "outAmount": "5000000",
            "otherAmountThreshold": "4975000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "0.5",
            "routePlan": [],
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        with (
            patch(
                "api.main.resolve_token",
                return_value={
                    "ok": True,
                    "token": {
                        "source": "dexscreener",
                        "symbol": "JUP",
                        "display_name": "Jupiter",
                        "mint": ext_mint,
                        "decimals": 6,
                        "verified": False,
                        "warnings": ["external_metadata_unverified"],
                    },
                },
            ),
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote) as fetch_jupiter,
            patch("api.main._try_fetch_jupiter_quote", return_value=unsupported),
            patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
            patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "JUP": {"usd": 0.2},
                    "SOL": {"usd": 84.0},
                },
            ),
        ):
            response = swap_quote(from_token=ext_mint, to_token="SOL", amount=2.5)

        self.assertEqual(response["from_token"], "JUP")
        self.assertEqual(response["to_token"], "SOL")
        self.assertEqual(response["input_amount_raw"], 2500000)
        self.assertEqual(response["external_tokens"][0]["side"], "from")
        self.assertEqual(response["recommended_option"]["estimated_output_raw"], "5000000")
        self.assertEqual(fetch_jupiter.call_args.args[0]["inputMint"], ext_mint)

    def test_swap_quote_rejects_external_mint_without_decimals(self):
        ext_mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        with patch(
            "api.main.resolve_token",
            return_value={
                "ok": True,
                "token": {
                    "source": "dexscreener",
                    "symbol": "JUP",
                    "display_name": "Jupiter",
                    "mint": ext_mint,
                    "decimals": None,
                },
            },
        ):
            with self.assertRaises(Exception) as ctx:
                swap_quote(from_token="SOL", to_token=ext_mint, amount=1.0)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["side"], "to")
        self.assertEqual(
            ctx.exception.detail["error"]["code"],
            "TOKEN_RESOLUTION_INCOMPLETE",
        )

    def test_swap_quote_rejects_external_mint_not_found(self):
        ext_mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        with patch(
            "api.main.resolve_token",
            return_value={
                "ok": False,
                "error": {"code": "TOKEN_METADATA_NOT_FOUND", "message": "not found"},
            },
        ):
            with self.assertRaises(Exception) as ctx:
                swap_quote(from_token="SOL", to_token=ext_mint, amount=1.0)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["side"], "to")
        self.assertEqual(
            ctx.exception.detail["error"]["code"],
            "TOKEN_METADATA_NOT_FOUND",
        )

    def test_swap_registry_resolves_curated_swap_tokens(self):
        sol = _resolve_swap_token_meta("SOL")
        usdc = _resolve_swap_token_meta("USDC")
        bonk = _resolve_swap_token_meta("BONK")
        wif = _resolve_swap_token_meta("WIF")
        popcat = _resolve_swap_token_meta("POPCAT")
        chad = _resolve_swap_token_meta("CHAD")
        spx6900 = _resolve_swap_token_meta("SPX6900")

        self.assertEqual(sol["mint"], "So11111111111111111111111111111111111111112")
        self.assertEqual(sol["decimals"], 9)
        self.assertEqual(usdc["mint"], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.assertEqual(usdc["decimals"], 6)
        self.assertEqual(bonk["mint"], "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
        self.assertEqual(bonk["decimals"], 5)
        self.assertEqual(bonk["coingecko_id"], "bonk")
        self.assertEqual(wif["mint"], "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm")
        self.assertEqual(wif["decimals"], 6)
        self.assertEqual(wif["coingecko_id"], "dogwifhat")
        self.assertEqual(wif["display_name"], "dogwifhat")
        self.assertEqual(popcat["mint"], "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
        self.assertEqual(popcat["decimals"], 9)
        self.assertEqual(popcat["coingecko_id"], "popcat")
        self.assertEqual(popcat["display_name"], "Popcat")
        self.assertEqual(chad["mint"], "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump")
        self.assertEqual(chad["decimals"], 6)
        self.assertEqual(chad["coingecko_id"], "chad-3")
        self.assertEqual(chad["display_name"], "CHAD")
        self.assertEqual(spx6900["mint"], "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr")
        self.assertEqual(spx6900["decimals"], 8)
        self.assertEqual(spx6900["coingecko_id"], "spx6900")
        self.assertEqual(spx6900["display_name"], "SPX6900")
        figure = _resolve_swap_token_meta("FIGURE")
        self.assertEqual(figure["mint"], "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump")
        self.assertEqual(figure["decimals"], 6)

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
        self.assertEqual(by_symbol["WIF"]["mint"], "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm")
        self.assertEqual(by_symbol["WIF"]["display_name"], "dogwifhat")
        self.assertEqual(by_symbol["WIF"]["decimals"], 6)
        self.assertTrue(by_symbol["WIF"]["default_enabled"])
        self.assertTrue(by_symbol["WIF"]["verified"])
        self.assertEqual(by_symbol["POPCAT"]["mint"], "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
        self.assertEqual(by_symbol["POPCAT"]["display_name"], "Popcat")
        self.assertEqual(by_symbol["POPCAT"]["decimals"], 9)
        self.assertTrue(by_symbol["POPCAT"]["default_enabled"])
        self.assertTrue(by_symbol["POPCAT"]["verified"])
        self.assertEqual(by_symbol["CHAD"]["mint"], "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump")
        self.assertEqual(by_symbol["CHAD"]["decimals"], 6)
        self.assertTrue(by_symbol["CHAD"]["default_enabled"])
        self.assertTrue(by_symbol["CHAD"]["verified"])
        self.assertEqual(by_symbol["SPX6900"]["mint"], "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr")
        self.assertEqual(by_symbol["SPX6900"]["decimals"], 8)
        self.assertTrue(by_symbol["SPX6900"]["default_enabled"])
        self.assertTrue(by_symbol["SPX6900"]["verified"])
        self.assertEqual(by_symbol["FIGURE"]["display_name"], "Action Figure")
        self.assertFalse(by_symbol["FIGURE"]["verified"])
        self.assertNotIn("USDT", by_symbol)

    def test_quote_coverage_audit_parses_explicit_pairs(self):
        from tools.quote_coverage_audit import parse_pair

        self.assertEqual(parse_pair("WIF:SOL"), ("WIF", "SOL"))
        self.assertEqual(parse_pair("popcat:wif"), ("POPCAT", "WIF"))
        self.assertEqual(parse_pair(" USDC : POPCAT "), ("USDC", "POPCAT"))

    def test_quote_coverage_audit_supports_arbitrary_pair_metadata(self):
        from tools import quote_coverage_audit

        calls = []

        def fake_quote_universe(universe, *, input_mint, output_mint, amount_raw, user_public_key):
            calls.append((universe, input_mint, output_mint, amount_raw, user_public_key))
            return {"ok": True, "data": {"outAmount": "1"}}

        with (
            patch.object(quote_coverage_audit, "UNIVERSES", ["Jupiter"]),
            patch.object(quote_coverage_audit, "quote_universe", side_effect=fake_quote_universe),
            patch.object(quote_coverage_audit.time, "sleep") as sleep,
        ):
            result = quote_coverage_audit.audit_pairs(
                [("WIF", "SOL"), ("USDC", "POPCAT")],
                amount=1.0,
                user_public_key="wallet",
                request_delay=0.01,
            )

        self.assertEqual([pair["pair"] for pair in result["pairs"]], ["WIF->SOL", "USDC->POPCAT"])
        self.assertEqual(result["pairs"][0]["amount_raw"], "1000000")
        self.assertEqual(result["pairs"][1]["amount_raw"], "1000000")
        self.assertEqual(calls[0][1], "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm")
        self.assertEqual(calls[0][2], METEORA_DLMM_SOL_MINT)
        self.assertEqual(calls[1][1], METEORA_DLMM_USDC_MINT)
        self.assertEqual(calls[1][2], "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
        sleep.assert_called_once_with(0.01)

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
        self.assertIsNone(baseline["pricing_ts"])
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
        self.assertNotIn("Jupiter reference", html)
        self.assertIn("Source detail: Jupiter Price V3 market price", html)
        self.assertIn("Source detail: DexScreener Solana market pair", html)
        self.assertIn("fmtUsdCost(rawUsd)", html)
        self.assertIn("fmtUsdCost(tradeCostUsd)", html)
        self.assertIn("estimated_output_usd", html)
        self.assertIn('const sign = n < 0 ? "-" : "";', html)
        self.assertIn('return sign + "$" + abs.toFixed(2);', html)

    def test_swap_ui_recommended_and_direct_titles_include_surface(self):
        html = build_ui_html()

        self.assertIn('return "Best quote";', html)
        self.assertIn('if (kind === "recommended") return "Recommended route";', html)
        self.assertIn('if (kind === "direct") return "Direct / simple route";', html)
        self.assertIn('font-weight:600;">${escapeHtml(routeLabel)}</div>', html)
        self.assertIn('title: "Best executable route"', html)
        self.assertNotIn("Recommended executable", html)
        self.assertNotIn("Recommended route</h4>", html)
        self.assertNotIn("Direct route check</h4>", html)
        self.assertIn("Direct route is also the current recommendation.", html)
        self.assertIn("Execution cost: ${escapeHtml(executionCostUsdText)}", html)
        self.assertIn("Route shape:", html)
        self.assertIn("Alternative ${idx + 1} — ${escapeHtml(routeLabel)}", html)

    def test_swap_ui_renders_route_coverage_depth_logic(self):
        html = build_ui_html()

        self.assertIn('id="swapCoverageDepth"', html)
        self.assertIn("function collectLiveRouteCoverageLabels(quote)", html)
        self.assertIn('if (!opt || opt.quote_status !== "live") continue;', html)
        self.assertIn("const key = String(label).trim().toLowerCase();", html)
        self.assertIn("seen.has(key)", html)
        self.assertIn("Limited live route coverage for this pair: ", html)
        self.assertIn("live route options checked: ", html)
        self.assertIn("renderSwapCoverageDepth(quote);", html)

    def test_swap_ui_two_hop_route_display_is_user_facing(self):
        html = build_ui_html()

        self.assertIn("function routeTokenLabelFromMint(mint, opt)", html)
        self.assertIn("function cleanContinuousRouteMints(opt)", html)
        self.assertIn("function formatCleanRoutePath(opt)", html)
        self.assertIn("if (steps.length < 2) return null;", html)
        self.assertIn("return null;", html)
        self.assertIn("mints[mints.length - 1] !== inputMint", html)
        self.assertIn("return `${fromLabel} -> ${middleLabel} -> ${toLabel}`;", html)
        self.assertIn("Route: ${escapeHtml(cleanRoutePath)}", html)
        self.assertIn("Shape: two-hop · Steps: ${escapeHtml(String(routeSteps))}", html)
        self.assertIn("Route shape: ${escapeHtml(routeShape)} · Steps: ${escapeHtml(String(routeSteps))}", html)

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
        self.assertFalse(payload["discover_pools"])
        self.assertFalse(payload["enable_two_hop_discovery"])
        self.assertEqual(
            payload["pool_candidates"][0]["address"],
            "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
        )

    def test_build_meteora_dlmm_quote_payload_adds_sol_bonk_candidate(self):
        payload = _build_meteora_dlmm_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_BONK_MINT,
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(len(payload["pool_candidates"]), 1)
        self.assertFalse(payload["discover_pools"])
        self.assertFalse(payload["enable_two_hop_discovery"])
        self.assertEqual(
            payload["pool_candidates"][0]["address"],
            "6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp",
        )
        self.assertEqual(payload["pool_candidates"][0]["token_x"], METEORA_DLMM_BONK_MINT)
        self.assertEqual(payload["pool_candidates"][0]["token_y"], METEORA_DLMM_SOL_MINT)

    def test_build_meteora_dlmm_quote_payload_has_no_unverified_sol_wif_candidate(self):
        payload = _build_meteora_dlmm_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["discover_pools"])
        self.assertTrue(payload["enable_two_hop_discovery"])
        self.assertGreaterEqual(payload["discovery"]["min_tvl_usd"], 1000)

    def test_build_meteora_dlmm_quote_payload_discovers_new_meme_candidates(self):
        for mint in [
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump",
            "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr",
        ]:
            payload = _build_meteora_dlmm_quote_payload(
                input_mint=METEORA_DLMM_SOL_MINT,
                output_mint=mint,
                amount_raw=1000000000,
                slippage_bps=50,
                rpc_url="https://example.invalid",
            )

            self.assertEqual(payload["pool_candidates"], [])
            self.assertTrue(payload["discover_pools"])
            self.assertTrue(payload["enable_two_hop_discovery"])
            self.assertEqual(payload["discovery"]["api_url"], "https://dlmm.datapi.meteora.ag/pools")
            self.assertGreaterEqual(payload["discovery"]["min_tvl_usd"], 1000)

    def test_build_meteora_dlmm_quote_payload_discovers_sideways_pairs(self):
        payload = _build_meteora_dlmm_quote_payload(
            input_mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            output_mint="7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            amount_raw=1000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["discover_pools"])
        self.assertTrue(payload["enable_two_hop_discovery"])
        self.assertNotIn("unsupported_pair", payload)

    def test_build_meteora_dlmm_quote_payload_enables_two_hop_for_wif_usdc(self):
        payload = _build_meteora_dlmm_quote_payload(
            input_mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            output_mint=METEORA_DLMM_USDC_MINT,
            amount_raw=1000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["discover_pools"])
        self.assertTrue(payload["enable_two_hop_discovery"])

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

    def test_try_fetch_meteora_dlmm_quote_handles_invalid_helper_json(self):
        with patch(
            "api.main.subprocess.run",
            return_value=subprocess.CompletedProcess(["node"], 0, "{not-json", ""),
        ):
            result = _try_fetch_meteora_dlmm_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 502)
        self.assertIn("invalid JSON", result["error"]["detail"])

    def test_try_fetch_meteora_dlmm_quote_reports_low_quality_discovery(self):
        helper_output = {
            "ok": False,
            "error": {
                "code": "NO_USABLE_DISCOVERED_POOL",
                "message": "Discovered Meteora DLMM pools did not pass quality filters.",
                "details": {"rejected_low_tvl_count": 3},
            },
        }

        with patch(
            "api.main.subprocess.run",
            return_value=subprocess.CompletedProcess(["node"], 1, json.dumps(helper_output), ""),
        ):
            result = _try_fetch_meteora_dlmm_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "NO_USABLE_DISCOVERED_POOL")
        self.assertEqual(result["error"]["helper_error"]["details"]["rejected_low_tvl_count"], 3)

    def test_build_orca_whirlpool_quote_payload_supports_sol_usdc(self):
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
        self.assertTrue(payload["discover_pools"])
        self.assertTrue(payload["enable_two_hop_discovery"])
        self.assertEqual(payload["discovery"]["api_url"], "https://api.orca.so/v2/solana/pools")
        self.assertEqual(payload["discovery"]["min_tvl_usdc"], 10000)
        self.assertNotIn("unsupported_pair", payload)

    def test_build_orca_whirlpool_quote_payload_supports_sol_bonk(self):
        payload = _build_orca_whirlpool_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_BONK_MINT,
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["rpc_url"], "https://example.invalid")
        self.assertEqual(payload["amount_raw"], "1000000000")
        self.assertEqual(len(payload["pool_candidates"]), 1)
        self.assertEqual(
            payload["pool_candidates"][0]["address"],
            "5zpyutJu9ee6jFymDGoK7F6S5Kczqtc9FomP3ueKuyA9",
        )
        self.assertEqual(payload["pool_candidates"][0]["token_mint_a"], METEORA_DLMM_BONK_MINT)
        self.assertEqual(payload["pool_candidates"][0]["token_mint_b"], METEORA_DLMM_SOL_MINT)
        self.assertFalse(payload["discover_pools"])
        self.assertFalse(payload["enable_two_hop_discovery"])
        self.assertNotIn("unsupported_pair", payload)

    def test_build_orca_whirlpool_quote_payload_supports_sol_wif(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        payload = _build_orca_whirlpool_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=wif_mint,
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["rpc_url"], "https://example.invalid")
        self.assertEqual(payload["amount_raw"], "1000000000")
        self.assertEqual(len(payload["pool_candidates"]), 1)
        self.assertEqual(
            payload["pool_candidates"][0]["address"],
            "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1",
        )
        self.assertEqual(payload["pool_candidates"][0]["token_mint_a"], wif_mint)
        self.assertEqual(payload["pool_candidates"][0]["token_mint_b"], METEORA_DLMM_SOL_MINT)
        self.assertFalse(payload["discover_pools"])
        self.assertFalse(payload["enable_two_hop_discovery"])
        self.assertNotIn("unsupported_pair", payload)

    def test_build_orca_whirlpool_quote_payload_discovers_new_memes_without_curated_pools(self):
        for mint in [
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump",
            "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr",
        ]:
            payload = _build_orca_whirlpool_quote_payload(
                input_mint=METEORA_DLMM_SOL_MINT,
                output_mint=mint,
                amount_raw=1000000000,
                slippage_bps=50,
                rpc_url="https://example.invalid",
            )

            self.assertEqual(payload["pool_candidates"], [])
            self.assertTrue(payload["discover_pools"])
            self.assertTrue(payload["enable_two_hop_discovery"])
            self.assertEqual(payload["discovery"]["min_tvl_usdc"], 10000)
            self.assertNotIn("unsupported_pair", payload)

    def test_build_orca_whirlpool_quote_payload_discovers_sideways_pairs(self):
        payload = _build_orca_whirlpool_quote_payload(
            input_mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            output_mint="7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            amount_raw=1000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["discover_pools"])
        self.assertTrue(payload["enable_two_hop_discovery"])
        self.assertNotIn("unsupported_pair", payload)

    def test_build_orca_whirlpool_quote_payload_enables_two_hop_for_wif_usdc(self):
        payload = _build_orca_whirlpool_quote_payload(
            input_mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            output_mint=METEORA_DLMM_USDC_MINT,
            amount_raw=1000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["discover_pools"])
        self.assertTrue(payload["enable_two_hop_discovery"])

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

    def test_try_fetch_orca_whirlpool_quote_handles_invalid_helper_json(self):
        with patch(
            "api.main.subprocess.run",
            return_value=subprocess.CompletedProcess(["node"], 0, "{not-json", ""),
        ):
            result = _try_fetch_orca_whirlpool_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 502)
        self.assertIn("invalid JSON", result["error"]["detail"])

    def test_try_fetch_orca_whirlpool_quote_reports_low_quality_discovery(self):
        helper_output = {
            "ok": False,
            "error": {
                "code": "NO_USABLE_DISCOVERED_POOL",
                "message": "Discovered Orca Whirlpool pools did not pass quality filters.",
                "details": {
                    "discovery": {
                        "rejected_low_tvl_count": 2,
                        "usable_pool_count": 0,
                    },
                },
            },
        }

        with patch(
            "api.main.subprocess.run",
            return_value=subprocess.CompletedProcess(["node"], 1, json.dumps(helper_output), ""),
        ):
            result = _try_fetch_orca_whirlpool_quote({"amount_raw": "1000000000"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "NO_USABLE_DISCOVERED_POOL")
        self.assertEqual(
            result["error"]["helper_error"]["details"]["discovery"]["rejected_low_tvl_count"],
            2,
        )

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

    def test_build_phoenix_quote_payload_keeps_sol_bonk_fail_soft(self):
        payload = _build_phoenix_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_BONK_MINT,
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["market_candidates"], [])
        self.assertTrue(payload["unsupported_pair"])
        self.assertIn("SOL -> USDC only", payload["unsupported_pair_detail"])

    def test_build_phoenix_quote_payload_keeps_sol_wif_fail_soft(self):
        payload = _build_phoenix_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
        )

        self.assertEqual(payload["market_candidates"], [])
        self.assertTrue(payload["unsupported_pair"])
        self.assertIn("SOL -> USDC only", payload["unsupported_pair_detail"])

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

    def test_build_pumpswap_quote_payload_adds_docs_pool_for_sol_to_docs_token(self):
        payload = _build_pumpswap_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint="7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertEqual(payload["rpc_url"], "https://example.invalid")
        self.assertEqual(payload["amount_raw"], "1000000000")
        self.assertEqual(payload["user_public_key"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertEqual(len(payload["pool_candidates"]), 1)
        self.assertEqual(
            payload["pool_candidates"][0]["address"],
            "GseMAnNDvntR5uFePZ51yZBXzNSn7GdFPkfHwfr6d77J",
        )
        self.assertNotIn("unsupported_pair", payload)

    def test_build_pumpswap_quote_payload_adds_docs_pool_for_docs_token_to_sol(self):
        payload = _build_pumpswap_quote_payload(
            input_mint="7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
            output_mint=METEORA_DLMM_SOL_MINT,
            amount_raw=1000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertEqual(len(payload["pool_candidates"]), 1)
        self.assertEqual(payload["pool_candidates"][0]["base_mint"], "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump")
        self.assertEqual(payload["pool_candidates"][0]["quote_mint"], METEORA_DLMM_SOL_MINT)
        self.assertNotIn("unsupported_pair", payload)

    def test_build_pumpswap_quote_payload_keeps_sol_wif_fail_soft(self):
        payload = _build_pumpswap_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["unsupported_pair"])
        self.assertIn("FIGURE docs-token pool only", payload["unsupported_pair_detail"])

    def test_build_pumpswap_quote_payload_keeps_new_memes_fail_soft(self):
        for mint in [
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump",
            "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr",
        ]:
            payload = _build_pumpswap_quote_payload(
                input_mint=METEORA_DLMM_SOL_MINT,
                output_mint=mint,
                amount_raw=1000000000,
                slippage_bps=50,
                rpc_url="https://example.invalid",
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

            self.assertEqual(payload["pool_candidates"], [])
            self.assertTrue(payload["unsupported_pair"])

    def test_try_fetch_pumpswap_quote_handles_unsupported_pair_without_fake_card(self):
        payload = _build_pumpswap_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_BONK_MINT,
            amount_raw=1000000000,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        result = _try_fetch_pumpswap_quote(payload)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 400)
        self.assertIn("PumpSwap", result["error"]["detail"])

    def test_fetch_pumpswap_quote_uses_subprocess_json_contract(self):
        helper_output = {
            "ok": True,
            "provider": "pumpswap",
            "out_amount_raw": "123456789",
        }

        def fake_run(cmd, **kwargs):
            self.assertIn("tools/pumpswap_quote_research.mjs", cmd[1])
            payload = json.loads(kwargs["input"])
            self.assertEqual(payload["user_public_key"], "wallet")
            self.assertFalse(kwargs.get("shell", False))
            self.assertGreater(kwargs["timeout"], 0)
            return subprocess.CompletedProcess(cmd, 0, json.dumps(helper_output), "")

        with patch("api.main.subprocess.run", side_effect=fake_run):
            result = _fetch_pumpswap_quote(
                {
                    "rpc_url": "https://example.invalid",
                    "input_mint": METEORA_DLMM_SOL_MINT,
                    "output_mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
                    "amount_raw": "1000000000",
                    "slippage_bps": 50,
                    "user_public_key": "wallet",
                    "pool_candidates": [dict(address="pool")],
                }
            )

        self.assertEqual(result, helper_output)

    def test_try_fetch_pumpswap_quote_handles_timeout(self):
        with patch("api.main.subprocess.run", side_effect=subprocess.TimeoutExpired("node", 20)):
            result = _try_fetch_pumpswap_quote(
                {
                    "rpc_url": "https://example.invalid",
                    "input_mint": METEORA_DLMM_SOL_MINT,
                    "output_mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
                    "amount_raw": "1000000000",
                    "user_public_key": "wallet",
                    "pool_candidates": [dict(address="pool")],
                }
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["status_code"], 504)

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
        self.assertFalse(payload["buy_token_is_native"])
        self.assertEqual(payload["sell_token_mint"], METEORA_DLMM_SOL_MINT)
        self.assertEqual(payload["buy_token_mint"], METEORA_DLMM_USDC_MINT)
        self.assertEqual(payload["amount"], "1000000000")
        self.assertEqual(payload["amount_unit"], "base")
        self.assertEqual(payload["slippage_bps"], 50)
        self.assertEqual(payload["taker_address"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertNotIn("unsupported_pair", payload)
        self.assertNotIn("skip_reason", payload)

    def test_build_phantom_quote_payload_supports_sol_to_bonk(self):
        payload = _build_phantom_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            amount_raw=1000000000,
            slippage_bps=50,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertTrue(payload["sell_token_is_native"])
        self.assertEqual(payload["buy_token_mint"], "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
        self.assertEqual(payload["taker_address"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertNotIn("unsupported_pair", payload)
        self.assertNotIn("skip_reason", payload)

    def test_build_phantom_quote_payload_supports_sol_to_wif(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        payload = _build_phantom_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=wif_mint,
            amount_raw=1000000000,
            slippage_bps=50,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertTrue(payload["sell_token_is_native"])
        self.assertEqual(payload["buy_token_mint"], wif_mint)
        self.assertEqual(payload["taker_address"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertNotIn("unsupported_pair", payload)
        self.assertNotIn("skip_reason", payload)

    def test_build_phantom_quote_payload_supports_sol_to_new_memes(self):
        for mint in [
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
            "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump",
            "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr",
        ]:
            payload = _build_phantom_quote_payload(
                input_mint=METEORA_DLMM_SOL_MINT,
                output_mint=mint,
                amount_raw=1000000000,
                slippage_bps=50,
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

            self.assertTrue(payload["sell_token_is_native"])
            self.assertEqual(payload["buy_token_mint"], mint)
            self.assertEqual(payload["taker_address"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
            self.assertNotIn("unsupported_pair", payload)
            self.assertNotIn("skip_reason", payload)

    def test_build_phantom_quote_payload_supports_sideways_default_enabled_pairs(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        popcat_mint = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
        payload = _build_phantom_quote_payload(
            input_mint=wif_mint,
            output_mint=popcat_mint,
            amount_raw=1000000,
            slippage_bps=50,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertFalse(payload["sell_token_is_native"])
        self.assertEqual(payload["sell_token_mint"], wif_mint)
        self.assertFalse(payload["buy_token_is_native"])
        self.assertEqual(payload["buy_token_mint"], popcat_mint)
        self.assertNotIn("unsupported_pair", payload)
        self.assertNotIn("skip_reason", payload)

    def test_build_phantom_quote_payload_supports_exit_to_sol(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        payload = _build_phantom_quote_payload(
            input_mint=wif_mint,
            output_mint=METEORA_DLMM_SOL_MINT,
            amount_raw=1000000,
            slippage_bps=50,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertFalse(payload["sell_token_is_native"])
        self.assertEqual(payload["sell_token_mint"], wif_mint)
        self.assertTrue(payload["buy_token_is_native"])
        self.assertEqual(payload["buy_token_mint"], METEORA_DLMM_SOL_MINT)
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

    def test_normalize_pumpswap_quote_option_marks_quote_only_non_clickable(self):
        quote = {
            "ok": True,
            "provider": "pumpswap",
            "direction": "buy_base_with_quote",
            "pool": {
                "address": "GseMAnNDvntR5uFePZ51yZBXzNSn7GdFPkfHwfr6d77J",
                "name": "official-docs-example",
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
            "in_amount_raw": "1000000000",
            "out_amount_raw": "45000000",
            "base_reserve_raw": "1000000000000",
            "quote_reserve_raw": "2000000000",
            "slippage_bps": 50,
        }

        option = _normalize_pumpswap_quote_option(
            variant_id="pumpswap_quote",
            label="Via PumpSwap",
            kind="alternative",
            quote=quote,
            from_token="SOL",
            to_token="FIGURE",
            input_amount=1.0,
            input_amount_raw=1000000000,
            output_decimals=6,
        )

        self.assertEqual(option["provider"], "pumpswap")
        self.assertEqual(option["execution_surface_label"], "PumpSwap")
        self.assertEqual(option["quote_status"], "live")
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_native_pool_sdk")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertEqual(option["route_shape"], "single-pool")
        self.assertEqual(option["estimated_output"], 45.0)
        self.assertIsNone(option["min_received"])
        self.assertFalse(option["explicit_route_fees"]["has_explicit_fees"])
        self.assertEqual(option["_sort_out_amount_raw"], 45000000)

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
            "discovery": {
                "selected_pool": {
                    "address": "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6",
                    "tvl": 100000,
                },
            },
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
        self.assertEqual(option["raw_quote"]["discovery"]["selected_pool"]["tvl"], 100000)
        self.assertEqual(option["_sort_out_amount_raw"], 84019465)

    def test_normalize_meteora_dlmm_two_hop_quote_option_marks_comparison_only(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "route_shape": "two-hop",
            "pool": {
                "address": "8Ve9KtGNtLRxCQNAVfkHEP5GRZHjdj6BjB1RQFZewG6V",
                "name": "$WIF-SOL",
                "bin_step": 50,
            },
            "input_mint": wif_mint,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "intermediate_mint": METEORA_DLMM_SOL_MINT,
            "in_amount_raw": "1000000",
            "out_amount_raw": "180000",
            "min_out_amount_raw": "179100",
            "price_impact": "0",
            "route_steps": [
                {
                    "label": "Meteora DLMM leg 1",
                    "pool_address": "8Ve9KtGNtLRxCQNAVfkHEP5GRZHjdj6BjB1RQFZewG6V",
                    "input_mint": wif_mint,
                    "output_mint": METEORA_DLMM_SOL_MINT,
                    "out_amount_raw": "2140000",
                },
                {
                    "label": "Meteora DLMM leg 2",
                    "pool_address": "BGm1tav58oGcsQJehL9WXBFXF7D27vZsKefj4xJKD5Y",
                    "input_mint": METEORA_DLMM_SOL_MINT,
                    "output_mint": METEORA_DLMM_USDC_MINT,
                    "out_amount_raw": "180000",
                },
            ],
            "discovery": {
                "route_type": "venue_restricted_two_hop",
                "intermediate_mint": METEORA_DLMM_SOL_MINT,
            },
        }

        option = _normalize_meteora_dlmm_quote_option(
            variant_id="meteora_dlmm_quote",
            label="Via Meteora",
            kind="alternative",
            quote=quote,
            from_token="WIF",
            to_token="USDC",
            input_amount=1.0,
            input_amount_raw=1000000,
            output_decimals=6,
        )

        self.assertEqual(option["provider"], "meteora-dlmm")
        self.assertEqual(option["quote_status"], "live")
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertEqual(option["route_shape"], "two-hop")
        self.assertEqual(option["route_step_count"], 2)
        self.assertEqual(option["route_steps"][0]["pool_address"], "8Ve9KtGNtLRxCQNAVfkHEP5GRZHjdj6BjB1RQFZewG6V")
        self.assertEqual(option["route_steps"][1]["pool_address"], "BGm1tav58oGcsQJehL9WXBFXF7D27vZsKefj4xJKD5Y")
        self.assertEqual(option["estimated_output"], 0.18)
        self.assertEqual(option["min_received"], 0.1791)
        self.assertEqual(option["_sort_out_amount_raw"], 180000)

    def test_normalize_orca_whirlpool_quote_option_marks_quote_only_non_clickable(self):
        quote = {
            "ok": True,
            "provider": "orca_whirlpool",
            "pool": {
                "address": "AHTTzwf3GmVMJdxWM8v2MSxyjZj8rQR6hyAC3g9477Yj",
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
            "discovery": {
                "selected_pool": {
                    "address": "AHTTzwf3GmVMJdxWM8v2MSxyjZj8rQR6hyAC3g9477Yj",
                    "tvl_usdc": 26800,
                    "volume_24h": 28500,
                },
            },
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
        self.assertEqual(option["raw_quote"]["discovery"]["selected_pool"]["tvl_usdc"], 26800)
        self.assertEqual(option["raw_quote"]["discovery"]["selected_pool"]["volume_24h"], 28500)

    def test_normalize_orca_whirlpool_two_hop_quote_option_marks_quote_only_non_clickable(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        quote = {
            "ok": True,
            "provider": "orca_whirlpool",
            "route_shape": "two-hop",
            "pool": {
                "address": "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1",
                "name": "WIF-SOL",
                "tick_spacing": 4,
                "fee_rate": 400,
            },
            "input_mint": wif_mint,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "intermediate_mint": METEORA_DLMM_SOL_MINT,
            "in_amount_raw": "1000000",
            "out_amount_raw": "180000",
            "min_out_amount_raw": "179100",
            "route_steps": [
                {
                    "label": "Orca Whirlpool leg 1",
                    "pool_address": "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1",
                    "input_mint": wif_mint,
                    "output_mint": METEORA_DLMM_SOL_MINT,
                    "out_amount_raw": "2140000",
                },
                {
                    "label": "Orca Whirlpool leg 2",
                    "pool_address": "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
                    "input_mint": METEORA_DLMM_SOL_MINT,
                    "output_mint": METEORA_DLMM_USDC_MINT,
                    "out_amount_raw": "180000",
                },
            ],
            "discovery": {
                "route_type": "venue_restricted_two_hop",
                "intermediate_mint": METEORA_DLMM_SOL_MINT,
            },
        }

        option = _normalize_orca_whirlpool_quote_option(
            variant_id="orca_whirlpool_quote",
            label="Via Orca",
            kind="alternative",
            quote=quote,
            from_token="WIF",
            to_token="USDC",
            input_amount=1.0,
            input_amount_raw=1000000,
            output_decimals=6,
        )

        self.assertEqual(option["provider"], "orca-whirlpool")
        self.assertEqual(option["quote_status"], "live")
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertEqual(option["route_shape"], "two-hop")
        self.assertEqual(option["route_step_count"], 2)
        self.assertEqual(option["route_steps"][0]["pool_address"], "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1")
        self.assertEqual(option["route_steps"][1]["pool_address"], "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE")
        self.assertEqual(option["estimated_output"], 0.18)
        self.assertEqual(option["min_received"], 0.1791)
        self.assertEqual(option["_sort_out_amount_raw"], 180000)

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
        self.assertAlmostEqual(response["recommended_option"]["estimated_output_usd"], 81.0)
        raydium_option = next(
            opt for opt in response["other_options"] if opt["provider"] == "raydium-trade-api"
        )
        self.assertAlmostEqual(raydium_option["estimated_trade_execution_cost"]["amount"], 600000.0)
        self.assertAlmostEqual(raydium_option["estimated_trade_execution_cost"]["amount_usd"], 3.6)
        self.assertAlmostEqual(raydium_option["estimated_output_usd"], 80.4)
        self.assertNotEqual(
            raydium_option["estimated_trade_execution_cost"]["amount"],
            raydium_option["estimated_trade_execution_cost"]["amount_usd"],
        )

    def test_swap_quote_sol_to_bonk_can_include_phantom_alternative(self):
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
            "routePlan": [],
        }
        phantom_quote = {
            "ok": True,
            "status_code": 200,
            "first_quote_buyAmount": "1345000000000",
            "quoteResponse": {
                "quotes": [
                    {
                        "buyAmount": "1345000000000",
                        "baseProvider": {"id": "phantom", "name": "Phantom"},
                        "sources": [{"name": "Phantom Route", "proportion": 1}],
                    }
                ]
            },
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value={"ok": True, "data": phantom_quote}) as fetch_phantom,
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "BONK": {"usd": 0.000006},
                },
            ),
        ):
            response = swap_quote(
                from_token="SOL",
                to_token="BONK",
                amount=1.0,
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(fetch_phantom.call_args.args[0]["buy_token_mint"], bonk_mint)
        phantom_option = next(
            opt for opt in response["other_options"] if opt["provider"] == "phantom-routing-api"
        )
        self.assertEqual(phantom_option["execution_surface_label"], "Phantom")
        self.assertEqual(phantom_option["quote_status"], "live")
        self.assertEqual(phantom_option["execution_status"], "quote_only")
        self.assertEqual(phantom_option["quote_source_type"], "wallet_routing_api")
        self.assertTrue(phantom_option["is_comparison_only"])
        self.assertFalse(phantom_option["is_clickable"])
        self.assertTrue(phantom_option["is_official_quote"])
        self.assertEqual(phantom_option["estimated_output"], 13450000.0)
        self.assertAlmostEqual(phantom_option["estimated_output_usd"], 80.7)

    def test_swap_quote_sol_to_bonk_can_show_successful_real_universes(self):
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
            "routePlan": [],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": sol_mint,
                "inputAmount": "1000000000",
                "outputMint": bonk_mint,
                "outputAmount": "1349000000000",
                "otherAmountThreshold": "1342255000000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }
        meteora_quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {
                "address": "6oFWm7KPLfxnwMb3z5xwBoXNSPP3JJyirAPqPSiVcnsp",
                "name": "BONK-SOL",
            },
            "input_mint": sol_mint,
            "output_mint": bonk_mint,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "1348000000000",
            "min_out_amount_raw": "1341260000000",
            "fee_raw": "500030",
            "protocol_fee_raw": "50002",
            "price_impact": "0",
            "bin_arrays": ["bin"],
        }
        orca_quote = {
            "ok": True,
            "provider": "orca_whirlpool",
            "pool": {
                "address": "orca_pool",
                "name": "BONK-SOL",
                "token_mint_a": bonk_mint,
                "token_mint_b": sol_mint,
            },
            "input_mint": sol_mint,
            "output_mint": bonk_mint,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "1347000000000",
            "min_out_amount_raw": "1340265000000",
            "fee_raw": "400000",
            "slippage_bps": 50,
        }
        phantom_quote = {
            "ok": True,
            "status_code": 200,
            "first_quote_buyAmount": "1346000000000",
            "quoteResponse": {
                "quotes": [
                    {
                        "buyAmount": "1346000000000",
                        "baseProvider": {"id": "phantom", "name": "Phantom"},
                    }
                ]
            },
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
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
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value={"ok": True, "data": phantom_quote}),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "BONK": {"usd": 0.000006},
                },
            ),
        ):
            response = swap_quote(
                from_token="SOL",
                to_token="BONK",
                amount=1.0,
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        visible = [
            response["recommended_option"],
            response["direct_route_check"],
            *response["other_options"],
        ]
        visible_providers = {opt["provider"] for opt in visible if opt}
        self.assertIn("jupiter-metis", visible_providers)
        self.assertIn("raydium-trade-api", visible_providers)
        self.assertIn("meteora-dlmm", visible_providers)
        self.assertIn("orca-whirlpool", visible_providers)
        self.assertIn("phantom-routing-api", visible_providers)
        self.assertNotIn("phoenix-clob", visible_providers)
        for provider in ["meteora-dlmm", "orca-whirlpool", "phantom-routing-api"]:
            option = next(opt for opt in visible if opt and opt["provider"] == provider)
            self.assertTrue(option["is_comparison_only"])
            self.assertFalse(option["is_clickable"])
            self.assertIsNotNone(option["estimated_output_usd"])

    def test_swap_quote_sol_to_wif_can_show_successful_real_universes(self):
        sol_mint = "So11111111111111111111111111111111111111112"
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        jupiter_quote = {
            "inputMint": sol_mint,
            "inAmount": "1000000000",
            "outputMint": wif_mint,
            "outAmount": "440000000",
            "otherAmountThreshold": "437800000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [],
        }
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": sol_mint,
                "inputAmount": "1000000000",
                "outputMint": wif_mint,
                "outputAmount": "438000000",
                "otherAmountThreshold": "435810000",
                "slippageBps": 50,
                "priceImpactPct": 0,
                "routePlan": [],
            },
        }
        orca_quote = {
            "ok": True,
            "provider": "orca_whirlpool",
            "pool": {
                "address": "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1",
                "name": "WIF-SOL",
                "token_mint_a": wif_mint,
                "token_mint_b": sol_mint,
            },
            "input_mint": sol_mint,
            "output_mint": wif_mint,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "436916834",
            "min_out_amount_raw": "434732249",
            "fee_raw": "400000",
            "slippage_bps": 50,
        }
        meteora_quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {
                "address": "8Ve9KtGNtLRxCQNAVfkHEP5GRZHjdj6BjB1RQFZewG6V",
                "name": "$WIF-SOL",
                "bin_step": 50,
            },
            "input_mint": sol_mint,
            "output_mint": wif_mint,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "436750000",
            "min_out_amount_raw": "434566250",
            "fee_raw": "400000",
            "protocol_fee_raw": "20000",
            "price_impact": "0",
            "bin_arrays": ["bin"],
            "discovery": {
                "selected_pool": {
                    "address": "8Ve9KtGNtLRxCQNAVfkHEP5GRZHjdj6BjB1RQFZewG6V",
                    "tvl": 100000,
                },
            },
        }
        phantom_quote = {
            "ok": True,
            "status_code": 200,
            "first_quote_buyAmount": "436500000",
            "quoteResponse": {
                "quotes": [
                    {
                        "buyAmount": "436500000",
                        "baseProvider": {"id": "phantom", "name": "Phantom"},
                    }
                ]
            },
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value={"ok": True, "data": raydium_quote}),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": meteora_quote}) as fetch_meteora,
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value={"ok": True, "data": orca_quote}) as fetch_orca,
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported) as fetch_phoenix,
            patch("api.main._try_fetch_phantom_quote", return_value={"ok": True, "data": phantom_quote}) as fetch_phantom,
            patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported) as fetch_pumpswap,
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "WIF": {"usd": 0.19},
                },
            ),
        ):
            response = swap_quote(
                from_token="SOL",
                to_token="WIF",
                amount=1.0,
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(response["to_token"], "WIF")
        self.assertEqual(fetch_orca.call_args.args[0]["pool_candidates"][0]["address"], "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1")
        self.assertFalse(fetch_orca.call_args.args[0]["discover_pools"])
        self.assertEqual(fetch_phantom.call_args.args[0]["buy_token_mint"], wif_mint)
        self.assertEqual(fetch_meteora.call_args.args[0]["pool_candidates"], [])
        self.assertTrue(fetch_meteora.call_args.args[0]["discover_pools"])
        self.assertEqual(fetch_phoenix.call_args.args[0]["market_candidates"], [])
        self.assertEqual(fetch_pumpswap.call_args.args[0]["pool_candidates"], [])

        visible = [
            response["recommended_option"],
            response["direct_route_check"],
            *response["other_options"],
        ]
        visible_providers = {opt["provider"] for opt in visible if opt}
        self.assertIn("jupiter-metis", visible_providers)
        self.assertIn("raydium-trade-api", visible_providers)
        self.assertIn("meteora-dlmm", visible_providers)
        self.assertIn("orca-whirlpool", visible_providers)
        self.assertIn("phantom-routing-api", visible_providers)
        self.assertNotIn("phoenix-clob", visible_providers)
        self.assertNotIn("pumpswap", visible_providers)

        for provider in ["meteora-dlmm", "orca-whirlpool", "phantom-routing-api"]:
            option = next(opt for opt in visible if opt and opt["provider"] == provider)
            self.assertEqual(option["quote_status"], "live")
            self.assertEqual(option["execution_status"], "quote_only")
            self.assertTrue(option["is_comparison_only"])
            self.assertFalse(option["is_clickable"])
            self.assertIsNotNone(option["estimated_output_usd"])

    def test_swap_quote_accepts_new_curated_meme_tokens_without_fake_cards(self):
        sol_mint = "So11111111111111111111111111111111111111112"
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }
        cases = [
            ("POPCAT", "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "125000000000", 125.0, 0.06),
            ("CHAD", "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump", "9000000", 9.0, 0.000007),
            ("SPX6900", "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr", "25000000000", 250.0, 0.3),
        ]

        for symbol, mint, out_amount_raw, estimated_output, usd_price in cases:
            jupiter_quote = {
                "inputMint": sol_mint,
                "inAmount": "1000000000",
                "outputMint": mint,
                "outAmount": out_amount_raw,
                "otherAmountThreshold": str(int(out_amount_raw) - 1),
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
                patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
                patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported) as fetch_meteora,
                patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported) as fetch_orca,
                patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
                patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
                patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
                patch(
                    "api.main._resolve_quote_reference_prices_usd",
                    return_value={
                        "SOL": {"usd": 84.0},
                        symbol: {"usd": usd_price},
                    },
                ),
            ):
                response = swap_quote(from_token="SOL", to_token=symbol, amount=1.0)

            self.assertEqual(response["to_token"], symbol)
            self.assertEqual(response["recommended_option"]["provider"], "jupiter-metis")
            self.assertAlmostEqual(response["recommended_option"]["estimated_output"], estimated_output)
            self.assertEqual(fetch_meteora.call_args.args[0]["pool_candidates"], [])
            self.assertTrue(fetch_meteora.call_args.args[0]["discover_pools"])
            self.assertEqual(fetch_orca.call_args.args[0]["pool_candidates"], [])
            self.assertTrue(fetch_orca.call_args.args[0]["discover_pools"])
            visible = [
                response["recommended_option"],
                response["direct_route_check"],
                *response["other_options"],
            ]
            visible_providers = {opt["provider"] for opt in visible if opt}
            self.assertNotIn("meteora-dlmm", visible_providers)
            self.assertNotIn("orca-whirlpool", visible_providers)
            self.assertNotIn("phoenix-clob", visible_providers)
            self.assertNotIn("pumpswap", visible_providers)

    def test_swap_quote_wif_usdc_can_include_meteora_two_hop_quote(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        jupiter_quote = {
            "inputMint": wif_mint,
            "inAmount": "1000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "178000",
            "otherAmountThreshold": "177110",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "0.18",
            "routePlan": [],
        }
        meteora_quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "route_shape": "two-hop",
            "pool": {
                "address": "8Ve9KtGNtLRxCQNAVfkHEP5GRZHjdj6BjB1RQFZewG6V",
                "name": "$WIF-SOL",
                "bin_step": 50,
            },
            "input_mint": wif_mint,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "intermediate_mint": METEORA_DLMM_SOL_MINT,
            "in_amount_raw": "1000000",
            "out_amount_raw": "180000",
            "min_out_amount_raw": "179100",
            "route_steps": [
                {
                    "pool_address": "8Ve9KtGNtLRxCQNAVfkHEP5GRZHjdj6BjB1RQFZewG6V",
                    "input_mint": wif_mint,
                    "output_mint": METEORA_DLMM_SOL_MINT,
                },
                {
                    "pool_address": "BGm1tav58oGcsQJehL9WXBFXF7D27vZsKefj4xJKD5Y",
                    "input_mint": METEORA_DLMM_SOL_MINT,
                    "output_mint": METEORA_DLMM_USDC_MINT,
                },
            ],
            "discovery": {
                "route_type": "venue_restricted_two_hop",
                "intermediate_mint": METEORA_DLMM_SOL_MINT,
            },
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": meteora_quote}) as fetch_meteora,
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
            patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "WIF": {"usd": 0.18},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="WIF", to_token="USDC", amount=1.0)

        self.assertTrue(fetch_meteora.call_args.args[0]["discover_pools"])
        self.assertTrue(fetch_meteora.call_args.args[0]["enable_two_hop_discovery"])
        self.assertEqual(fetch_meteora.call_args.args[0]["pool_candidates"], [])
        visible = [
            response["recommended_option"],
            response["direct_route_check"],
            *response["other_options"],
        ]
        meteora_option = next(opt for opt in visible if opt and opt["provider"] == "meteora-dlmm")
        self.assertEqual(meteora_option["route_shape"], "two-hop")
        self.assertEqual(meteora_option["route_step_count"], 2)
        self.assertTrue(meteora_option["is_comparison_only"])
        self.assertFalse(meteora_option["is_clickable"])

    def test_swap_quote_meteora_two_hop_leg_failures_do_not_create_fake_card(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        jupiter_quote = {
            "inputMint": wif_mint,
            "inAmount": "1000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "178000",
            "otherAmountThreshold": "177110",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "0.18",
            "routePlan": [],
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        cases = [
            ("TWO_HOP_LEG_1_FAILED", "Meteora DLMM two-hop quote failed on the input-to-SOL leg."),
            ("TWO_HOP_LEG_2_FAILED", "Meteora DLMM two-hop quote failed on the SOL-to-output leg."),
        ]
        for code, detail in cases:
            with self.subTest(code=code):
                meteora_leg_failure = {
                    "ok": False,
                    "error": {
                        "status_code": 502,
                        "detail": detail,
                        "code": code,
                    },
                }

                with (
                    patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
                    patch(
                        "api.main._try_fetch_jupiter_quote",
                        return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
                    ),
                    patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
                    patch("api.main._try_fetch_meteora_dlmm_quote", return_value=meteora_leg_failure),
                    patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
                    patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
                    patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
                    patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
                    patch(
                        "api.main._resolve_quote_reference_prices_usd",
                        return_value={
                            "WIF": {"usd": 0.18},
                            "USDC": {"usd": 1.0},
                        },
                    ),
                ):
                    response = swap_quote(from_token="WIF", to_token="USDC", amount=1.0)

                visible = [
                    response["recommended_option"],
                    response["direct_route_check"],
                    *response["other_options"],
                ]
                self.assertNotIn("meteora-dlmm", {opt["provider"] for opt in visible if opt})
                meteora_errors = [
                    item for item in response["debug"]["variant_errors"]
                    if item["variant_id"] == "meteora_dlmm_quote"
                ]
                self.assertEqual(meteora_errors[0]["code"], code)

    def test_swap_quote_wif_usdc_can_include_orca_two_hop_quote(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        jupiter_quote = {
            "inputMint": wif_mint,
            "inAmount": "1000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "178000",
            "otherAmountThreshold": "177110",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "0.18",
            "routePlan": [],
        }
        orca_quote = {
            "ok": True,
            "provider": "orca_whirlpool",
            "route_shape": "two-hop",
            "pool": {
                "address": "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1",
                "name": "WIF-SOL",
                "tick_spacing": 4,
                "fee_rate": 400,
            },
            "input_mint": wif_mint,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "intermediate_mint": METEORA_DLMM_SOL_MINT,
            "in_amount_raw": "1000000",
            "out_amount_raw": "181000",
            "min_out_amount_raw": "180095",
            "route_steps": [
                {
                    "pool_address": "D6NdKrKNQPmRZCCnG1GqXtF7MMoHB7qR6GU5TkG59Qz1",
                    "input_mint": wif_mint,
                    "output_mint": METEORA_DLMM_SOL_MINT,
                },
                {
                    "pool_address": "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
                    "input_mint": METEORA_DLMM_SOL_MINT,
                    "output_mint": METEORA_DLMM_USDC_MINT,
                },
            ],
            "discovery": {
                "route_type": "venue_restricted_two_hop",
                "intermediate_mint": METEORA_DLMM_SOL_MINT,
            },
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value={"ok": True, "data": orca_quote}) as fetch_orca,
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
            patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "WIF": {"usd": 0.18},
                    "USDC": {"usd": 1.0},
                },
            ),
        ):
            response = swap_quote(from_token="WIF", to_token="USDC", amount=1.0)

        self.assertTrue(fetch_orca.call_args.args[0]["discover_pools"])
        self.assertTrue(fetch_orca.call_args.args[0]["enable_two_hop_discovery"])
        self.assertEqual(fetch_orca.call_args.args[0]["pool_candidates"], [])
        visible = [
            response["recommended_option"],
            response["direct_route_check"],
            *response["other_options"],
        ]
        orca_option = next(opt for opt in visible if opt and opt["provider"] == "orca-whirlpool")
        self.assertEqual(orca_option["route_shape"], "two-hop")
        self.assertEqual(orca_option["route_step_count"], 2)
        self.assertTrue(orca_option["is_comparison_only"])
        self.assertFalse(orca_option["is_clickable"])

    def test_swap_quote_orca_two_hop_leg_failures_do_not_create_fake_card(self):
        wif_mint = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
        jupiter_quote = {
            "inputMint": wif_mint,
            "inAmount": "1000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": "178000",
            "otherAmountThreshold": "177110",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "0.18",
            "routePlan": [],
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }
        cases = [
            ("TWO_HOP_LEG_1_FAILED", "Orca Whirlpool two-hop quote failed on the input-to-SOL leg."),
            ("TWO_HOP_LEG_2_FAILED", "Orca Whirlpool two-hop quote failed on the SOL-to-output leg."),
        ]
        for code, detail in cases:
            with self.subTest(code=code):
                orca_leg_failure = {
                    "ok": False,
                    "error": {
                        "status_code": 502,
                        "detail": detail,
                        "code": code,
                    },
                }

                with (
                    patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
                    patch(
                        "api.main._try_fetch_jupiter_quote",
                        return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
                    ),
                    patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
                    patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
                    patch("api.main._try_fetch_orca_whirlpool_quote", return_value=orca_leg_failure),
                    patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
                    patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
                    patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
                    patch(
                        "api.main._resolve_quote_reference_prices_usd",
                        return_value={
                            "WIF": {"usd": 0.18},
                            "USDC": {"usd": 1.0},
                        },
                    ),
                ):
                    response = swap_quote(from_token="WIF", to_token="USDC", amount=1.0)

                visible = [
                    response["recommended_option"],
                    response["direct_route_check"],
                    *response["other_options"],
                ]
                self.assertNotIn("orca-whirlpool", {opt["provider"] for opt in visible if opt})
                orca_errors = [
                    item for item in response["debug"]["variant_errors"]
                    if item["variant_id"] == "orca_whirlpool_quote"
                ]
                self.assertEqual(orca_errors[0]["code"], code)

    def test_swap_quote_popcat_and_spx_can_include_discovered_meteora_quote(self):
        sol_mint = "So11111111111111111111111111111111111111112"
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }
        cases = [
            (
                "POPCAT",
                "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
                "125000000000",
                "124000000000",
                "EbLiu3GfBYh9cfxrdrfhQgbZJmXqch38NmzZKZSkFGGq",
                0.06,
            ),
            (
                "SPX6900",
                "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr",
                "25000000000",
                "24900000000",
                "62KR7tk1KWARJ9PdCgoK9tTcTJBvDjB1aEcdr8myxKXN",
                0.3,
            ),
        ]

        for symbol, mint, jupiter_out_raw, meteora_out_raw, pool_address, usd_price in cases:
            jupiter_quote = {
                "inputMint": sol_mint,
                "inAmount": "1000000000",
                "outputMint": mint,
                "outAmount": jupiter_out_raw,
                "otherAmountThreshold": str(int(jupiter_out_raw) - 1),
                "slippageBps": 50,
                "priceImpactPct": "0",
                "swapUsdValue": "84",
                "routePlan": [],
            }
            meteora_quote = {
                "ok": True,
                "provider": "meteora_dlmm",
                "pool": {
                    "address": pool_address,
                    "name": f"{symbol}-SOL",
                    "bin_step": 100,
                },
                "input_mint": sol_mint,
                "output_mint": mint,
                "in_amount_raw": "1000000000",
                "out_amount_raw": meteora_out_raw,
                "min_out_amount_raw": str(int(meteora_out_raw) - 1),
                "fee_raw": "400000",
                "protocol_fee_raw": "20000",
                "price_impact": "0",
                "bin_arrays": ["bin"],
                "discovery": {
                    "selected_pool": {
                        "address": pool_address,
                        "tvl": 100000,
                    },
                },
            }

            with (
                patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
                patch(
                    "api.main._try_fetch_jupiter_quote",
                    return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
                ),
                patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
                patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": meteora_quote}) as fetch_meteora,
                patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
                patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
                patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
                patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
                patch(
                    "api.main._resolve_quote_reference_prices_usd",
                    return_value={
                        "SOL": {"usd": 84.0},
                        symbol: {"usd": usd_price},
                    },
                ),
            ):
                response = swap_quote(from_token="SOL", to_token=symbol, amount=1.0)

            self.assertEqual(fetch_meteora.call_args.args[0]["pool_candidates"], [])
            self.assertTrue(fetch_meteora.call_args.args[0]["discover_pools"])
            visible = [
                response["recommended_option"],
                response["direct_route_check"],
                *response["other_options"],
            ]
            meteora_option = next(opt for opt in visible if opt and opt["provider"] == "meteora-dlmm")
            self.assertEqual(meteora_option["quote_status"], "live")
            self.assertEqual(meteora_option["execution_status"], "quote_only")
            self.assertTrue(meteora_option["is_comparison_only"])
            self.assertFalse(meteora_option["is_clickable"])
            self.assertEqual(meteora_option["raw_quote"]["discovery"]["selected_pool"]["address"], pool_address)

    def test_swap_quote_popcat_and_spx_can_include_discovered_orca_quote(self):
        sol_mint = "So11111111111111111111111111111111111111112"
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }
        cases = [
            (
                "POPCAT",
                "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
                "125000000000",
                "123000000000",
                "AHTTzwf3GmVMJdxWM8v2MSxyjZj8rQR6hyAC3g9477Yj",
                0.06,
            ),
            (
                "SPX6900",
                "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr",
                "25000000000",
                "24800000000",
                "orca_spx_pool",
                0.3,
            ),
        ]

        for symbol, mint, jupiter_out_raw, orca_out_raw, pool_address, usd_price in cases:
            jupiter_quote = {
                "inputMint": sol_mint,
                "inAmount": "1000000000",
                "outputMint": mint,
                "outAmount": jupiter_out_raw,
                "otherAmountThreshold": str(int(jupiter_out_raw) - 1),
                "slippageBps": 50,
                "priceImpactPct": "0",
                "swapUsdValue": "84",
                "routePlan": [],
            }
            orca_quote = {
                "ok": True,
                "provider": "orca_whirlpool",
                "pool": {
                    "address": pool_address,
                    "name": f"{symbol}-SOL",
                    "tick_spacing": 64,
                    "fee_rate": 3000,
                },
                "input_mint": sol_mint,
                "output_mint": mint,
                "in_amount_raw": "1000000000",
                "out_amount_raw": orca_out_raw,
                "min_out_amount_raw": str(int(orca_out_raw) - 1),
                "fee_raw": "3000000",
                "slippage_bps": 50,
                "discovery": {
                    "selected_pool": {
                        "address": pool_address,
                        "tvl_usdc": 26800 if symbol == "POPCAT" else 100000,
                        "volume_24h": 28500 if symbol == "POPCAT" else 50000,
                    },
                },
            }

            with (
                patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
                patch(
                    "api.main._try_fetch_jupiter_quote",
                    return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
                ),
                patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
                patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
                patch("api.main._try_fetch_orca_whirlpool_quote", return_value={"ok": True, "data": orca_quote}) as fetch_orca,
                patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
                patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
                patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
                patch(
                    "api.main._resolve_quote_reference_prices_usd",
                    return_value={
                        "SOL": {"usd": 84.0},
                        symbol: {"usd": usd_price},
                    },
                ),
            ):
                response = swap_quote(from_token="SOL", to_token=symbol, amount=1.0)

            self.assertEqual(fetch_orca.call_args.args[0]["pool_candidates"], [])
            self.assertTrue(fetch_orca.call_args.args[0]["discover_pools"])
            visible = [
                response["recommended_option"],
                response["direct_route_check"],
                *response["other_options"],
            ]
            orca_option = next(opt for opt in visible if opt and opt["provider"] == "orca-whirlpool")
            self.assertEqual(orca_option["quote_status"], "live")
            self.assertEqual(orca_option["execution_status"], "quote_only")
            self.assertTrue(orca_option["is_comparison_only"])
            self.assertFalse(orca_option["is_clickable"])
            self.assertEqual(orca_option["raw_quote"]["discovery"]["selected_pool"]["address"], pool_address)

    def test_swap_quote_can_include_pumpswap_for_docs_token(self):
        sol_mint = "So11111111111111111111111111111111111111112"
        docs_mint = "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump"
        jupiter_quote = {
            "inputMint": sol_mint,
            "inAmount": "1000000000",
            "outputMint": docs_mint,
            "outAmount": "40000000",
            "otherAmountThreshold": "39800000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "swapUsdValue": "84",
            "routePlan": [],
        }
        pumpswap_quote = {
            "ok": True,
            "provider": "pumpswap",
            "direction": "buy_base_with_quote",
            "pool": {
                "address": "GseMAnNDvntR5uFePZ51yZBXzNSn7GdFPkfHwfr6d77J",
                "name": "official-docs-example",
            },
            "input_mint": sol_mint,
            "output_mint": docs_mint,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "45000000",
            "base_reserve_raw": "1000000000000",
            "quote_reserve_raw": "2000000000",
            "slippage_bps": 50,
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
            patch("api.main._try_fetch_pumpswap_quote", return_value={"ok": True, "data": pumpswap_quote}) as fetch_pumpswap,
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "FIGURE": {"usd": 0.000018},
                },
            ),
        ):
            response = swap_quote(
                from_token="SOL",
                to_token="FIGURE",
                amount=1.0,
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(fetch_pumpswap.call_args.args[0]["pool_candidates"][0]["address"], "GseMAnNDvntR5uFePZ51yZBXzNSn7GdFPkfHwfr6d77J")
        self.assertEqual(response["recommended_option"]["provider"], "pumpswap")
        self.assertTrue(response["recommended_option"]["is_comparison_only"])
        self.assertFalse(response["recommended_option"]["is_clickable"])
        self.assertEqual(response["recommended_option"]["execution_status"], "quote_only")
        self.assertAlmostEqual(response["recommended_option"]["estimated_output"], 45.0)
        self.assertAlmostEqual(response["recommended_option"]["estimated_output_usd"], 0.00081)
        self.assertEqual(response["recommended_executable_option"]["provider"], "jupiter-metis")
        self.assertIn("pumpswap_quote", response["summary"]["checked_variants"])

    def test_swap_quote_sol_to_bonk_does_not_show_fake_pumpswap(self):
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
            "routePlan": [],
        }
        unsupported = {
            "ok": False,
            "error": {"status_code": 400, "detail": "unsupported pair"},
        }

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={"ok": False, "error": {"status_code": 502, "detail": "mock"}},
            ),
            patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
            patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
            patch(
                "api.main._resolve_quote_reference_prices_usd",
                return_value={
                    "SOL": {"usd": 84.0},
                    "BONK": {"usd": 0.000006},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token="BONK", amount=1.0)

        visible = [
            response["recommended_option"],
            response["direct_route_check"],
            *response["other_options"],
        ]
        self.assertNotIn("pumpswap", {opt["provider"] for opt in visible if opt})
        diagnostic_variants = {
            item["variant_id"] for item in response["debug"]["variant_errors"]
        }
        self.assertIn("pumpswap_quote", diagnostic_variants)

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
