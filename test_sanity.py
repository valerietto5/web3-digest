import unittest
import tempfile
import json
import os
import subprocess
import requests
import io
import urllib.error
from pathlib import Path
from unittest.mock import patch
from api.main import (
    METEORA_DLMM_SOL_MINT,
    METEORA_DLMM_USDC_MINT,
    METEORA_DLMM_BONK_MINT,
    TOKEN_META,
    _build_promotion_audit_summary,
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
    _fetch_jupiter_swap_transaction,
    swap_execute_prepare,
    swap_quote,
    swap_tokens,
    token_resolve,
    token_promotion_audit,
    token_holder_concentration_config,
    token_holder_concentration,
    wallet_activity,
)
from api.ui_page import build_ui_html
from providers.token_resolver import resolve_token
from providers.solana_token_metadata import fetch_solana_mint_decimals
from providers.helius_activity import fetch_wallet_activity
from providers.token_holder_concentration import (
    build_bubblemaps_url,
    fetch_token_holder_concentration,
    get_holder_concentration_rpc_config_status,
)
from tools.token_promotion_audit import (
    audit_mint as audit_promotion_mint,
    classify_pair_coverage as classify_promotion_pair_coverage,
    classify_promotion,
    dedupe_reasons as dedupe_token_promotion_reasons,
    is_rate_limited_error,
    print_text_report as print_token_promotion_text_report,
    provider_diagnostics as token_promotion_provider_diagnostics,
    standard_pairs_for_mint,
    visible_live_surfaces as token_promotion_visible_live_surfaces,
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

    def test_token_promotion_audit_builds_standard_pairs_for_mint(self):
        mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"

        pairs = standard_pairs_for_mint(mint)

        self.assertEqual(
            pairs,
            [
                ("SOL", mint, "SOL->TOKEN"),
                (mint, "SOL", "TOKEN->SOL"),
                ("USDC", mint, "USDC->TOKEN"),
                (mint, "USDC", "TOKEN->USDC"),
            ],
        )

    def test_token_promotion_pair_classification(self):
        self.assertEqual(classify_promotion_pair_coverage(4), "strong")
        self.assertEqual(classify_promotion_pair_coverage(3), "good")
        self.assertEqual(classify_promotion_pair_coverage(2), "thin")
        self.assertEqual(classify_promotion_pair_coverage(1), "weak")

    def test_token_promotion_recommends_candidate_for_strong_verified_coverage(self):
        token = {
            "symbol": "TEST",
            "display_name": "Test Token",
            "mint": "mint",
            "decimals": 6,
            "verified": True,
            "warnings": [],
            "liquidity_usd": 1000000,
        }
        pairs = [
            {"pair": "SOL->TOKEN", "classification": "strong", "success_count": 4},
            {"pair": "TOKEN->SOL", "classification": "good", "success_count": 3},
            {"pair": "USDC->TOKEN", "classification": "thin", "success_count": 2},
            {"pair": "TOKEN->USDC", "classification": "weak", "success_count": 1},
        ]

        status, recommendation, reasons = classify_promotion(token, pairs)

        self.assertEqual(status, "promote_candidate")
        self.assertIn("curated-registry", recommendation)
        self.assertEqual(reasons, [])

    def test_token_promotion_rejects_missing_decimals(self):
        token = {
            "symbol": "TEST",
            "display_name": "Test Token",
            "mint": "mint",
            "decimals": None,
        }

        status, recommendation, reasons = classify_promotion(token, [])

        self.assertEqual(status, "do_not_promote_yet")
        self.assertIn("decimals", recommendation)
        self.assertIn("missing_decimals", reasons)

    def test_token_promotion_dedupes_warning_reasons(self):
        reasons = dedupe_token_promotion_reasons([
            "external_metadata_unverified",
            "warning:external_metadata_unverified",
            "low_liquidity",
            "low_liquidity",
        ])

        self.assertEqual(reasons, ["external_metadata_unverified", "low_liquidity"])

    def test_token_promotion_manual_review_wording_is_clear(self):
        token = {
            "symbol": "TEST",
            "display_name": "Test Token",
            "mint": "mint",
            "decimals": 6,
            "verified": False,
            "warnings": ["external_metadata_unverified"],
            "liquidity_usd": 1000000,
        }
        pairs = [
            {"pair": "SOL->TOKEN", "classification": "strong", "success_count": 4},
            {"pair": "TOKEN->SOL", "classification": "good", "success_count": 3},
        ]

        status, recommendation, reasons = classify_promotion(token, pairs)

        self.assertEqual(status, "manual_review")
        self.assertEqual(recommendation, "Strong route coverage; review metadata before registry promotion.")
        self.assertEqual(reasons, ["external_metadata_unverified"])

    def test_token_promotion_detects_rate_limits(self):
        exc = Exception('Jupiter HTTP error: {"code":429,"message":"Too many requests"}')

        self.assertTrue(is_rate_limited_error(exc))

    def test_token_promotion_audit_resolves_mocked_external_mint_without_mutating_registry(self):
        mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        before_mints = {meta.get("mint") for meta in TOKEN_META.values()}
        token = {
            "source": "dexscreener",
            "symbol": "JUP",
            "display_name": "Jupiter",
            "mint": mint,
            "decimals": 6,
            "verified": True,
            "warnings": [],
            "liquidity_usd": 1000000,
            "price_usd": 0.2,
        }

        def quote_response(from_token, to_token, amount, network="solana", user_public_key=None):
            return {
                "from_token": "SOL" if from_token == "SOL" else ("USDC" if from_token == "USDC" else "JUP"),
                "to_token": "SOL" if to_token == "SOL" else ("USDC" if to_token == "USDC" else "JUP"),
                "recommended_option": {
                    "quote_status": "live",
                    "execution_surface_label": "Jupiter",
                    "estimated_output": 1.0,
                    "estimated_output_usd": 1.0,
                },
                "direct_route_check": {
                    "quote_status": "live",
                    "execution_surface_label": "Orca",
                },
                "recommended_executable_option": None,
                "other_options": [
                    {"quote_status": "live", "execution_surface_label": "Raydium"},
                    {"quote_status": "live", "execution_surface_label": "Meteora"},
                ],
                "debug": {
                    "variant_errors": [
                        {"variant_id": "phantom_quote", "status_code": 400, "detail": "unsupported pair"},
                        {"variant_id": "pumpswap_quote", "status_code": 400, "detail": "curated pool only"},
                    ]
                },
            }

        with (
            patch("tools.token_promotion_audit.resolve_token", return_value={"ok": True, "token": token}) as resolver,
            patch("tools.token_promotion_audit.swap_quote", side_effect=quote_response) as quote,
            patch("tools.token_promotion_audit.time.sleep") as sleep,
        ):
            report = audit_promotion_mint(mint, amount=1.0, request_delay=0)

        self.assertTrue(report["ok"])
        self.assertEqual(report["token"]["symbol"], "JUP")
        self.assertEqual([pair["pair"] for pair in report["pairs"]], [
            "SOL->TOKEN",
            "TOKEN->SOL",
            "USDC->TOKEN",
            "TOKEN->USDC",
        ])
        self.assertEqual(report["pairs"][0]["classification"], "strong")
        self.assertEqual(report["promotion_status"], "promote_candidate")
        resolver.assert_called_once_with(mint, allow_external=True)
        self.assertEqual(quote.call_count, 4)
        sleep.assert_not_called()
        self.assertEqual(before_mints, {meta.get("mint") for meta in TOKEN_META.values()})

    def test_token_promotion_audit_counts_phantom_and_pumpswap_visible_success(self):
        response = {
            "recommended_option": {"quote_status": "live", "execution_surface_label": "Jupiter"},
            "direct_route_check": {"quote_status": "live", "execution_surface_label": "PumpSwap"},
            "recommended_executable_option": None,
            "other_options": [
                {"quote_status": "live", "execution_surface_label": "Phantom"},
                {"quote_status": "live", "execution_surface_label": "Jupiter"},
            ],
            "debug": {"variant_errors": []},
        }

        surfaces = token_promotion_visible_live_surfaces(response)
        diagnostics = token_promotion_provider_diagnostics(response, surfaces)
        by_universe = {item["universe"]: item for item in diagnostics}

        self.assertEqual(surfaces, ["Jupiter", "PumpSwap", "Phantom"])
        self.assertEqual(by_universe["Phantom"]["status"], "success")
        self.assertEqual(by_universe["PumpSwap"]["status"], "success")

    def test_token_promotion_audit_classifies_no_pumpswap_pool(self):
        response = {
            "recommended_option": {"quote_status": "live", "execution_surface_label": "Jupiter"},
            "direct_route_check": None,
            "recommended_executable_option": None,
            "other_options": [],
            "debug": {
                "variant_errors": [
                    {
                        "variant_id": "pumpswap_quote",
                        "status_code": 502,
                        "code": "NO_PUMPSWAP_POOL",
                        "detail": "No canonical PumpSwap pool was found for this token mint.",
                    }
                ]
            },
        }

        diagnostics = token_promotion_provider_diagnostics(
            response,
            token_promotion_visible_live_surfaces(response),
        )
        pumpswap = next(item for item in diagnostics if item["universe"] == "PumpSwap")

        self.assertEqual(pumpswap["status"], "no_pumpswap_pool")
        self.assertEqual(pumpswap["fail_code"], "NO_PUMPSWAP_POOL")

    def test_token_promotion_json_and_text_output_do_not_crash(self):
        report = {
            "ok": True,
            "universes": ["Jupiter"],
            "reports": [
                {
                    "ok": True,
                    "token": {
                        "symbol": "JUP",
                        "display_name": "Jupiter",
                        "mint": "mint",
                        "decimals": 6,
                        "source": "dexscreener",
                        "liquidity_usd": 1000000,
                        "price_usd": 0.2,
                        "warnings": [],
                    },
                    "pairs": [
                        {
                            "pair": "SOL->TOKEN",
                            "success_count": 4,
                            "classification": "strong",
                            "live_surfaces": ["Jupiter", "Orca"],
                            "universes": [
                                {"universe": "Jupiter", "status": "success"},
                                {
                                    "universe": "PumpSwap",
                                    "status": "no_pumpswap_pool",
                                    "fail_code": "NO_PUMPSWAP_POOL",
                                    "fail_reason": "No canonical PumpSwap pool was found.",
                                },
                            ],
                        }
                    ],
                    "promotion_status": "promote_candidate",
                    "recommendation": "ok",
                    "promotion_reasons": [],
                }
            ],
        }

        encoded = json.dumps(report)
        self.assertIn("JUP", encoded)
        with patch("builtins.print") as printer:
            print_token_promotion_text_report(report)

        self.assertGreater(printer.call_count, 0)
        printed = "\n".join(str(call.args[0]) for call in printer.call_args_list if call.args)
        self.assertIn("Universe diagnostics", printed)
        self.assertIn("PumpSwap: no_pumpswap_pool", printed)

    def test_token_promotion_audit_summary_counts_pair_classes_and_universes(self):
        report = {
            "pairs": [
                {
                    "classification": "strong",
                    "universes": [
                        {"universe": "Jupiter", "status": "success"},
                        {"universe": "Phantom", "status": "success"},
                    ],
                },
                {
                    "classification": "good",
                    "universes": [
                        {"universe": "Jupiter", "status": "success"},
                        {"universe": "PumpSwap", "status": "success"},
                    ],
                },
                {"classification": "thin", "universes": []},
                {"classification": "weak", "universes": []},
            ]
        }

        summary = _build_promotion_audit_summary(report)

        self.assertEqual(summary["total_pairs"], 4)
        self.assertEqual(summary["strong_pairs"], 1)
        self.assertEqual(summary["good_pairs"], 1)
        self.assertEqual(summary["thin_pairs"], 1)
        self.assertEqual(summary["weak_pairs"], 1)
        self.assertEqual(summary["successful_universes"], ["Jupiter", "Phantom", "PumpSwap"])
        self.assertTrue(summary["phantom_supported"])
        self.assertTrue(summary["pumpswap_supported"])
        self.assertEqual(summary["best_pair_classification"], "strong")
        self.assertEqual(summary["coverage_label"], "Strong coverage")

    def test_token_promotion_audit_endpoint_validates_inputs(self):
        with self.assertRaises(Exception) as empty_ctx:
            token_promotion_audit(mint="", amount=1.0, request_delay=1.5)
        self.assertEqual(empty_ctx.exception.status_code, 400)

        with self.assertRaises(Exception) as amount_ctx:
            token_promotion_audit(mint="mint", amount=0, request_delay=1.5)
        self.assertEqual(amount_ctx.exception.status_code, 400)

        with self.assertRaises(Exception) as negative_delay_ctx:
            token_promotion_audit(mint="mint", amount=1.0, request_delay=-0.1)
        self.assertEqual(negative_delay_ctx.exception.status_code, 400)

        with self.assertRaises(Exception) as high_delay_ctx:
            token_promotion_audit(mint="mint", amount=1.0, request_delay=5.1)
        self.assertEqual(high_delay_ctx.exception.status_code, 400)

    def test_token_promotion_audit_endpoint_calls_audit_and_preserves_registry(self):
        before_mints = {meta.get("mint") for meta in TOKEN_META.values()}
        report = {
            "ok": True,
            "token": {"symbol": "JUP", "mint": "mint", "decimals": 6},
            "pairs": [
                {
                    "classification": "strong",
                    "universes": [
                        {"universe": "Phantom", "status": "success"},
                        {"universe": "PumpSwap", "status": "success"},
                    ],
                }
            ],
            "promotion_status": "manual_review",
            "recommendation": "Strong route coverage; review metadata before registry promotion.",
        }

        with patch("tools.token_promotion_audit.audit_mint", return_value=report) as audit:
            response = token_promotion_audit(mint="mint", amount=2.0, request_delay=1.5)

        audit.assert_called_once_with("mint", amount=2.0, request_delay=1.5)
        self.assertIn("promotion_summary", response)
        self.assertTrue(response["promotion_summary"]["phantom_supported"])
        self.assertTrue(response["promotion_summary"]["pumpswap_supported"])
        self.assertEqual(before_mints, {meta.get("mint") for meta in TOKEN_META.values()})

    def test_helius_activity_returns_not_configured_without_env(self):
        with patch.dict(os.environ, {}, clear=True):
            result = fetch_wallet_activity("wallet-address")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "HELIUS_NOT_CONFIGURED")

    def test_helius_activity_validates_address_and_limit(self):
        empty = fetch_wallet_activity("", api_key="key")
        self.assertFalse(empty["ok"])
        self.assertEqual(empty["error"]["code"], "WALLET_ADDRESS_REQUIRED")

        invalid = fetch_wallet_activity("wallet-address", limit=0, api_key="key")
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["error"]["code"], "INVALID_ACTIVITY_LIMIT")

    def test_helius_activity_normalizes_success_response(self):
        class MockResponse:
            ok = True
            status_code = 200
            text = ""

            def json(self):
                return [
                    {
                        "signature": "sig1",
                        "timestamp": 1710000000,
                        "type": "TRANSFER",
                        "description": "Received SOL",
                        "fee": 5000,
                        "nativeTransfers": [{"amount": 1000}],
                        "tokenTransfers": [{"mint": "mint"}],
                        "instructions": [{"programId": "program1"}],
                    }
                ]

        with patch("providers.helius_activity.requests.get", return_value=MockResponse()) as fetch:
            result = fetch_wallet_activity("wallet-address", limit=3, api_key="key")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "helius")
        self.assertEqual(result["address"], "wallet-address")
        self.assertEqual(len(result["items"]), 1)
        item = result["items"][0]
        self.assertEqual(item["signature"], "sig1")
        self.assertEqual(item["timestamp"], 1710000000)
        self.assertEqual(item["type"], "TRANSFER")
        self.assertEqual(item["description"], "Received SOL")
        self.assertEqual(item["fee"], 5000)
        self.assertEqual(item["native_transfers"], [{"amount": 1000}])
        self.assertEqual(item["token_transfers"], [{"mint": "mint"}])
        self.assertEqual(item["programs"], ["program1"])
        self.assertEqual(item["raw"]["signature"], "sig1")
        fetch.assert_called_once()
        self.assertIn("/v0/addresses/wallet-address/transactions", fetch.call_args.args[0])
        self.assertEqual(fetch.call_args.kwargs["params"]["limit"], 3)
        self.assertEqual(fetch.call_args.kwargs["params"]["api-key"], "key")

    def test_helius_activity_http_error_invalid_json_and_request_failure(self):
        class HttpErrorResponse:
            ok = False
            status_code = 429
            text = "rate limited"

        with patch("providers.helius_activity.requests.get", return_value=HttpErrorResponse()):
            http_error = fetch_wallet_activity("wallet-address", api_key="key")
        self.assertFalse(http_error["ok"])
        self.assertEqual(http_error["error"]["code"], "HELIUS_ACTIVITY_HTTP_ERROR")
        self.assertEqual(http_error["error"]["status_code"], 429)

        class InvalidJsonResponse:
            ok = True
            status_code = 200
            text = ""

            def json(self):
                raise ValueError("bad json")

        with patch("providers.helius_activity.requests.get", return_value=InvalidJsonResponse()):
            invalid_json = fetch_wallet_activity("wallet-address", api_key="key")
        self.assertFalse(invalid_json["ok"])
        self.assertEqual(invalid_json["error"]["code"], "HELIUS_ACTIVITY_INVALID_JSON")

        with patch(
            "providers.helius_activity.requests.get",
            side_effect=requests.Timeout("timed out"),
        ):
            failed = fetch_wallet_activity("wallet-address", api_key="key")
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["error"]["code"], "HELIUS_ACTIVITY_LOOKUP_FAILED")

    def test_wallet_activity_endpoint_validates_inputs(self):
        with self.assertRaises(Exception) as empty_ctx:
            wallet_activity(address="", limit=20)
        self.assertEqual(empty_ctx.exception.status_code, 400)

        with self.assertRaises(Exception) as limit_ctx:
            wallet_activity(address="wallet-address", limit=101)
        self.assertEqual(limit_ctx.exception.status_code, 400)

    def test_wallet_activity_endpoint_calls_provider(self):
        expected = {"ok": True, "source": "helius", "items": []}
        with patch("api.main.fetch_wallet_activity", return_value=expected) as fetch:
            result = wallet_activity(address=" wallet-address ", limit=5)

        self.assertEqual(result, expected)
        fetch.assert_called_once_with("wallet-address", limit=5)

    def test_wallet_activity_endpoint_returns_not_configured_cleanly(self):
        expected = {
            "ok": False,
            "error": {"code": "HELIUS_NOT_CONFIGURED", "message": "missing"},
        }
        with patch("api.main.fetch_wallet_activity", return_value=expected):
            result = wallet_activity(address="wallet-address", limit=20)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "HELIUS_NOT_CONFIGURED")

    def test_bubblemaps_url_uses_solana_mint(self):
        mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"

        url = build_bubblemaps_url(mint)

        self.assertEqual(
            url,
            "https://v2.bubblemaps.io/map?address=JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN&chain=solana",
        )

    def test_token_holder_concentration_rejects_empty_mint(self):
        result = fetch_token_holder_concentration("")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TOKEN_MINT_REQUIRED")

    def test_token_holder_concentration_computes_visible_account_summary(self):
        class MockResponse:
            ok = True
            status_code = 200
            text = ""

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        supply_payload = {
            "jsonrpc": "2.0",
            "result": {
                "value": {
                    "amount": "1000000",
                    "decimals": 6,
                    "uiAmountString": "1",
                }
            },
            "id": 1,
        }
        largest_payload = {
            "jsonrpc": "2.0",
            "result": {
                "value": [
                    {"address": f"account{i}", "amount": amount, "decimals": 6}
                    for i, amount in enumerate(
                        [
                            "60000",
                            "50000",
                            "40000",
                            "30000",
                            "20000",
                            "10000",
                            "9000",
                            "8000",
                            "7000",
                            "6000",
                            "5000",
                            "4000",
                        ],
                        start=1,
                    )
                ]
            },
            "id": 1,
        }

        with patch(
            "providers.token_holder_concentration.requests.post",
            side_effect=[MockResponse(supply_payload), MockResponse(largest_payload)],
        ) as post:
            result = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")

        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "solana_rpc")
        self.assertEqual(result["summary"]["top_account_pct"], 6.0)
        self.assertEqual(result["summary"]["top_3_accounts_pct"], 15.0)
        self.assertEqual(result["summary"]["top_5_accounts_pct"], 20.0)
        self.assertEqual(result["summary"]["top_10_accounts_pct"], 24.0)
        self.assertEqual(result["summary"]["sampled_account_count"], 12)
        self.assertEqual(result["summary"]["concentration_level"], "high")
        self.assertEqual(result["signals"][0]["label"], "Largest visible token account")
        self.assertEqual(result["signals"][0]["severity"], "caution")
        self.assertIn("One visible token account controls 6% of supply.", result["signals"][0]["explanation"])
        self.assertIn("token_accounts_are_not_wallet_clusters", result["warnings"])
        self.assertIn("concentration_is_not_safety_score", result["warnings"])
        self.assertEqual(result["links"]["bubblemaps"], build_bubblemaps_url("mint"))
        self.assertEqual(result["rpc"]["source"], "explicit")
        self.assertTrue(result["rpc"]["url_configured"])
        self.assertNotIn("rpc.example", json.dumps(result["rpc"]))
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs["json"]["method"], "getTokenSupply")
        self.assertEqual(post.call_args_list[1].kwargs["json"]["method"], "getTokenLargestAccounts")
        self.assertEqual(post.call_args_list[0].args[0], "https://rpc.example")

    def test_token_holder_concentration_uses_holder_specific_rpc_env(self):
        class MockResponse:
            ok = False
            status_code = 429
            text = "Too many requests"

        with (
            patch.dict(
                os.environ,
                {
                    "TOKEN_HOLDER_CONCENTRATION_RPC_URL": "https://holder.example?api-key=secret",
                    "SOLANA_RPC_URL": "https://solana.example",
                    "SOLANA_MAINNET_RPC_URL": "https://mainnet.example",
                    "HELIUS_RPC_URL": "https://helius.example",
                },
                clear=True,
            ),
            patch("providers.token_holder_concentration.requests.post", return_value=MockResponse()) as post,
        ):
            result = fetch_token_holder_concentration("mint")

        self.assertFalse(result["ok"])
        self.assertEqual(post.call_args.args[0], "https://holder.example?api-key=secret")
        self.assertEqual(result["rpc"]["source"], "TOKEN_HOLDER_CONCENTRATION_RPC_URL")
        self.assertTrue(result["rpc"]["url_configured"])
        self.assertNotIn("secret", json.dumps(result["rpc"]))
        self.assertNotIn("holder.example", json.dumps(result["rpc"]))

    def test_token_holder_concentration_prefers_explicit_rpc_over_env(self):
        class MockResponse:
            ok = False
            status_code = 429
            text = "Too many requests"

        with (
            patch.dict(os.environ, {"TOKEN_HOLDER_CONCENTRATION_RPC_URL": "https://holder.example"}, clear=True),
            patch("providers.token_holder_concentration.requests.post", return_value=MockResponse()) as post,
        ):
            result = fetch_token_holder_concentration("mint", rpc_url="https://explicit.example?api-key=secret")

        self.assertFalse(result["ok"])
        self.assertEqual(post.call_args.args[0], "https://explicit.example?api-key=secret")
        self.assertEqual(result["rpc"]["source"], "explicit")
        self.assertTrue(result["rpc"]["url_configured"])
        self.assertNotIn("explicit.example", json.dumps(result["rpc"]))
        self.assertNotIn("secret", json.dumps(result["rpc"]))

    def test_token_holder_concentration_rpc_env_fallback_order(self):
        class MockResponse:
            ok = False
            status_code = 429
            text = "Too many requests"

        cases = [
            ({"SOLANA_RPC_URL": "https://solana.example", "HELIUS_RPC_URL": "https://helius.example"}, "SOLANA_RPC_URL", "https://solana.example"),
            ({"SOLANA_MAINNET_RPC_URL": "https://mainnet.example", "HELIUS_RPC_URL": "https://helius.example"}, "SOLANA_MAINNET_RPC_URL", "https://mainnet.example"),
            ({"HELIUS_RPC_URL": "https://helius.example?api-key=secret"}, "HELIUS_RPC_URL", "https://helius.example?api-key=secret"),
        ]

        for env, source, expected_url in cases:
            with (
                self.subTest(source=source),
                patch.dict(os.environ, env, clear=True),
                patch("providers.token_holder_concentration.requests.post", return_value=MockResponse()) as post,
            ):
                result = fetch_token_holder_concentration("mint")

            self.assertFalse(result["ok"])
            self.assertEqual(post.call_args.args[0], expected_url)
            self.assertEqual(result["rpc"]["source"], source)
            self.assertTrue(result["rpc"]["url_configured"])
            self.assertNotIn("secret", json.dumps(result["rpc"]))

    def test_token_holder_concentration_public_rpc_fallback_marks_unconfigured(self):
        class MockResponse:
            ok = False
            status_code = 429
            text = "Too many requests"

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("providers.token_holder_concentration.requests.post", return_value=MockResponse()) as post,
        ):
            result = fetch_token_holder_concentration("mint")

        self.assertFalse(result["ok"])
        self.assertEqual(post.call_args.args[0], "https://api.mainnet-beta.solana.com")
        self.assertEqual(result["rpc"]["source"], "public_solana_rpc")
        self.assertFalse(result["rpc"]["url_configured"])

    def test_holder_concentration_rpc_config_status_is_redacted(self):
        with patch.dict(os.environ, {}, clear=True):
            public_status = get_holder_concentration_rpc_config_status()

        self.assertEqual(public_status["source"], "public_solana_rpc")
        self.assertFalse(public_status["url_configured"])
        self.assertTrue(public_status["using_public_fallback"])

        with patch.dict(
            os.environ,
            {"TOKEN_HOLDER_CONCENTRATION_RPC_URL": "https://holder.example?api-key=secret"},
            clear=True,
        ):
            configured_status = get_holder_concentration_rpc_config_status()

        self.assertEqual(configured_status["source"], "TOKEN_HOLDER_CONCENTRATION_RPC_URL")
        self.assertTrue(configured_status["url_configured"])
        self.assertFalse(configured_status["using_public_fallback"])
        self.assertNotIn("holder.example", json.dumps(configured_status))
        self.assertNotIn("secret", json.dumps(configured_status))

    def test_holder_concentration_config_endpoint_returns_redacted_status(self):
        with patch.dict(
            os.environ,
            {"TOKEN_HOLDER_CONCENTRATION_RPC_URL": "https://holder.example?api-key=secret"},
            clear=True,
        ):
            response = token_holder_concentration_config()

        self.assertTrue(response["ok"])
        self.assertEqual(response["rpc"]["source"], "TOKEN_HOLDER_CONCENTRATION_RPC_URL")
        self.assertTrue(response["rpc"]["url_configured"])
        self.assertFalse(response["rpc"]["using_public_fallback"])
        self.assertIn("TOKEN_HOLDER_CONCENTRATION_RPC_URL", response["note"])
        self.assertNotIn("holder.example", json.dumps(response))
        self.assertNotIn("secret", json.dumps(response))

    def test_env_example_documents_holder_rpc_without_real_key(self):
        text = (Path(__file__).resolve().parent / ".env.example").read_text()

        self.assertIn("TOKEN_HOLDER_CONCENTRATION_RPC_URL", text)
        self.assertIn("https://your-solana-rpc.example", text)
        self.assertNotIn("api-key=", text.lower())
        self.assertNotIn("secret", text.lower())

    def test_token_holder_concentration_http_error_invalid_json_and_request_failure(self):
        class HttpErrorResponse:
            ok = False
            status_code = 503
            text = "unavailable"

        with patch("providers.token_holder_concentration.requests.post", return_value=HttpErrorResponse()):
            http_error = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")
        self.assertFalse(http_error["ok"])
        self.assertEqual(http_error["error"]["code"], "TOKEN_HOLDER_CONCENTRATION_HTTP_ERROR")

        class InvalidJsonResponse:
            ok = True
            status_code = 200
            text = ""

            def json(self):
                raise ValueError("bad json")

        with patch("providers.token_holder_concentration.requests.post", return_value=InvalidJsonResponse()):
            invalid_json = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")
        self.assertFalse(invalid_json["ok"])
        self.assertEqual(invalid_json["error"]["code"], "TOKEN_HOLDER_CONCENTRATION_INVALID_JSON")

        with patch(
            "providers.token_holder_concentration.requests.post",
            side_effect=requests.Timeout("timed out"),
        ):
            failed = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["error"]["code"], "TOKEN_SUPPLY_LOOKUP_FAILED")

    def test_token_holder_concentration_rate_limit_errors_are_explicit(self):
        class RateLimitHttpResponse:
            ok = False
            status_code = 429
            text = "Too many requests"

        with patch("providers.token_holder_concentration.requests.post", return_value=RateLimitHttpResponse()):
            http_limited = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")
        self.assertFalse(http_limited["ok"])
        self.assertEqual(http_limited["error"]["code"], "TOKEN_HOLDER_CONCENTRATION_RATE_LIMITED")
        self.assertEqual(http_limited["error"]["status_code"], 429)
        self.assertEqual(http_limited["links"]["bubblemaps"], build_bubblemaps_url("mint"))
        self.assertIn("concentration_is_not_safety_score", http_limited["warnings"])

        class MockResponse:
            ok = True
            status_code = 200
            text = ""

            def json(self):
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": 429, "message": "Too many requests for a specific RPC call"},
                    "id": 1,
                }

        with patch("providers.token_holder_concentration.requests.post", return_value=MockResponse()):
            rpc_limited = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")
        self.assertFalse(rpc_limited["ok"])
        self.assertEqual(rpc_limited["error"]["code"], "TOKEN_HOLDER_CONCENTRATION_RATE_LIMITED")
        self.assertEqual(rpc_limited["error"]["status_code"], 429)
        self.assertEqual(rpc_limited["links"]["bubblemaps"], build_bubblemaps_url("mint"))

    def test_token_holder_concentration_failures_include_bubblemaps_link(self):
        class MockResponse:
            ok = True
            status_code = 200
            text = ""

            def json(self):
                return {"jsonrpc": "2.0", "result": {"value": {"amount": "0"}}, "id": 1}

        with patch("providers.token_holder_concentration.requests.post", return_value=MockResponse()):
            result = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TOKEN_SUPPLY_NOT_FOUND")
        self.assertEqual(result["links"]["bubblemaps"], build_bubblemaps_url("mint"))
        self.assertIn("token_accounts_are_not_wallet_clusters", result["warnings"])

    def test_token_holder_concentration_missing_supply_or_accounts_fail_softly(self):
        class MockResponse:
            ok = True
            status_code = 200
            text = ""

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        zero_supply = {"jsonrpc": "2.0", "result": {"value": {"amount": "0"}}, "id": 1}
        with patch(
            "providers.token_holder_concentration.requests.post",
            return_value=MockResponse(zero_supply),
        ):
            supply_missing = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")
        self.assertFalse(supply_missing["ok"])
        self.assertEqual(supply_missing["error"]["code"], "TOKEN_SUPPLY_NOT_FOUND")

        supply = {"jsonrpc": "2.0", "result": {"value": {"amount": "100"}}, "id": 1}
        no_accounts = {"jsonrpc": "2.0", "result": {"value": []}, "id": 1}
        with patch(
            "providers.token_holder_concentration.requests.post",
            side_effect=[MockResponse(supply), MockResponse(no_accounts)],
        ):
            accounts_missing = fetch_token_holder_concentration("mint", rpc_url="https://rpc.example")
        self.assertFalse(accounts_missing["ok"])
        self.assertEqual(accounts_missing["error"]["code"], "TOKEN_LARGEST_ACCOUNTS_NOT_FOUND")

    def test_token_holder_concentration_endpoint_calls_provider_and_preserves_registry(self):
        before_mints = {meta.get("mint") for meta in TOKEN_META.values()}
        expected = {"ok": True, "source": "solana_rpc", "summary": {}}

        with patch("api.main.fetch_token_holder_concentration", return_value=expected) as fetch:
            result = token_holder_concentration(mint=" mint ")

        self.assertEqual(result, expected)
        fetch.assert_called_once_with("mint")
        self.assertEqual(before_mints, {meta.get("mint") for meta in TOKEN_META.values()})

    def test_token_holder_concentration_endpoint_rejects_empty_mint(self):
        with self.assertRaises(Exception) as ctx:
            token_holder_concentration(mint="")

        self.assertEqual(ctx.exception.status_code, 400)

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

    def test_swap_quote_uses_external_resolver_price_for_usd_and_reference(self):
        ext_mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
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
            ),
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
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
                    "SOL": {"usd": 84.0, "pricing_source": "coingecko_simple_price"},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token=ext_mint, amount=1.0)

        self.assertEqual(response["to_token"], "JUP")
        self.assertAlmostEqual(response["recommended_option"]["estimated_output_usd"], 0.4)
        self.assertEqual(response["inline_baseline"]["pricing_source"], "dexscreener_solana")
        self.assertEqual(response["inline_baseline"]["output_token"], "JUP")
        self.assertAlmostEqual(response["inline_baseline"]["output_usd_price"], 0.2)
        self.assertIsNotNone(response["inline_baseline"]["ideal_output_amount"])
        self.assertEqual(
            response["inline_baseline"]["pricing_source_detail"]["to_token"]["pair_url"],
            "https://dexscreener.com/solana/pair",
        )

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

    def test_swap_ui_supports_external_token_resolve_preview(self):
        html = build_ui_html()

        self.assertIn('id="swapFromToken" list="swapTokenChoices"', html)
        self.assertIn('id="swapToToken" list="swapTokenChoices"', html)
        self.assertIn("Saved token or Solana mint.", html)
        self.assertNotIn("Choose a saved token or paste a Solana mint.", html)
        self.assertIn('class="swap-input-grid"', html)
        self.assertIn(".swap-input-grid { display: grid;", html)
        self.assertIn('id="swapTokenChoices"', html)
        self.assertIn('id="swapFromTokenPreview"', html)
        self.assertIn('id="swapToTokenPreview"', html)
        self.assertIn("function resolveSwapTokenInput(side)", html)
        self.assertIn('fetchMaybeJson("/tokens/resolve?" + qs({', html)
        self.assertIn("allow_external: true", html)
        self.assertIn("${symbol} · Saved token", html)
        self.assertNotIn("Registry · ${decimals} decimals", html)
        self.assertNotIn("Known token:", html)
        self.assertIn("${symbol} · External token · ${mint} · unverified", html)
        self.assertNotIn("External · ${decimals} decimals", html)
        self.assertNotIn("External token: ${symbol} / ${name}", html)
        self.assertIn("External", html)
        self.assertIn("unverified", html)
        self.assertIn("Could not resolve token metadata.", html)
        self.assertIn("Token metadata found, but decimals are unresolved. Quote preview is not safe yet.", html)

    def test_swap_ui_renders_external_token_quote_notice(self):
        html = build_ui_html()

        self.assertIn('id="swapExternalTokenNotice"', html)
        self.assertIn("function renderSwapExternalTokenNotice(quote)", html)
        self.assertIn("Array.isArray(quote?.external_tokens)", html)
        self.assertIn("External token metadata used: ", html)
        self.assertIn(" · unverified", html)
        self.assertIn("renderSwapExternalTokenNotice(quote);", html)

    def test_swap_ui_renders_holder_concentration_manual_card(self):
        html = build_ui_html()

        self.assertNotIn('id="btnHolderConcentration"', html)
        self.assertNotIn("Check holder concentration", html)
        self.assertIn('id="holderConcentrationCard"', html)
        self.assertIn('id="holderConcentrationBox"', html)
        self.assertIn("function selectedExternalTokenForHolderConcentration()", html)
        self.assertNotIn("function refreshHolderConcentrationButton()", html)
        self.assertIn("function renderHolderConcentration(data)", html)
        self.assertIn("function runHolderConcentration()", html)
        self.assertIn('fetchMaybeJson("/tokens/holder-concentration?" + qs({', html)
        self.assertIn("https://v2.bubblemaps.io/map?address=", html)
        self.assertIn("Holder concentration", html)
        self.assertIn("Top visible token account", html)
        self.assertIn("Top 5 visible token accounts", html)
        self.assertIn("Open Bubblemaps", html)
        self.assertIn("Based on visible token accounts from Solana RPC. Separate from route ranking.", html)
        self.assertIn("Distribution only — not a safety score.", html)
        self.assertIn('code === "TOKEN_HOLDER_CONCENTRATION_RATE_LIMITED"', html)
        self.assertIn("Solana RPC is rate-limited right now. Try again later.", html)
        self.assertIn("Holder concentration unavailable right now.", html)
        self.assertIn("const fallbackMint = selectedExternalTokenForHolderConcentration()?.mint", html)
        self.assertIn("holderConcentrationMint", html)
        self.assertIn("resetHolderConcentration();", html)

    def test_swap_ui_holder_concentration_is_manual_only(self):
        html = build_ui_html()

        self.assertIn("async function previewSwap()", html)
        self.assertIn("runHolderConcentration();", html)
        self.assertNotIn('$("btnHolderConcentration").addEventListener("click", runHolderConcentration);', html)
        self.assertEqual(html.count("/tokens/holder-concentration?"), 1)

    def test_swap_ui_holder_concentration_avoids_score_and_scam_language(self):
        html = build_ui_html()
        start = html.index("function renderHolderConcentration(data)")
        end = html.index("function renderSwapOptionCard", start)
        holder_html = html[start:end].lower()

        self.assertNotIn("scam", holder_html)
        self.assertNotIn("rug", holder_html)
        self.assertNotIn("trusted", holder_html)
        self.assertNotIn("wallet cluster", holder_html)
        self.assertNotIn("risk score", holder_html)

    def test_swap_ui_omits_token_intelligence_panel(self):
        html = build_ui_html()

        self.assertNotIn('id="btnTokenIntelligence"', html)
        self.assertNotIn("Run token intelligence", html)
        self.assertNotIn('id="tokenIntelligenceCard"', html)
        self.assertNotIn('id="tokenIntelligenceBox"', html)
        self.assertNotIn("function runTokenIntelligence()", html)
        self.assertNotIn('fetchMaybeJson("/tokens/promotion-audit?" + qs({', html)

    def test_token_promotion_audit_endpoint_remains_backend_tooling(self):
        report = {
            "ok": True,
            "token": {"symbol": "JUP", "mint": "mint", "decimals": 6},
            "pairs": [
                {
                    "classification": "strong",
                    "universes": [{"universe": "Phantom", "status": "success"}],
                }
            ],
            "promotion_status": "manual_review",
            "recommendation": "Strong route coverage; review metadata before registry promotion.",
        }

        with patch("tools.token_promotion_audit.audit_mint", return_value=report):
            response = token_promotion_audit(mint="mint", amount=1.0, request_delay=1.5)

        self.assertTrue(response["ok"])
        self.assertIn("promotion_summary", response)

    def test_swap_ui_preserves_curated_token_choice_behavior(self):
        html = build_ui_html()

        self.assertIn("async function loadSwapTokens()", html)
        self.assertIn('fetchMaybeJson("/swap/tokens")', html)
        self.assertIn("function renderSwapTokenChoices()", html)
        self.assertIn('opt.value = symbol;', html)
        self.assertIn('if (!$("swapFromToken").value) $("swapFromToken").value = "SOL";', html)
        self.assertIn('if (!$("swapToToken").value) $("swapToToken").value = "USDC";', html)
        self.assertIn("const fromToken = $(\"swapFromToken\").value;", html)
        self.assertIn("const toToken = $(\"swapToToken\").value;", html)

    def test_swap_ui_two_hop_route_display_is_user_facing(self):
        html = build_ui_html()

        self.assertIn("function tokenListSymbolForMint(mint)", html)
        self.assertIn("function routeTokenLabelFromMint(mint, opt, fallbackLabel", html)
        self.assertIn("function cleanContinuousRouteMints(opt)", html)
        self.assertIn("function formatCleanRoutePath(opt)", html)
        self.assertIn("if (steps.length < 2) return null;", html)
        self.assertIn("return null;", html)
        self.assertIn("mints[mints.length - 1] !== inputMint", html)
        self.assertIn("return `${fromLabel} -> ${middleLabel} -> ${toLabel}`;", html)
        self.assertIn('routeTokenLabelFromMint(middleMint, opt, "intermediate token")', html)
        self.assertIn("return fallbackLabel || knownLabel;", html)
        self.assertIn("Route: ${escapeHtml(cleanRoutePath)}", html)
        self.assertIn("Shape: two-hop · Steps: ${escapeHtml(String(routeSteps))}", html)
        self.assertIn("Route shape: ${escapeHtml(routeShape)} · Steps: ${escapeHtml(String(routeSteps))}", html)

    def test_swap_ui_includes_prepare_route_state_and_endpoint_call(self):
        html = build_ui_html()

        self.assertIn('id="swapExecutionStatus"', html)
        self.assertIn('let latestPreparedSwap = null;', html)
        self.assertIn('let swapExecutionState = "idle";', html)
        self.assertIn("function setSwapExecutionStatus(state, text, detail = null)", html)
        self.assertIn("async function prepareSwapRoute(routeRequest)", html)
        self.assertIn('fetchMaybeJson("/swap/execute/prepare"', html)
        self.assertIn('provider: "jupiter-metis"', html)
        self.assertIn("variant_id: variantId", html)
        self.assertIn("from_token: fromToken", html)
        self.assertIn("to_token: toToken", html)
        self.assertIn("amount,", html)
        self.assertIn("slippage_bps: 50", html)
        self.assertIn("user_public_key: activeWalletPubkey", html)
        self.assertIn('network: "solana"', html)
        self.assertIn("Swap transaction prepared. Review the summary before signing.", html)
        self.assertIn("Jupiter authorization is required for execution prepare.", html)
        self.assertIn("Jupiter is rate-limited right now. Try again later.", html)

    def test_swap_ui_prepare_route_requires_phantom_and_does_not_sign(self):
        html = build_ui_html()
        start = html.index("async function prepareSwapRoute(routeRequest)")
        end = html.index("function isPhantomUserRejection", start)
        prepare_block = html[start:end]

        self.assertIn("Connect Phantom to prepare this swap.", prepare_block)
        self.assertIn("if (!activeWalletPubkey)", prepare_block)
        self.assertIn('routeRequest.provider !== "jupiter-metis"', prepare_block)
        self.assertIn("setSwapPreparedActionVisible(true);", prepare_block)
        self.assertNotIn("signTransaction", prepare_block)
        self.assertNotIn("sendRawTransaction", prepare_block)
        self.assertNotIn("VersionedTransaction", prepare_block)
        self.assertNotIn("signAndSubmitPreparedSwap", prepare_block)

    def test_swap_ui_renders_swap_button_only_for_jupiter_executable_cards(self):
        html = build_ui_html()

        self.assertIn("function isJupiterExecutableRouteOption(opt)", html)
        self.assertIn('opt?.provider === "jupiter-metis"', html)
        self.assertIn("opt?.is_clickable === true", html)
        self.assertIn("opt?.is_comparison_only !== true", html)
        self.assertIn('opt?.execution_status === "executable_capable"', html)
        self.assertIn("!!opt?.variant_id", html)
        self.assertIn('data-swap-execute="true"', html)
        self.assertIn('data-provider="jupiter-metis"', html)
        self.assertIn('data-variant-id="${escapeHtml(opt.variant_id)}"', html)
        self.assertIn('data-card-role="${escapeHtml(cardRole || opt.kind || "route")}"', html)
        self.assertIn("Comparison-only - no swap action available yet.", html)

        start = html.index("function renderCompactAlternativeCard")
        end = html.index("function swapPrepareErrorMessage", start)
        alternative_block = html[start:end]
        self.assertNotIn('data-swap-execute="true"', alternative_block)

    def test_swap_ui_direct_route_uses_direct_variant_for_prepare(self):
        html = build_ui_html()

        self.assertIn('showDirectAction: true,', html)
        self.assertIn('cardRole: "direct"', html)
        self.assertIn('renderRouteActionButton("Swap this route", opt, opts.cardRole || "direct")', html)
        self.assertIn("variant_id: button.dataset.variantId", html)
        self.assertNotIn("Try direct route", html)

    def test_swap_ui_prepare_click_uses_event_delegation_and_preserves_preview_flow(self):
        html = build_ui_html()

        self.assertIn("function handleSwapExecuteClick(event)", html)
        self.assertIn('event.target?.closest?.(\'[data-swap-execute="true"]\')', html)
        self.assertIn('$("swapCard").addEventListener("click", handleSwapExecuteClick);', html)
        self.assertIn("latestSwapQuoteResponse = quote;", html)
        self.assertIn("runHolderConcentration();", html)

    def test_swap_ui_includes_prepared_sign_action_and_copy(self):
        html = build_ui_html()

        self.assertIn('id="swapPreparedAction"', html)
        self.assertIn('id="swapPreparedSummary"', html)
        self.assertIn('id="swapSignAcknowledgement"', html)
        self.assertIn('id="btnSignPreparedSwap"', html)
        self.assertIn('id="btnSignPreparedSwap" type="button" class="secondary" disabled', html)
        self.assertIn("Review and sign in Phantom", html)
        self.assertIn("I understand this is a real Solana mainnet swap", html)
        self.assertIn("async function signAndSubmitPreparedSwap()", html)
        self.assertIn('$("btnSignPreparedSwap").addEventListener("click", signAndSubmitPreparedSwap);', html)
        self.assertIn('$("swapSignAcknowledgement").addEventListener("change", updateSwapSignButtonState);', html)
        self.assertIn("Swap submitted", html)
        self.assertIn("Swap confirmed", html)
        self.assertIn("Swap failed.", html)
        self.assertIn("Swap was rejected in Phantom.", html)
        self.assertIn("Quote expired. Preview again.", html)

    def test_swap_ui_signing_requires_prepared_swap_phantom_and_versioned_tx(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn("if (!latestPreparedSwap || !latestPreparedSwap.transaction_base64)", sign_block)
        self.assertIn("const ack = $(\"swapSignAcknowledgement\");", sign_block)
        self.assertIn("if (!ack?.checked)", sign_block)
        self.assertIn("Confirm you understand this is a real mainnet swap before signing.", sign_block)
        self.assertIn('latestPreparedSwap.transaction_format !== "versioned"', sign_block)
        self.assertIn("if (!phantomProvider || !activeWalletPubkey)", sign_block)
        self.assertIn("if (!solanaWeb3?.VersionedTransaction?.deserialize)", sign_block)
        self.assertIn("Swap signing is not supported in this browser session.", sign_block)
        self.assertIn("Connect Phantom to continue.", sign_block)

    def test_swap_ui_signing_deserializes_signs_submits_and_confirms(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn("Uint8Array.from(atob(transactionBase64), c => c.charCodeAt(0))", sign_block)
        self.assertIn("solanaWeb3.VersionedTransaction.deserialize(bytes)", sign_block)
        self.assertIn("phantomProvider.signTransaction(tx)", sign_block)
        self.assertIn("new solanaWeb3.Connection(MAINNET_RPC_URL, \"confirmed\")", sign_block)
        self.assertIn("connection.sendRawTransaction(signedTx.serialize()", sign_block)
        self.assertIn("confirmTransactionWithTimeout(", sign_block)
        self.assertIn("MAINNET_EXPLORER_BASE", html)
        self.assertIn('const MAINNET_RPC_URL = "https://api.mainnet-beta.solana.com";', html)
        self.assertNotIn("new solanaWeb3.Connection(DEVNET_RPC_URL", sign_block)

    def test_swap_ui_prepare_success_reveals_sign_action_without_auto_signing(self):
        html = build_ui_html()
        start = html.index("async function prepareSwapRoute(routeRequest)")
        end = html.index("function isPhantomUserRejection", start)
        prepare_block = html[start:end]

        self.assertIn("setSwapPreparedActionVisible(false);", prepare_block)
        self.assertIn("latestPreparedSwap = res.data || null;", prepare_block)
        self.assertIn("renderPreparedSwapSummary(latestPreparedSwap);", prepare_block)
        self.assertIn("setSwapPreparedActionVisible(true);", prepare_block)
        self.assertNotIn("signAndSubmitPreparedSwap()", prepare_block)

    def test_swap_ui_signing_uses_mainnet_not_devnet_for_swap_submission(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn("MAINNET_RPC_URL", sign_block)
        self.assertIn("MAINNET_EXPLORER_BASE", html)
        self.assertNotIn("DEVNET_RPC_URL", sign_block)
        self.assertNotIn("DEVNET_EXPLORER_BASE", sign_block)

    def test_swap_ui_prepared_summary_renders_mainnet_guardrails(self):
        html = build_ui_html()

        self.assertIn("function renderPreparedSwapSummary(prepared)", html)
        self.assertIn("Prepared swap", html)
        self.assertIn("Route: Jupiter", html)
        self.assertIn("From:", html)
        self.assertIn("To:", html)
        self.assertIn("Estimated receive:", html)
        self.assertIn("Minimum receive:", html)
        self.assertIn("Slippage:", html)
        self.assertIn("Network: Solana mainnet", html)
        self.assertIn("This is a real mainnet transaction. Review in Phantom before signing.", html)

        start = html.index("function renderPreparedSwapSummary(prepared)")
        end = html.index("function resetSwapExecutionPrepare", start)
        summary_block = html[start:end]
        self.assertNotIn("transaction_base64", summary_block)

    def test_swap_ui_prepare_reset_clears_acknowledgement_and_disables_sign_button(self):
        html = build_ui_html()

        self.assertIn("function setSwapPreparedActionVisible(visible)", html)
        self.assertIn("if (ack) ack.checked = false;", html)
        self.assertIn("if (button) button.disabled = true;", html)
        self.assertIn("button.disabled = !(latestPreparedSwap && ack?.checked);", html)

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

    def test_build_pumpswap_quote_payload_enables_sol_pair_canonical_discovery(self):
        payload = _build_pumpswap_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint="EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["discover_canonical_pool"])
        self.assertEqual(payload["discovery_mode"], "canonical_pumpswap_pool")
        self.assertNotIn("unsupported_pair", payload)

    def test_build_pumpswap_quote_payload_enables_new_meme_sol_pair_discovery(self):
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
            self.assertTrue(payload["discover_canonical_pool"])
            self.assertNotIn("unsupported_pair", payload)

    def test_build_pumpswap_quote_payload_keeps_usdc_external_pair_unsupported(self):
        payload = _build_pumpswap_quote_payload(
            input_mint=METEORA_DLMM_USDC_MINT,
            output_mint="9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
            amount_raw=1000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["unsupported_pair"])
        self.assertIn("SOL <-> token canonical pools only", payload["unsupported_pair_detail"])

    def test_try_fetch_pumpswap_quote_handles_unsupported_pair_without_fake_card(self):
        payload = _build_pumpswap_quote_payload(
            input_mint=METEORA_DLMM_USDC_MINT,
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

    def test_build_phantom_quote_payload_supports_external_mints(self):
        external_mint = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
        payload = _build_phantom_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=external_mint,
            amount_raw=1000000000,
            slippage_bps=50,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertTrue(payload["sell_token_is_native"])
        self.assertEqual(payload["buy_token_mint"], external_mint)
        self.assertNotIn("unsupported_pair", payload)

        reverse_payload = _build_phantom_quote_payload(
            input_mint=external_mint,
            output_mint=METEORA_DLMM_SOL_MINT,
            amount_raw=1000000,
            slippage_bps=50,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertFalse(reverse_payload["sell_token_is_native"])
        self.assertEqual(reverse_payload["sell_token_mint"], external_mint)
        self.assertTrue(reverse_payload["buy_token_is_native"])
        self.assertNotIn("unsupported_pair", reverse_payload)

        usdc_payload = _build_phantom_quote_payload(
            input_mint=METEORA_DLMM_USDC_MINT,
            output_mint=external_mint,
            amount_raw=1000000,
            slippage_bps=50,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertFalse(usdc_payload["sell_token_is_native"])
        self.assertFalse(usdc_payload["buy_token_is_native"])
        self.assertEqual(usdc_payload["buy_token_mint"], external_mint)
        self.assertNotIn("unsupported_pair", usdc_payload)

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

    def _mock_jupiter_execution_quote(self, out_amount="85000000"):
        return {
            "inputMint": METEORA_DLMM_SOL_MINT,
            "inAmount": "1000000000",
            "outputMint": METEORA_DLMM_USDC_MINT,
            "outAmount": out_amount,
            "otherAmountThreshold": "84575000",
            "slippageBps": 50,
            "priceImpactPct": "0",
            "routePlan": [
                {
                    "swapInfo": {
                        "label": "Orca",
                        "inputMint": METEORA_DLMM_SOL_MINT,
                        "outputMint": METEORA_DLMM_USDC_MINT,
                        "inAmount": "1000000000",
                        "outAmount": out_amount,
                    },
                    "percent": 100,
                }
            ],
        }

    def _base_swap_execute_prepare_payload(self, **overrides):
        payload = {
            "provider": "jupiter-metis",
            "variant_id": "recommended_default",
            "from_token": "SOL",
            "to_token": "USDC",
            "amount": 1.0,
            "slippage_bps": 50,
            "user_public_key": "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            "network": "solana",
        }
        payload.update(overrides)
        return payload

    def test_swap_execute_prepare_rejects_missing_user_public_key(self):
        result = swap_execute_prepare(self._base_swap_execute_prepare_payload(user_public_key=""))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_WALLET_REQUIRED")

    def test_swap_execute_prepare_rejects_unsupported_provider(self):
        result = swap_execute_prepare(self._base_swap_execute_prepare_payload(provider="raydium-trade-api"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_UNSUPPORTED_PROVIDER")

    def test_swap_execute_prepare_rejects_non_jupiter_provider_in_v1(self):
        result = swap_execute_prepare(self._base_swap_execute_prepare_payload(provider="PumpSwap"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_UNSUPPORTED_PROVIDER")

    def test_swap_execute_prepare_accepts_jupiter_provider_alias(self):
        quote = self._mock_jupiter_execution_quote()
        with (
            patch("api.main._fetch_jupiter_quote", return_value=quote),
            patch(
                "api.main._fetch_jupiter_swap_transaction",
                return_value={
                    "ok": True,
                    "swap_transaction": "base64tx",
                    "last_valid_block_height": 123,
                    "raw": {"swapTransaction": "base64tx"},
                },
            ),
        ):
            result = swap_execute_prepare(self._base_swap_execute_prepare_payload(provider="Jupiter"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "jupiter-metis")

    def test_swap_execute_prepare_rejects_unsupported_network(self):
        result = swap_execute_prepare(self._base_swap_execute_prepare_payload(network="ethereum"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_UNSUPPORTED_NETWORK")

    def test_swap_execute_prepare_rejects_unsupported_variant_id(self):
        result = swap_execute_prepare(self._base_swap_execute_prepare_payload(variant_id="pumpswap_quote"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_UNSUPPORTED_ROUTE")

    def test_swap_execute_prepare_rebuilds_fresh_jupiter_quote_before_swap(self):
        quote = self._mock_jupiter_execution_quote()
        with (
            patch("api.main._fetch_jupiter_quote", return_value=quote) as fetch_quote,
            patch(
                "api.main._fetch_jupiter_swap_transaction",
                return_value={
                    "ok": True,
                    "swap_transaction": "base64tx",
                    "last_valid_block_height": 456,
                    "raw": {"swapTransaction": "base64tx"},
                },
            ) as fetch_swap,
        ):
            result = swap_execute_prepare(self._base_swap_execute_prepare_payload(raw_quote={"tampered": True}))

        self.assertTrue(result["ok"])
        fetch_quote.assert_called_once()
        params = fetch_quote.call_args.args[0]
        self.assertEqual(params["inputMint"], METEORA_DLMM_SOL_MINT)
        self.assertEqual(params["outputMint"], METEORA_DLMM_USDC_MINT)
        self.assertEqual(params["amount"], "1000000000")
        self.assertEqual(params["slippageBps"], "50")
        fetch_swap.assert_called_once()
        self.assertEqual(fetch_swap.call_args.kwargs["quote_response"], quote)

    def test_swap_execute_prepare_direct_route_sets_only_direct_routes(self):
        quote = self._mock_jupiter_execution_quote()
        with (
            patch("api.main._fetch_jupiter_quote", return_value=quote) as fetch_quote,
            patch(
                "api.main._fetch_jupiter_swap_transaction",
                return_value={
                    "ok": True,
                    "swap_transaction": "base64tx",
                    "last_valid_block_height": 456,
                    "raw": {"swapTransaction": "base64tx"},
                },
            ),
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(variant_id="direct_route_check")
            )

        self.assertTrue(result["ok"])
        self.assertEqual(fetch_quote.call_args.args[0]["onlyDirectRoutes"], "true")

    def test_swap_execute_prepare_broader_search_relaxes_intermediate_restriction(self):
        quote = self._mock_jupiter_execution_quote()
        with (
            patch("api.main._fetch_jupiter_quote", return_value=quote) as fetch_quote,
            patch(
                "api.main._fetch_jupiter_swap_transaction",
                return_value={
                    "ok": True,
                    "swap_transaction": "base64tx",
                    "last_valid_block_height": 456,
                    "raw": {"swapTransaction": "base64tx"},
                },
            ),
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(variant_id="broader_search")
            )

        self.assertTrue(result["ok"])
        self.assertEqual(fetch_quote.call_args.args[0]["restrictIntermediateTokens"], "false")

    def test_swap_execute_prepare_exclude_recommended_dexes_rebuilds_two_quotes(self):
        default_quote = self._mock_jupiter_execution_quote(out_amount="85000000")
        alternate_quote = self._mock_jupiter_execution_quote(out_amount="84000000")
        with (
            patch("api.main._fetch_jupiter_quote", side_effect=[default_quote, alternate_quote]) as fetch_quote,
            patch(
                "api.main._fetch_jupiter_swap_transaction",
                return_value={
                    "ok": True,
                    "swap_transaction": "base64tx",
                    "last_valid_block_height": 456,
                    "raw": {"swapTransaction": "base64tx"},
                },
            ) as fetch_swap,
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(variant_id="exclude_recommended_dexes")
            )

        self.assertTrue(result["ok"])
        self.assertEqual(fetch_quote.call_count, 2)
        self.assertEqual(fetch_quote.call_args_list[1].args[0]["excludeDexes"], "Orca")
        self.assertEqual(fetch_swap.call_args.kwargs["quote_response"], alternate_quote)

    def test_swap_execute_prepare_returns_prepared_transaction_summary(self):
        quote = self._mock_jupiter_execution_quote()
        with (
            patch("api.main._fetch_jupiter_quote", return_value=quote),
            patch(
                "api.main._fetch_jupiter_swap_transaction",
                return_value={
                    "ok": True,
                    "swap_transaction": "base64tx",
                    "last_valid_block_height": 789,
                    "raw": {"swapTransaction": "base64tx"},
                },
            ),
        ):
            result = swap_execute_prepare(self._base_swap_execute_prepare_payload())

        self.assertTrue(result["ok"])
        self.assertEqual(result["transaction_base64"], "base64tx")
        self.assertEqual(result["transaction_format"], "versioned")
        self.assertEqual(result["last_valid_block_height"], 789)
        self.assertEqual(result["quote_summary"]["from_token"], "SOL")
        self.assertEqual(result["quote_summary"]["to_token"], "USDC")
        self.assertEqual(result["quote_summary"]["estimated_output_raw"], "85000000")
        self.assertAlmostEqual(result["quote_summary"]["estimated_output"], 85.0)
        self.assertEqual(result["quote_summary"]["min_received_raw"], "84575000")
        self.assertAlmostEqual(result["quote_summary"]["min_received"], 84.575)
        self.assertEqual(result["quote_summary"]["variant_id"], "recommended_default")
        self.assertIn("quote_refreshed_before_execution", result["warnings"])

    def test_swap_execute_prepare_does_not_mutate_token_meta(self):
        before = json.dumps(TOKEN_META, sort_keys=True)
        quote = self._mock_jupiter_execution_quote()
        with (
            patch("api.main._fetch_jupiter_quote", return_value=quote),
            patch(
                "api.main._fetch_jupiter_swap_transaction",
                return_value={
                    "ok": True,
                    "swap_transaction": "base64tx",
                    "last_valid_block_height": 789,
                    "raw": {"swapTransaction": "base64tx"},
                },
            ),
        ):
            result = swap_execute_prepare(self._base_swap_execute_prepare_payload())

        self.assertTrue(result["ok"])
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

    def test_fetch_jupiter_swap_transaction_calls_swap_endpoint(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({
                    "swapTransaction": "base64tx",
                    "lastValidBlockHeight": 123,
                }).encode("utf-8")

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = _fetch_jupiter_swap_transaction(
                quote_response={"routePlan": []},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(captured["url"], "https://api.jup.ag/swap/v1/swap")
        self.assertEqual(captured["body"]["quoteResponse"], {"routePlan": []})
        self.assertEqual(
            captured["body"]["userPublicKey"],
            "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )
        self.assertTrue(captured["body"]["wrapAndUnwrapSol"])
        self.assertTrue(captured["body"]["dynamicComputeUnitLimit"])
        self.assertFalse(captured["body"]["asLegacyTransaction"])
        self.assertEqual(result["swap_transaction"], "base64tx")
        self.assertEqual(result["last_valid_block_height"], 123)

    def test_fetch_jupiter_swap_transaction_maps_auth_errors(self):
        err = urllib.error.HTTPError(
            "https://api.jup.ag/swap/v1/swap",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":"unauthorized"}'),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            result = _fetch_jupiter_swap_transaction(
                quote_response={"routePlan": []},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_JUPITER_AUTH_REQUIRED")

    def test_fetch_jupiter_swap_transaction_maps_rate_limit_errors(self):
        err = urllib.error.HTTPError(
            "https://api.jup.ag/swap/v1/swap",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error":"too many requests"}'),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            result = _fetch_jupiter_swap_transaction(
                quote_response={"routePlan": []},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_RATE_LIMITED")

    def test_fetch_jupiter_swap_transaction_rejects_missing_swap_transaction(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps({"lastValidBlockHeight": 123}).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = _fetch_jupiter_swap_transaction(
                quote_response={"routePlan": []},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_PREPARE_FAILED")

if __name__ == "__main__":
    unittest.main()
