import unittest
import tempfile
import base64
import json
import os
import subprocess
import requests
import io
import urllib.error
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from api.main import (
    METEORA_DLMM_SOL_MINT,
    METEORA_DLMM_USDC_MINT,
    METEORA_DLMM_BONK_MINT,
    TOKEN_META,
    SWAP_EXECUTION_PROVIDER_CAPABILITIES,
    _apply_external_token_reference_prices,
    _attach_cost_fields,
    _build_recommended_swap_cost_summary,
    _build_promotion_audit_summary,
    _build_meteora_dlmm_quote_payload,
    _build_orca_whirlpool_quote_payload,
    _build_phantom_quote_payload,
    _build_phoenix_quote_payload,
    _build_pumpswap_quote_payload,
    _known_pumpswap_amm_pool_addresses_from_meta,
    _fetch_meteora_dlmm_quote,
    _fetch_orca_whirlpool_quote,
    _fetch_phantom_quote,
    _fetch_phoenix_quote,
    _fetch_pumpswap_quote,
    _fetch_fresh_pumpswap_execution_quote,
    _fetch_meteora_dlmm_swap_transaction,
    _fetch_pumpswap_swap_transaction,
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
    _fetch_solana_send_transaction,
    _fetch_solana_signature_status,
    _fetch_solana_simulate_transaction,
    _decode_solana_transaction_diagnostics,
    _build_swap_setup_cost_estimate,
    _external_token_response_meta,
    _fetch_jupiter_swap_transaction,
    _fetch_orca_whirlpool_swap_transaction,
    _fetch_raydium_swap_transaction,
    _prepare_meteora_dlmm_swap_transaction,
    _derive_solana_associated_token_account,
    _raydium_prepare_token_accounts,
    build_swap_execution_readiness,
    get_swap_execution_provider,
    get_swap_execution_provider_capability,
    prepare_swap_transaction_with_provider,
    swap_inline_baseline,
    swap_execute_prepare,
    swap_execute_preflight,
    swap_execute_submit,
    swap_transaction_status,
    swap_quote,
    swap_tokens,
    token_resolve,
    token_promotion_audit,
    token_holder_concentration_config,
    token_holder_concentration,
    wallet_activity,
)
from api.ui_page import build_ui_html
from providers.token_resolver import maybe_enrich_token_logo_uri_from_dexscreener, resolve_token
from providers.solana_token_metadata import fetch_solana_mint_decimals
from providers.helius_activity import fetch_wallet_activity
from providers.token_holder_concentration import (
    build_bubblemaps_url,
    clear_holder_concentration_cache,
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
from token_registry import NATIVE_TOKENS, SOL_LOGO_URI, TOKENS, USDC_LOGO_URI, USDC_MINT
from run_balances_to_db import (
    apply_requested_zero_balances,
    normalize_solana_requested_asset,
)

from db import (
    init_db,
    insert_price_snapshot,
    get_latest_prices_with_ts,
    get_price_at_or_before,
    insert_balance_snapshot,
    get_latest_balances_with_ts,
)

_TEST_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _test_base58_decode(value: str) -> bytes:
    decoded = 0
    for char in value:
        decoded = decoded * 58 + _TEST_BASE58_ALPHABET.index(char)
    raw = decoded.to_bytes((decoded.bit_length() + 7) // 8, "big") if decoded else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return (b"\x00" * leading_zeroes) + raw


def _test_shortvec(value: int) -> bytes:
    out = bytearray()
    while True:
        elem = value & 0x7F
        value >>= 7
        if value:
            elem |= 0x80
        out.append(elem)
        if not value:
            return bytes(out)


def _test_pubkey_bytes(value: str) -> bytes:
    raw = _test_base58_decode(value)
    if len(raw) != 32:
        raise ValueError(f"test public key must decode to 32 bytes: {value}")
    return raw


def _test_compiled_instruction(
    program_index: int,
    account_indexes: list[int] | None = None,
    data: bytes = b"",
) -> bytes:
    accounts = bytes(account_indexes or [])
    return bytes([program_index]) + _test_shortvec(len(accounts)) + accounts + _test_shortvec(len(data)) + data


def _test_system_transfer_data(lamports: int) -> bytes:
    return (2).to_bytes(4, "little") + lamports.to_bytes(8, "little")


def _test_versioned_swap_transaction_base64(
    *,
    payer: str,
    include_native_sol_wrap: bool = False,
    include_close_account: bool = False,
) -> str:
    account_keys = [
        payer,
        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "11111111111111111111111111111111",
        "So11111111111111111111111111111111111111112",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    ]
    instructions = [
        _test_compiled_instruction(1, [0, 5, 0, 4, 3, 2]),
    ]
    if include_native_sol_wrap:
        instructions.extend([
            _test_compiled_instruction(3, [0, 5], _test_system_transfer_data(18_999_040)),
            _test_compiled_instruction(2, [5], bytes([17])),
        ])
    instructions.append(_test_compiled_instruction(2))
    instructions.append(_test_compiled_instruction(3))
    if include_close_account:
        instructions.append(_test_compiled_instruction(2, [5, 0, 0], bytes([9])))

    message = bytearray()
    message.append(0x80)
    message.extend(bytes([1, 0, 1]))
    message.extend(_test_shortvec(len(account_keys)))
    for account_key in account_keys:
        message.extend(_test_pubkey_bytes(account_key))
    message.extend(bytes(32))
    message.extend(_test_shortvec(len(instructions)))
    for instruction in instructions:
        message.extend(instruction)
    message.extend(_test_shortvec(0))
    raw = _test_shortvec(1) + bytes(64) + bytes(message)
    return base64.b64encode(raw).decode("ascii")

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

    def test_token_resolver_resolves_figure_by_asset_key_and_mint_variants(self):
        figure_mint = "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump"
        figure_mint_upper_variant = "7LSsEoJGhLeZzGvDofTdNg7M3JttXqqGWNLo6vWMpump"

        for query in ("FIGURE", "figure", figure_mint, figure_mint_upper_variant, "spl:" + figure_mint):
            with self.subTest(query=query):
                with patch("providers.token_resolver.fetch_dexscreener_token_metadata") as fetch_external:
                    result = resolve_token(query)

                self.assertTrue(result["ok"])
                self.assertEqual(result["token"]["source"], "registry")
                self.assertEqual(result["token"]["symbol"], "FIGURE")
                self.assertEqual(result["token"]["asset"], "figure")
                self.assertEqual(result["token"]["asset_key"], "figure")
                self.assertEqual(result["token"]["mint"], figure_mint)
                self.assertEqual(result["token"]["decimals"], 6)
                fetch_external.assert_not_called()

        with patch(
            "providers.token_resolver.fetch_dexscreener_token_metadata",
            return_value={
                "ok": True,
                "token": {
                    "source": "dexscreener",
                    "mint": figure_mint,
                    "logo_uri": None,
                },
            },
        ):
            endpoint = token_resolve(query="spl:" + figure_mint_upper_variant, allow_external=True)
        self.assertTrue(endpoint["ok"])
        self.assertTrue(endpoint["can_quote"])
        self.assertEqual(endpoint["token"]["symbol"], "FIGURE")
        self.assertEqual(endpoint["token"]["asset_key"], "figure")

    def test_inline_baseline_resolves_raw_figure_mint_without_uppercasing(self):
        figure_mint = "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump"

        with patch(
            "api.main._resolve_quote_reference_prices_usd",
            return_value={
                "FIGURE": {"usd": 0.000017, "pricing_source": "dexscreener_solana"},
                "SOL": {"usd": 77.0, "pricing_source": "jupiter_price_v3"},
            },
        ):
            result = swap_inline_baseline(
                from_token=figure_mint,
                to_token="SOL",
                amount=52497.317836,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["from_token"], "FIGURE")
        self.assertEqual(result["to_token"], "SOL")
        self.assertEqual(result["inline_baseline"]["input_token"], "FIGURE")
        self.assertEqual(result["inline_baseline"]["output_token"], "SOL")
        self.assertIsNotNone(result["inline_baseline"]["input_usd_value"])
        self.assertIsNotNone(result["inline_baseline"]["ideal_output_amount"])

    def test_token_resolver_resolves_registry_mint_missing_decimals_via_rpc_without_mutating_registry(self):
        snp500_mint = "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"
        before = json.dumps(TOKEN_META, sort_keys=True)
        with patch(
            "providers.token_resolver.fetch_solana_mint_decimals",
            return_value={
                "ok": True,
                "decimals": 6,
                "source": "solana_rpc_mint_account",
                "mint": snp500_mint,
                "owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            },
        ) as fetch_decimals:
            result = resolve_token(snp500_mint)

        self.assertTrue(result["ok"])
        self.assertEqual(result["token"]["source"], "registry")
        self.assertEqual(result["token"]["asset"], "snp500")
        self.assertEqual(result["token"]["symbol"], "SNP500")
        self.assertEqual(result["token"]["mint"], snp500_mint)
        self.assertEqual(result["token"]["decimals"], 6)
        self.assertEqual(result["token"]["decimals_source"], "solana_rpc_mint_account")
        self.assertNotIn("decimals_unresolved", result["token"]["warnings"])
        fetch_decimals.assert_called_once_with(snp500_mint)
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

    def test_registry_token_logo_enrichment_uses_dexscreener_image_without_changing_source(self):
        snp500_mint = "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"
        token = {
            "source": "registry",
            "symbol": "SNP500",
            "mint": snp500_mint,
            "logo_uri": None,
            "dexscreener": True,
            "dexscreener_chain_id": "solana",
        }
        with patch(
            "providers.token_resolver.fetch_dexscreener_token_metadata",
            return_value={
                "ok": True,
                "token": {
                    "source": "dexscreener",
                    "mint": snp500_mint,
                    "logo_uri": "https://example.invalid/snp500.png",
                },
            },
        ) as fetch_external:
            result = maybe_enrich_token_logo_uri_from_dexscreener(token)

        self.assertEqual(result["source"], "registry")
        self.assertEqual(result["symbol"], "SNP500")
        self.assertEqual(result["logo_uri"], "https://example.invalid/snp500.png")
        self.assertEqual(result["logo_source"], "dexscreener")
        fetch_external.assert_called_once_with(snp500_mint)

    def test_registry_token_logo_enrichment_keeps_null_when_dexscreener_has_no_image(self):
        snp500_mint = "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"
        token = {
            "source": "registry",
            "symbol": "SNP500",
            "mint": snp500_mint,
            "logo_uri": None,
            "dexscreener": True,
            "dexscreener_chain_id": "solana",
        }
        with patch(
            "providers.token_resolver.fetch_dexscreener_token_metadata",
            return_value={
                "ok": True,
                "token": {
                    "source": "dexscreener",
                    "mint": snp500_mint,
                    "logo_uri": None,
                },
            },
        ):
            result = maybe_enrich_token_logo_uri_from_dexscreener(token)

        self.assertEqual(result["source"], "registry")
        self.assertIsNone(result["logo_uri"])
        self.assertNotIn("logo_source", result)

    def test_registry_token_logo_enrichment_is_fail_soft_on_dexscreener_error(self):
        snp500_mint = "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"
        token = {
            "source": "registry",
            "symbol": "SNP500",
            "mint": snp500_mint,
            "logo_uri": None,
            "dexscreener": True,
            "dexscreener_chain_id": "solana",
        }
        with patch(
            "providers.token_resolver.fetch_dexscreener_token_metadata",
            return_value={
                "ok": False,
                "error": {
                    "code": "EXTERNAL_TOKEN_LOOKUP_FAILED",
                    "message": "timeout",
                },
            },
        ):
            result = maybe_enrich_token_logo_uri_from_dexscreener(token)

        self.assertEqual(result["source"], "registry")
        self.assertIsNone(result["logo_uri"])

    def test_quote_token_resolution_does_not_enrich_registry_logo_metadata(self):
        with patch("providers.token_resolver.fetch_dexscreener_token_metadata") as fetch_external:
            result = _resolve_swap_token_for_quote("FIGURE")

        self.assertEqual(result["source"], "registry")
        self.assertEqual(result["symbol"], "FIGURE")
        self.assertNotIn("logo_source", result)
        fetch_external.assert_not_called()

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

    def test_core_registry_tokens_include_curated_logo_uri(self):
        self.assertEqual(NATIVE_TOKENS["SOL"]["logo_uri"], SOL_LOGO_URI)
        self.assertEqual(TOKENS[USDC_MINT]["logo_uri"], USDC_LOGO_URI)

    def test_token_resolve_endpoint_returns_expected_shape(self):
        result = token_resolve(query="USDC", allow_external=True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["can_quote"])
        self.assertTrue(result["token"]["can_quote"])
        self.assertEqual(result["token"]["symbol"], "USDC")
        self.assertEqual(result["token"]["mint"], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.assertEqual(result["token"]["decimals"], 6)
        self.assertEqual(result["token"]["logo_uri"], USDC_LOGO_URI)

    def test_token_resolve_endpoint_returns_curated_sol_logo_uri(self):
        result = token_resolve(query="SOL", allow_external=True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["can_quote"])
        self.assertEqual(result["token"]["symbol"], "SOL")
        self.assertEqual(result["token"]["logo_uri"], SOL_LOGO_URI)

    def test_token_resolve_endpoint_preserves_logo_uri_from_resolver(self):
        mint = "11111111111111111111111111111112"
        with patch(
            "api.main.resolve_token",
            return_value={
                "ok": True,
                "token": {
                    "source": "dexscreener",
                    "symbol": "EXT",
                    "name": "External Token",
                    "display_name": "External Token",
                    "mint": mint,
                    "decimals": 6,
                    "logo_uri": "https://example.invalid/logo.png",
                },
            },
        ):
            result = token_resolve(query=mint, allow_external=True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["can_quote"])
        self.assertEqual(result["token"]["logo_uri"], "https://example.invalid/logo.png")

    def test_token_resolve_endpoint_preserves_registry_logo_uri_when_present(self):
        mint = "11111111111111111111111111111112"
        with (
            patch(
                "api.main.resolve_token",
                return_value={
                    "ok": True,
                    "token": {
                        "source": "registry",
                        "symbol": "LOGO",
                        "name": "Logo Token",
                        "display_name": "Logo Token",
                        "mint": mint,
                        "decimals": 6,
                        "logo_uri": "https://example.invalid/registry-logo.png",
                    },
                },
            ),
            patch("api.main.maybe_enrich_token_logo_uri_from_dexscreener") as enrich_logo,
        ):
            enrich_logo.side_effect = lambda token: token
            result = token_resolve(query="LOGO", allow_external=True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["can_quote"])
        self.assertEqual(result["token"]["source"], "registry")
        self.assertEqual(result["token"]["logo_uri"], "https://example.invalid/registry-logo.png")
        enrich_logo.assert_called_once()

    def test_token_resolve_endpoint_enriches_registry_logo_uri_from_dexscreener(self):
        snp500_mint = "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"
        with (
            patch(
                "providers.token_resolver.fetch_solana_mint_decimals",
                return_value={
                    "ok": True,
                    "decimals": 6,
                    "source": "solana_rpc_mint_account",
                    "mint": snp500_mint,
                },
            ),
            patch(
                "providers.token_resolver.fetch_dexscreener_token_metadata",
                return_value={
                    "ok": True,
                    "token": {
                        "source": "dexscreener",
                        "mint": snp500_mint,
                        "logo_uri": "https://example.invalid/snp500.png",
                    },
                },
            ) as fetch_external,
        ):
            result = token_resolve(query=snp500_mint, allow_external=True)

        self.assertTrue(result["ok"])
        self.assertTrue(result["can_quote"])
        self.assertEqual(result["token"]["source"], "registry")
        self.assertEqual(result["token"]["logo_uri"], "https://example.invalid/snp500.png")
        self.assertEqual(result["token"]["logo_source"], "dexscreener")
        fetch_external.assert_called_once_with(snp500_mint)

    def test_token_resolve_endpoint_marks_unresolved_decimals_not_quote_safe(self):
        snp500_mint = "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"
        with (
            patch(
                "providers.token_resolver.fetch_solana_mint_decimals",
                return_value={
                    "ok": False,
                    "error": {
                        "code": "TOKEN_DECIMALS_NOT_FOUND",
                        "message": "missing decimals",
                    },
                },
            ),
            patch(
                "providers.token_resolver.fetch_dexscreener_token_metadata",
                return_value={
                    "ok": False,
                    "error": {
                        "code": "TOKEN_METADATA_NOT_FOUND",
                        "message": "not found",
                    },
                },
            ),
        ):
            result = token_resolve(query=snp500_mint, allow_external=True)

        self.assertTrue(result["ok"])
        self.assertFalse(result["can_quote"])
        self.assertFalse(result["token"]["can_quote"])
        self.assertEqual(result["reason"], "decimals_unresolved")
        self.assertIn("decimals_unresolved", result["token"]["warnings"])

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
            result = fetch_solana_mint_decimals("11111111111111111111111111111112", rpc_url="https://example.invalid")

        self.assertTrue(result["ok"])
        self.assertEqual(result["decimals"], 8)
        self.assertEqual(result["source"], "solana_rpc_mint_account")
        self.assertEqual(result["owner"], "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
        self.assertEqual(post.call_args.kwargs["json"]["method"], "getAccountInfo")
        self.assertEqual(post.call_args.kwargs["json"]["params"][1]["encoding"], "jsonParsed")

    def test_solana_mint_decimals_rpc_helper_validates_mint_and_parses_raw_account(self):
        invalid = fetch_solana_mint_decimals("not a mint", rpc_url="https://example.invalid")
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["error"]["code"], "INVALID_SOLANA_MINT")

        raw = bytearray(82)
        raw[44] = 6

        class Response:
            ok = True
            status_code = 200

            def json(self):
                return {
                    "result": {
                        "value": {
                            "owner": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                            "data": [base64.b64encode(bytes(raw)).decode("ascii"), "base64"],
                        },
                    },
                }

        with patch("providers.solana_token_metadata.requests.post", return_value=Response()):
            result = fetch_solana_mint_decimals(
                "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump",
                rpc_url="https://example.invalid",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["decimals"], 6)
        self.assertEqual(result["source"], "solana_rpc_mint_account")

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
                    result = fetch_solana_mint_decimals("11111111111111111111111111111112", rpc_url="https://example.invalid")

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
                    result = fetch_solana_mint_decimals("11111111111111111111111111111112", rpc_url="https://example.invalid")

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

    def test_resolve_swap_token_for_quote_accepts_registry_mint_after_safe_decimal_lookup(self):
        mint = "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"
        with patch(
            "api.main.resolve_token",
            return_value={
                "ok": True,
                "token": {
                    "source": "registry",
                    "symbol": "SNP500",
                    "name": "SNP500",
                    "display_name": "SNP500",
                    "mint": mint,
                    "decimals": 6,
                    "decimals_source": "solana_rpc_mint_account",
                    "verified": False,
                    "default_enabled": False,
                    "tags": ["meme"],
                    "warnings": [],
                },
            },
        ):
            meta = _resolve_swap_token_for_quote(mint)

        self.assertTrue(meta["external"])
        self.assertEqual(meta["source"], "external_resolver")
        self.assertEqual(meta["resolver_source"], "registry")
        self.assertEqual(meta["symbol"], "SNP500")
        self.assertEqual(meta["quote_label"], "SNP500")
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
        self.assertEqual(result["summary"]["number_of_accounts_used"], 12)
        self.assertEqual(result["summary"]["supply"], "1000000")
        self.assertEqual(result["summary"]["concentration_level"], "high")
        self.assertEqual(result["diagnostics"]["rpc_url_source"], "explicit")
        self.assertEqual(result["diagnostics"]["rpc_methods_attempted"], ["getTokenSupply", "getTokenLargestAccounts"])
        self.assertFalse(result["diagnostics"]["rate_limited"])
        self.assertFalse(result["diagnostics"]["cached"])
        self.assertFalse(result["diagnostics"]["partial_data_available"])
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
        self.assertTrue(http_limited["diagnostics"]["rate_limited"])
        self.assertEqual(http_limited["diagnostics"]["rpc_methods_attempted"], ["getTokenSupply"])
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
        self.assertTrue(rpc_limited["diagnostics"]["rate_limited"])
        self.assertEqual(rpc_limited["links"]["bubblemaps"], build_bubblemaps_url("mint"))

    def test_token_holder_concentration_rate_limit_is_cached_for_endpoint_style_calls(self):
        clear_holder_concentration_cache()

        class RateLimitHttpResponse:
            ok = False
            status_code = 429
            text = "Too many requests"

        with (
            patch.dict(os.environ, {"TOKEN_HOLDER_CONCENTRATION_RPC_URL": "https://holder.example"}, clear=True),
            patch("providers.token_holder_concentration.requests.post", return_value=RateLimitHttpResponse()) as post,
        ):
            first = fetch_token_holder_concentration("mint")
            second = fetch_token_holder_concentration("mint")

        self.assertFalse(first["ok"])
        self.assertFalse(second["ok"])
        self.assertEqual(post.call_count, 1)
        self.assertFalse(first["diagnostics"]["cached"])
        self.assertTrue(second["diagnostics"]["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(second["error"]["code"], "TOKEN_HOLDER_CONCENTRATION_RATE_LIMITED")
        clear_holder_concentration_cache()

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
        self.assertTrue(accounts_missing["partial_data_available"])
        self.assertTrue(accounts_missing["diagnostics"]["partial_data_available"])
        self.assertEqual(accounts_missing["diagnostics"]["rpc_methods_attempted"], ["getTokenSupply", "getTokenLargestAccounts"])
        self.assertEqual(accounts_missing["raw"]["supply"]["amount"], "100")

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
        self.assertFalse(raydium_option["is_comparison_only"])
        self.assertTrue(raydium_option["is_clickable"])
        self.assertEqual(raydium_option["execution_status"], "executable_capable")
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
        self.assertIsNone(response["recommended_option"]["estimated_output_usd"])
        self.assertTrue(response["recommended_option"]["usd_reference_uncertain"])
        self.assertIn("USD estimate unavailable", response["recommended_option"]["usd_reference_note"])
        self.assertEqual(response["inline_baseline"]["pricing_source"], "dexscreener_solana")
        self.assertEqual(response["inline_baseline"]["output_token"], "JUP")
        self.assertAlmostEqual(response["inline_baseline"]["output_usd_price"], 0.2)
        self.assertIsNotNone(response["inline_baseline"]["ideal_output_amount"])
        self.assertEqual(
            response["inline_baseline"]["pricing_source_detail"]["to_token"]["pair_url"],
            "https://dexscreener.com/solana/pair",
        )

    def test_swap_quote_jupiter_no_routes_does_not_abort_other_providers(self):
        ext_mint = "AiXxRGmRc5oDiFXbEeRX9obPpr3Zir7rks1ef2NjddiF"
        raydium_quote = {
            "success": True,
            "data": {
                "inputMint": METEORA_DLMM_SOL_MINT,
                "inputAmount": "1000000000",
                "outputMint": ext_mint,
                "outputAmount": "4200000",
                "otherAmountThreshold": "4179000",
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
                        "symbol": "AIX",
                        "name": "AIX",
                        "display_name": "AIX",
                        "mint": ext_mint,
                        "decimals": 6,
                        "verified": False,
                        "price_usd": 0.502,
                    },
                },
            ),
            patch(
                "api.main._fetch_jupiter_quote",
                side_effect=HTTPException(
                    status_code=400,
                    detail='Jupiter HTTP error: {"error":"No routes found","errorCode":"NO_ROUTES_FOUND"}',
                ),
            ),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={
                    "ok": False,
                    "error": {
                        "status_code": 400,
                        "detail": 'Jupiter HTTP error: {"error":"No routes found","errorCode":"NO_ROUTES_FOUND"}',
                    },
                },
            ),
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
                    "AIX": {"usd": 0.502},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token=ext_mint, amount=1.0)

        self.assertTrue(response["ok"])
        self.assertEqual(response["recommended_option"]["provider"], "raydium-trade-api")
        self.assertEqual(response["recommended_executable_option"]["provider"], "raydium-trade-api")
        jupiter_errors = [
            item for item in response["debug"]["variant_errors"]
            if item.get("provider") == "jupiter-metis"
        ]
        self.assertTrue(jupiter_errors)
        self.assertEqual(jupiter_errors[0]["variant_id"], "recommended_default")
        self.assertEqual(jupiter_errors[0]["error_code"], "NO_ROUTES_FOUND")
        self.assertEqual(jupiter_errors[0]["message"], "No routes found")

    def test_swap_quote_all_provider_no_routes_returns_structured_no_route_state(self):
        ext_mint = "AiXxRGmRc5oDiFXbEeRX9obPpr3Zir7rks1ef2NjddiF"
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
                        "symbol": "AIX",
                        "name": "AIX",
                        "display_name": "AIX",
                        "mint": ext_mint,
                        "decimals": 6,
                        "verified": False,
                        "price_usd": 0.502,
                    },
                },
            ),
            patch(
                "api.main._fetch_jupiter_quote",
                side_effect=HTTPException(
                    status_code=400,
                    detail='Jupiter HTTP error: {"error":"No routes found","errorCode":"NO_ROUTES_FOUND"}',
                ),
            ),
            patch(
                "api.main._try_fetch_jupiter_quote",
                return_value={
                    "ok": False,
                    "error": {
                        "status_code": 400,
                        "detail": 'Jupiter HTTP error: {"error":"No routes found","errorCode":"NO_ROUTES_FOUND"}',
                    },
                },
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
                    "AIX": {"usd": 0.502},
                },
            ),
        ):
            response = swap_quote(from_token="SOL", to_token=ext_mint, amount=1.0)

        self.assertFalse(response["ok"])
        self.assertTrue(response["no_route"])
        self.assertEqual(response["message"], "No executable route found for this token/amount.")
        self.assertEqual(response["user_message"], "Reference price is available, but no live route was found.")
        self.assertIsNone(response["recommended_option"])
        self.assertEqual(response["other_options"], [])
        self.assertIsNotNone(response["inline_baseline"]["ideal_output_amount"])
        self.assertNotIn("Jupiter HTTP error", response["message"])
        jupiter_errors = [
            item for item in response["debug"]["variant_errors"]
            if item.get("provider") == "jupiter-metis"
        ]
        self.assertEqual(jupiter_errors[0]["error_code"], "NO_ROUTES_FOUND")

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
        self.assertEqual(by_symbol["SOL"]["logo_uri"], SOL_LOGO_URI)
        self.assertEqual(by_symbol["USDC"]["decimals"], 6)
        self.assertEqual(by_symbol["USDC"]["logo_uri"], USDC_LOGO_URI)
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
        self.assertEqual(by_symbol["FIGURE"]["asset"], "figure")
        self.assertEqual(by_symbol["FIGURE"]["asset_key"], "figure")
        self.assertEqual(by_symbol["FIGURE"]["display_name"], "Action Figure")
        self.assertFalse(by_symbol["FIGURE"]["verified"])
        self.assertNotIn("USDT", by_symbol)

    def test_swap_tokens_preserves_registry_logo_uri_when_present(self):
        with patch.dict(
            TOKEN_META,
            {
                "LOGO": {
                    "asset": "logo",
                    "symbol": "LOGO",
                    "display_name": "Logo Token",
                    "mint": "Logo111111111111111111111111111111111111",
                    "decimals": 6,
                    "logo_uri": "https://example.invalid/logo-token.png",
                    "verified": True,
                    "default_enabled": True,
                    "tags": ["test"],
                },
            },
        ):
            response = swap_tokens()

        by_symbol = {token["symbol"]: token for token in response["tokens"]}
        self.assertEqual(by_symbol["LOGO"]["logo_uri"], "https://example.invalid/logo-token.png")

    def test_external_token_response_meta_preserves_logo_uri(self):
        meta = _external_token_response_meta(
            "to",
            {
                "external": True,
                "symbol": "EXT",
                "display_name": "External Token",
                "mint": "Ext1111111111111111111111111111111111111",
                "decimals": 6,
                "logo_uri": "https://example.invalid/ext.png",
                "resolver_source": "dexscreener",
            },
        )

        self.assertEqual(meta["logo_uri"], "https://example.invalid/ext.png")

    def test_portfolio_report_includes_explicitly_requested_unpriced_balance(self):
        import portfolio as portfolio_module

        with (
            patch(
                "portfolio.get_latest_balances_with_ts",
                return_value={"figure": ("2026-06-01T10:00:00+00:00", 52497.317836)},
            ),
            patch("portfolio.get_latest_prices_with_ts", return_value={}),
            patch("portfolio.get_price_at_or_before", return_value=None),
            patch("portfolio.get_price_history", return_value=[]),
        ):
            report = portfolio_module.compute_portfolio_report(
                account="sol-test",
                assets=["figure"],
                currency="usd",
                include_unpriced=True,
            )

        self.assertIn("figure", report.positions)
        pos = report.positions["figure"]
        self.assertEqual(pos.amount, 52497.317836)
        self.assertIsNone(pos.price)
        self.assertIsNone(pos.price_ts)
        self.assertIsNone(pos.value)
        self.assertIn("figure", report.missing_prices)
        self.assertEqual(report.total_value, 0.0)

    def test_portfolio_report_still_drops_unpriced_balance_when_not_requested_for_unpriced(self):
        import portfolio as portfolio_module

        with (
            patch(
                "portfolio.get_latest_balances_with_ts",
                return_value={"figure": ("2026-06-01T10:00:00+00:00", 52497.317836)},
            ),
            patch("portfolio.get_latest_prices_with_ts", return_value={}),
        ):
            report = portfolio_module.compute_portfolio_report(
                account="sol-test",
                assets=["figure"],
                currency="usd",
            )

        self.assertNotIn("figure", report.positions)
        self.assertIn("figure", report.missing_prices)

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

    def test_external_token_reference_prices_prefer_resolver_dexscreener_metadata(self):
        prices = {"FIGURE": {"usd": 0.00002, "pricing_source": "coingecko_simple_price"}}
        out = _apply_external_token_reference_prices(
            prices,
            {
                "FIGURE": {
                    "external": True,
                    "mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
                    "price_usd": 0.000017,
                    "resolver_source": "dexscreener",
                    "pair_address": "pair-address",
                    "liquidity_usd": 100000,
                }
            },
        )

        self.assertEqual(out["FIGURE"]["usd"], 0.000017)
        self.assertEqual(out["FIGURE"]["pricing_source"], "dexscreener_solana")
        self.assertEqual(out["FIGURE"]["pricing_source_detail"]["external_token_metadata"], True)
        self.assertFalse(out["FIGURE"]["usd_valuation_reliable"])
        self.assertEqual(out["FIGURE"]["reference_quality"], "external_unverified_reference")

    def test_external_token_uncertain_reference_suppresses_route_usd_estimates(self):
        option = {
            "to_token": "GACHA",
            "estimated_output": 123456789.0,
        }
        result = _attach_cost_fields(
            option,
            reference_output_amount=123000000.0,
            reference_prices={
                "GACHA": {
                    "usd": 999.0,
                    "pricing_source": "dexscreener_solana",
                    "usd_valuation_reliable": False,
                    "pricing_source_detail": {
                        "external_token_metadata": True,
                    },
                }
            },
        )

        self.assertIsNone(result["estimated_output_usd"])
        self.assertIsNone(result["execution_cost_usd"])
        self.assertTrue(result["usd_reference_uncertain"])
        self.assertIn("USD estimate unavailable", result["usd_reference_note"])
        self.assertEqual(result["estimated_output"], 123456789.0)

    def test_attach_cost_fields_computes_positive_reference_gap_usd(self):
        option = {
            "to_token": "ANSEM",
            "estimated_output": 14.5246,
        }

        result = _attach_cost_fields(
            option,
            reference_output_amount=14.7923,
            reference_prices={"ANSEM": {"usd": 0.0872, "pricing_source": "dexscreener_solana"}},
        )

        self.assertGreater(result["estimated_trade_execution_cost"]["amount"], 0)
        self.assertAlmostEqual(result["estimated_trade_execution_cost"]["amount"], 14.7923 - 14.5246)
        self.assertAlmostEqual(result["execution_cost_usd"], (14.7923 - 14.5246) * 0.0872)
        self.assertAlmostEqual(result["estimated_output_usd"], 14.5246 * 0.0872)

    def test_attach_cost_fields_equal_or_better_route_never_negative(self):
        equal = _attach_cost_fields(
            {"to_token": "ANSEM", "estimated_output": 14.7923},
            reference_output_amount=14.7923,
            reference_prices={"ANSEM": {"usd": 0.0872}},
        )
        better = _attach_cost_fields(
            {"to_token": "ANSEM", "estimated_output": 14.7983},
            reference_output_amount=14.7923,
            reference_prices={"ANSEM": {"usd": 0.0872}},
        )

        self.assertEqual(equal["estimated_trade_execution_cost"]["amount"], 0)
        self.assertEqual(equal["execution_cost_usd"], 0)
        self.assertEqual(better["estimated_trade_execution_cost"]["amount"], 0)
        self.assertEqual(better["execution_cost_usd"], 0)
        self.assertLess(better["estimated_trade_execution_cost"]["raw_difference"], 0)

    def test_recommended_swap_cost_summary_uses_reference_gap_as_headline(self):
        option = {
            "to_token": "ANSEM",
            "estimated_trade_execution_cost": {
                "amount": 0.2677,
                "token": "ANSEM",
            },
            "estimated_network_fee": {"sol": 0.001},
            "explicit_route_fees": {"has_explicit_fees": False, "route_fee_items": []},
        }

        summary = _build_recommended_swap_cost_summary(
            option,
            reference_prices={
                "ANSEM": {"usd": 0.0872},
                "SOL": {"usd": 140.0},
            },
        )

        self.assertAlmostEqual(summary["execution_cost_usd"], 0.2677 * 0.0872)
        self.assertAlmostEqual(summary["network_cost_usd"], 0.14)
        self.assertAlmostEqual(summary["estimated_total_swap_cost_usd"], 0.2677 * 0.0872)
        self.assertEqual(summary["math_rule"], "benchmark_reference_gap_usd_only")

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

        self.assertNotIn("Quote surface only for now. No execution yet.", html)
        self.assertIn("Wallet-aware route preview", html)
        self.assertNotIn("Compare live swap routes and approve safely in Phantom.", html)
        self.assertNotIn("Cached reference", html)
        self.assertNotIn("Best executable output vs DexScreener reference", html)
        self.assertIn("Best executable quote", html)
        self.assertIn("Market reference", html)
        self.assertIn("Route difference vs reference", html)
        self.assertNotIn(". Difference from reference:", html)
        self.assertNotIn("CoinGecko reference", html)
        self.assertNotIn("Jupiter reference", html)
        self.assertIn("Reference source: Jupiter Price V3 market price", html)
        self.assertIn("Reference source: DexScreener market price", html)
        self.assertIn("Used only to compare route quality", html)
        self.assertIn("fmtUsdCost(Number(baseline.input_usd_value))", html)
        self.assertIn("fmtUsdCost(tradeCostUsd)", html)
        self.assertIn("if (abs < 0.01) return sign + \"$\" + abs.toFixed(6);", html)
        self.assertIn("if (abs < 1) return sign + \"$\" + abs.toFixed(4);", html)
        self.assertIn("estimated_output_usd", html)
        self.assertIn('const sign = n < 0 ? "-" : "";', html)
        self.assertIn('return sign + "$" + abs.toFixed(2);', html)

    def test_swap_ui_recommended_and_direct_titles_include_surface(self):
        html = build_ui_html()

        self.assertIn('return "Best quote";', html)
        self.assertIn('if (kind === "recommended") return "Recommended executable route";', html)
        self.assertIn('if (kind === "direct") return "Direct/simple route check";', html)
        self.assertIn("function shouldShowSwapOptionCardTitle(opt, opts = {})", html)
        self.assertIn('return !(kind === "recommended" || kind === "direct");', html)
        self.assertIn('${shouldShowSwapOptionCardTitle(opt, opts) ? `<div><strong>${escapeHtml(title)}</strong></div>` : ""}', html)
        self.assertIn('class="route-provider-title">Via <strong>${escapeHtml(providerTitle || routeLabel)}</strong></div>', html)
        self.assertIn("route-option-card route-option-card-recommended", html)
        self.assertIn("route-option-card route-option-card-direct", html)
        self.assertIn("route-result-shell route-result-shell-recommended", html)
        self.assertIn("route-result-shell route-result-shell-direct", html)
        self.assertIn("route-section-badge", html)
        self.assertIn('<span class="route-section-badge route-section-badge-secondary">Recommended</span>', html)
        self.assertIn(".route-provider-title strong {\n      color: inherit;", html)
        self.assertIn("button.route-action-button", html)
        self.assertIn("button.route-action-button-direct", html)
        self.assertIn(".route-action-slot {\n      position: absolute;\n      top: 12px;\n      right: 12px;\n      z-index: 3;", html)
        self.assertIn(".route-action-button {\n      position: relative;\n      z-index: 1;\n      min-width: 160px;", html)
        self.assertIn("pointer-events: auto;", html)
        self.assertIn("background: rgba(52, 245, 163, 0.1);", html)
        self.assertIn("color: var(--accent-emerald);", html)
        self.assertIn('class="route-action-button${roleClass}"', html)
        self.assertIn(".route-flow { margin-top:8px; padding-right:220px; font-size:15px;", html)
        self.assertIn(".route-flow.compact { padding-right:180px; font-size:14px;", html)
        self.assertIn(".route-flow-row { display:flex; align-items:baseline; gap:6px; }", html)
        self.assertIn(".route-flow-symbol { font-weight:600; display:inline-block; min-width:12px; }", html)
        self.assertIn(".route-flow-minus { color: var(--semantic-danger); }", html)
        self.assertIn(".route-flow-plus { color: var(--semantic-success); }", html)
        self.assertIn("function renderRouteFlowRows(opt, compact = false)", html)
        self.assertIn('<span class="route-flow-symbol route-flow-minus">−</span>', html)
        self.assertIn('<span class="route-flow-symbol route-flow-plus">+</span>', html)
        self.assertIn('${renderRouteFlowRows(opt)}', html)
        self.assertIn("${renderRouteFlowRows(opt, true)}", html)
        self.assertIn("function routeInputUsdText(opt)", html)
        self.assertIn("latestSwapQuoteResponse?.inline_baseline", html)
        self.assertIn("Best executable route</span></h4>", html)
        self.assertIn("Simple route check</span></h4>", html)
        self.assertIn("Alternatives</h4>", html)
        self.assertNotIn('title: "Best executable route"', html)
        self.assertIn("Direct route is also the current recommendation.", html)
        self.assertIn("Swap cost:", html)
        self.assertNotIn("App fee: $0.00", html)
        self.assertIn("Web3 Digest fee: $0.00", html)
        self.assertNotIn("Estimated swap cost vs market:", html)
        self.assertIn("function routeReferenceDifferenceText(opt)", html)
        self.assertIn('const direction = pct >= 0 ? "above reference" : "below reference";', html)
        self.assertIn('return pctText + " " + direction;', html)
        self.assertIn('Matches reference', html)
        self.assertNotIn('Reference unavailable', html)
        self.assertNotIn(
            "Swap cost is estimated as the value gap between the reference market price and the route’s expected output.",
            html,
        )
        self.assertIn("Swap cost estimates the gap between this quote and the market reference. It is not a Web3 Digest fee.", html)
        self.assertIn("Market gap estimate", html)
        self.assertIn("Network cost", html)
        self.assertIn("Route fee estimate", html)
        self.assertIn("function routeSwapCostUsdText(opt)", html)
        self.assertIn("function finiteNumberOrNull(value)", html)
        self.assertIn("if (value === null || value === undefined || value === \"\") return null;", html)
        self.assertIn("const estimatedTotalSwapCostUsdText = routeSwapCostUsdText(opt);", html)
        self.assertIn("const total = finiteNumberOrNull(opt?.estimated_total_swap_cost_usd);", html)
        self.assertIn("if (total !== null) return fmtUsdCost(Math.max(0, total));", html)
        self.assertIn("const executionCostUsd = finiteNumberOrNull(opt?.execution_cost_usd);", html)
        self.assertIn("const tradeCostUsd = finiteNumberOrNull(opt?.estimated_trade_execution_cost?.amount_usd);", html)
        self.assertNotIn("const total = Number(opt?.estimated_total_swap_cost_usd);", html)
        helper_start = html.index("function routeSwapCostUsdText(opt)")
        helper_end = html.index("function renderCompactAlternativeCard", helper_start)
        helper_block = html[helper_start:helper_end]
        self.assertIn('return "n/a";', helper_block)
        self.assertNotIn("Number(opt?.estimated_total_swap_cost_usd)", helper_block)
        self.assertNotIn("Number(opt?.execution_cost_usd)", helper_block)
        self.assertNotIn("Number(opt?.estimated_trade_execution_cost?.amount_usd)", helper_block)
        self.assertIn(".route-cost-summary strong", html)
        self.assertIn("display: inline-flex;", html)
        self.assertIn("width: fit-content;", html)
        self.assertIn("const showCostSummary = !!opts.showCostSummary;", html)
        self.assertIn("isRecommendedCard || showCostSummary", html)
        self.assertIn("Output vs best route", html)
        self.assertIn("function routeReceiveUsdText(opt)", html)
        self.assertIn("function routeVsBestOutputText(opt, bestOption)", html)
        self.assertIn('return "Output vs best route: " + pctText + " " + direction;', html)
        self.assertIn('const pctText = absPct < 0.01', html)
        self.assertIn('? "<0.01%"', html)
        self.assertIn(': "~" + Number(absPct).toFixed(2) + "%";', html)
        self.assertIn("opt?.usd_reference_uncertain", html)
        self.assertIn("const referenceUsdPrice = Number(opt?.estimated_trade_execution_cost?.token_usd_price);", html)
        self.assertIn('return " ≈ " + fmtUsdCost(referenceUsd) + " est.";', html)
        self.assertIn("if (estimatedOutput > 0)", html)
        self.assertIn(" · USD estimate unavailable / reference uncertain", html)
        self.assertIn("lower", html)
        self.assertIn("higher", html)
        self.assertIn("Output comparison unavailable", html)
        self.assertNotIn("Execution cost: ${escapeHtml(executionCostUsdText)}", html)
        self.assertNotIn("Execution cost: ${escapeHtml(executionCostText)}", html)
        self.assertNotIn("Route shape:", html)
        self.assertNotIn("Ready to approve in Phantom", html)
        self.assertNotIn("Best executable route found in this quote.", html)
        self.assertNotIn("Execution-ready via", html)
        self.assertNotIn("Spend:", html)
        self.assertNotIn("You receive:", html)
        self.assertNotIn("Receive:", html)
        self.assertNotIn("Shape:", html)
        self.assertNotIn("🟢", html)
        self.assertNotIn("🔴", html)
        self.assertNotIn("➡", html)
        self.assertNotIn("⬅", html)
        self.assertNotIn("Comparison-only - no swap action available yet.", html)
        self.assertIn("Benchmark", html)
        self.assertIn("Not executable here", html)
        self.assertNotIn("Alternative \" + (idx + 1)", html)
        self.assertIn('const title = opt?.provider === "phantom-routing-api" ? "Benchmark — " + routeLabel : routeLabel;', html)
        self.assertIn('<div class="route-provider-title">${escapeHtml(title)}</div>', html)
        self.assertIn('<strong>Swap cost: ${escapeHtml(swapCostText)}</strong>', html)
        self.assertIn("Show cost breakdown", html)
        self.assertIn("@keyframes routeResultFadeUp", html)
        self.assertNotIn("@keyframes routeResultInLeft", html)
        self.assertNotIn("@keyframes routeResultInRight", html)
        self.assertIn("@media (prefers-reduced-motion: reduce)", html)

    def test_swap_ui_has_option_ag_design_tokens_and_dark_shell(self):
        html = build_ui_html()

        for token in [
            "--bg-primary",
            "--bg-surface",
            "--bg-elevated",
            "--bg-card",
            "--bg-card-soft",
            "--text-primary",
            "--text-secondary",
            "--text-muted",
            "--border-default",
            "--border-strong",
            "--accent-emerald",
            "--accent-emerald-soft",
            "--accent-purple",
            "--accent-cyan",
            "--semantic-success",
            "--semantic-warning",
            "--semantic-danger",
            "--radius-sm",
            "--radius-md",
            "--radius-lg",
            "--radius-xl",
            "--shadow-card",
            "--shadow-glow",
        ]:
            self.assertIn(token, html)

        self.assertIn("background:", html)
        self.assertIn("linear-gradient(180deg, #07111f 0%, #081424 48%, #050b16 100%)", html)
        self.assertIn("#btnPreviewSwap", html)
        self.assertIn("var(--accent-emerald)", html)
        self.assertIn("button.secondary,", html)
        self.assertIn("rgba(155, 124, 255, 0.08)", html)
        self.assertIn("#swapCard", html)
        self.assertIn("var(--shadow-glow)", html)
        self.assertIn(".app-shell {", html)
        self.assertIn("width: min(100%, 980px);", html)
        self.assertIn(".swap-card-header {", html)
        self.assertIn(".swap-setup-panel {", html)
        self.assertIn(".swap-actions {", html)
        self.assertIn(".swap-summary-item {", html)
        self.assertIn(".brand-mark {", html)
        self.assertIn(".swap-field-label {", html)
        self.assertIn(".app-confidence {", html)
        self.assertIn(".token-pill-icon {", html)
        self.assertIn(".token-pill-icon-sol {", html)
        self.assertIn(".token-pill-icon-usdc {", html)
        self.assertIn(".swap-direction-button {", html)
        self.assertIn("pre {\n      background: rgba(3, 10, 20, 0.82);", html)
        self.assertIn(".token-modal {", html)
        self.assertIn("background: var(--bg-elevated);", html)

    def test_swap_ui_route_card_avoids_zero_usd_for_uncertain_nonzero_output(self):
        html = build_ui_html()

        helper_start = html.index("function routeReceiveUsdText(opt)")
        helper_end = html.index("function routeVsBestOutputText(opt, bestOption)", helper_start)
        helper_block = html[helper_start:helper_end]
        self.assertIn("const estimatedOutput = Number(opt?.estimated_output);", helper_block)
        self.assertIn("const referenceUsdPrice = Number(opt?.estimated_trade_execution_cost?.token_usd_price);", helper_block)
        self.assertIn("estimatedOutput * referenceUsdPrice", helper_block)
        self.assertIn('" est."', helper_block)
        self.assertIn("if (opt?.usd_reference_uncertain)", helper_block)
        self.assertIn("!(receiveUsd === 0 && estimatedOutput > 0)", helper_block)
        self.assertIn("if (estimatedOutput > 0)", helper_block)
        self.assertIn("USD estimate unavailable / reference uncertain", helper_block)

        alt_start = html.index("function renderCompactAlternativeCard")
        alt_end = html.index("function compactSwapPrepareErrorText", alt_start)
        alt_block = html[alt_start:alt_end]
        self.assertIn("renderRouteFlowRows(opt, true)", alt_block)
        self.assertIn("routeVsBestOutputText(opt, bestOption)", alt_block)
        self.assertIn("routeSwapCostUsdText(opt)", alt_block)
        self.assertIn("Swap cost:", alt_block)
        self.assertNotIn("Alternative \" + (idx + 1)", alt_block)
        self.assertNotIn('Quote vs best route: ${escapeHtml(executionCostText)}', alt_block)

    def test_swap_ui_contains_reusable_token_selection_modal(self):
        html = build_ui_html()

        self.assertIn("token-modal-backdrop", html)
        self.assertIn("token-modal", html)
        self.assertIn("token-modal-search", html)
        self.assertIn("token-modal-row", html)
        self.assertIn("Select token", html)
        self.assertIn("Search symbol or paste Solana mint", html)
        self.assertIn("Your balances", html)
        self.assertIn("Common tokens / Saved tokens", html)
        self.assertIn("External token found", html)
        self.assertIn("Import token", html)
        self.assertIn('let activeTokenSide = "from";', html)
        self.assertIn("function openSwapTokenModal(side)", html)
        self.assertIn("function closeSwapTokenModal()", html)
        self.assertIn("function renderSwapTokenModal()", html)
        self.assertIn('openSwapTokenModal("from")', html)
        self.assertIn('openSwapTokenModal("to")', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn("row.amount > 0.0000000001", html)
        self.assertIn("No non-zero wallet balances found.", html)

    def test_swap_ui_token_modal_preserves_external_mint_resolution_flow(self):
        html = build_ui_html()

        self.assertIn("function looksLikeSolanaMint(value)", html)
        self.assertIn("const query = tokenSearchQuery;", html)
        self.assertIn("const isMintSearch = looksLikeSolanaMint(tokenSearchQuery);", html)
        self.assertIn("const externalResultHtml = renderTokenModalExternalResult(tokenSearchQuery);", html)
        self.assertIn("${isMintSearch ? externalResultHtml + balancesHtml : balancesHtml + commonHtml}", html)
        self.assertIn('const commonHtml = isMintSearch', html)
        self.assertIn('? ""', html)
        self.assertIn('qs({ query, allow_external: true })', html)
        self.assertNotIn("tokenSearchQuery.toUpperCase()", html)
        self.assertNotIn("query.toUpperCase()", html)
        self.assertNotIn("selectedMint.toUpperCase()", html)
        self.assertIn("Unverified token metadata", html)
        self.assertIn("Unverified token metadata", html)
        self.assertIn("function importTokenModalExternalToken()", html)
        self.assertIn("useResolvedSwapToken(activeTokenSide)", html)
        self.assertIn("function applySwapTokenSelection(side, token)", html)
        self.assertIn("input.dataset.selectedMint = mint;", html)
        self.assertIn("input.dataset.selectedSymbol = symbol;", html)
        self.assertIn("const value = canonicalSwapTokenQuery(side);", html)
        self.assertIn("canonicalSwapTokenQuery(\"from\")", html)
        self.assertIn("canonicalSwapTokenQuery(\"to\")", html)

    def test_swap_ui_post_success_auto_refreshes_balances(self):
        html = build_ui_html()

        self.assertIn("function swapPostSuccessRefreshAssets(summary)", html)
        self.assertIn("function refreshBalancesAfterSwap(summary)", html)
        self.assertIn("swapAssetRefreshKeyForToken", html)
        self.assertIn('add("SOL");', html)
        self.assertIn("summary?.from_token || canonicalSwapTokenQuery(\"from\")", html)
        self.assertIn("summary?.to_token || canonicalSwapTokenQuery(\"to\")", html)
        self.assertIn("Balances refreshing…", html)
        self.assertIn("Balances updated.", html)
        self.assertIn("Swap submitted. Balance refresh failed — refresh manually.", html)
        self.assertIn("refreshBalances({ assetsOverride: assets || null, silent: true, afterSwap: true })", html)
        self.assertIn("swapBalancesStaleAfterSubmit = false;", html)
        self.assertIn('id="btnSwapRefreshBalances"', html)

        success_start = html.index("function renderSwapSubmittedSuccess(signature)")
        success_end = html.index("async function signAndSubmitPreparedSwap()", success_start)
        success_block = html[success_start:success_end]
        self.assertIn("refreshBalancesAfterSwap(summary);", success_block)

        prepare_start = html.index("async function prepareSwapRoute(routeRequest)")
        prepare_end = html.index("function bytesToBase64", prepare_start)
        prepare_block = html[prepare_start:prepare_end]
        self.assertNotIn("refreshBalancesAfterSwap", prepare_block)

        self.assertEqual(html.count("refreshBalancesAfterSwap(summary);"), 1)

    def test_swap_ui_route_display_uses_stable_buckets_and_direct_priority(self):
        html = build_ui_html()

        self.assertIn("function isDirectSimpleRouteOption(opt)", html)
        self.assertIn("function directRouteDisplayPriority(opt)", html)
        self.assertIn("function chooseDisplayDirectRoute(candidates)", html)
        self.assertIn("function uniqueRouteOptions(options)", html)
        self.assertIn("if (isExecutableRouteOption(opt)) return 0;", html)
        self.assertIn('opt?.execution_status === "executable_capable"', html)
        self.assertIn('shape === "single-pool"', html)
        self.assertIn("steps === 1", html)
        self.assertIn("const displayDirectRoute = chooseDisplayDirectRoute(displayCandidates);", html)
        self.assertIn("recommendedExecutable,", html)
        self.assertIn("directRoute,", html)
        self.assertIn("...otherOptions", html)
        self.assertIn("if (sameOption(opt, displayRec)) return false;", html)
        self.assertIn("sameOption(opt, displayDirectRoute)", html)
        self.assertIn("Quote-only direct check. No swap action is available for this provider yet.", html)
        self.assertIn('directNote = "Direct route is also the current recommendation."', html)
        self.assertNotIn("<div class='muted'>Direct route is also the current recommendation.</div>", html)
        self.assertIn('renderSwapOptionCard({...displayRec, ...displayDirectRoute, ...displayRec, kind: "direct"}', html)
        self.assertIn("renderSwapOptionCard({...displayDirectRoute, kind: \"direct\"}", html)
        self.assertIn("showCostSummary: true,", html)
        self.assertNotIn("showExecutableRecommendation", html)

    def test_swap_ui_renders_route_coverage_depth_logic(self):
        html = build_ui_html()

        self.assertIn('id="swapCoverageDepth"', html)
        self.assertIn("function collectLiveRouteCoverageLabels(quote)", html)
        self.assertIn('if (!opt || opt.quote_status !== "live") continue;', html)
        self.assertIn("const key = String(label).trim().toLowerCase();", html)
        self.assertIn("seen.has(key)", html)
        self.assertIn("Routes checked: ", html)
        self.assertIn("routes checked: ", html)
        self.assertIn(".swap-summary-header {", html)
        self.assertIn("justify-content: flex-start;", html)
        self.assertIn("flex-wrap: wrap;", html)
        self.assertIn('class="swap-summary-meta"', html)
        self.assertIn('<span class="pill warn" id="pillSwapState"', html)
        self.assertIn("renderSwapCoverageDepth(quote);", html)

    def test_swap_ui_includes_quote_freshness_timer_and_stale_prepare_block(self):
        html = build_ui_html()

        self.assertIn('id="swapQuoteFreshness"', html)
        self.assertIn('id="swapQuoteCard" style="display:none;"', html)
        self.assertIn("quote-expiry-pill", html)
        self.assertIn('id="swapExecutionStatus" style="display:none;"></div>', html)
        self.assertIn('setSwapExecutionStatus("idle", "");', html)
        self.assertIn('const card = $("swapQuoteCard");', html)
        self.assertIn('if (card) card.style.display = "block";', html)
        self.assertIn('card.style.display = "none";', html)
        self.assertNotIn("Ready to prepare a swap route.", html)
        self.assertNotIn("Backend quote preview ready.", html)
        self.assertIn("SWAP_QUOTE_TTL_SECONDS = 90", html)
        self.assertIn("Quote expires in ", html)
        self.assertIn("Quote expired — preview again before swapping.", html)
        self.assertIn("function startSwapQuoteFreshnessTimer()", html)
        self.assertIn("function clearSwapQuoteFreshness()", html)
        self.assertIn("if (isSwapQuoteExpired())", html)
        self.assertLess(html.index("latestSwapQuoteResponse = quote;"), html.index("startSwapQuoteFreshnessTimer();"))
        self.assertIn("startSwapQuoteFreshnessTimer();", html)
        self.assertIn("clearSwapQuoteFreshness();", html)

    def test_swap_ui_supports_external_token_resolve_preview(self):
        html = build_ui_html()

        self.assertIn('id="swapFromToken" list="swapTokenChoices"', html)
        self.assertIn('id="swapToToken" list="swapTokenChoices"', html)
        self.assertNotIn("Saved token or Solana mint.", html)
        self.assertNotIn("Choose a saved token or paste a Solana mint.", html)
        self.assertIn('class="swap-input-grid"', html)
        self.assertIn(".swap-input-grid { display: grid;", html)
        self.assertIn('id="swapTokenChoices"', html)
        self.assertIn('id="swapFromTokenPreview"', html)
        self.assertIn('id="swapToTokenPreview"', html)
        self.assertIn("function resolveSwapTokenInput(side)", html)
        self.assertIn('fetchMaybeJson("/tokens/resolve?" + qs({', html)
        self.assertIn("allow_external: true", html)
        self.assertIn("SWAP_RECOGNIZED_TOKENS_STORAGE_KEY", html)
        self.assertIn("web3Digest.swapRecognizedTokens.v1", html)
        self.assertIn("let swapRecognizedTokenMap = {}", html)
        self.assertIn("const swapSelectedRecognizedTokenMint = {", html)
        self.assertIn("function rememberResolvedSwapToken(token)", html)
        self.assertIn("function useResolvedSwapToken(side)", html)
        self.assertIn("function resetResolvedSwapTokenSelection(side)", html)
        self.assertIn("function resetSwapStateForTokenChange(options = {})", html)
        self.assertIn('if (options.clearAmount)', html)
        self.assertIn('amountInput.value = "";', html)
        self.assertIn('swapSelectedRecognizedTokenMint[side] = recognized.mint;', html)
        self.assertIn('swapSelectedRecognizedTokenMint[side] = "";', html)
        self.assertIn('resetSwapStateForTokenChange({ clearAmount: side === "from" });', html)
        self.assertIn("Token added ✓", html)
        self.assertIn("token-resolve-use-added", html)
        self.assertIn("disabledAttr", html)
        self.assertIn('resetResolvedSwapTokenSelection("from");', html)
        self.assertIn('resetResolvedSwapTokenSelection("to");', html)
        self.assertIn("localStorage.setItem(", html)
        self.assertIn(".token-resolve-use {", html)
        self.assertIn('"mini-btn token-resolve-use"', html)
        self.assertIn("data-token-resolve-use", html)
        self.assertIn("quote ready", html)
        self.assertIn("String(item.mint || \"\").toUpperCase() === t", html)
        self.assertNotIn("${symbol} · Saved token", html)
        self.assertNotIn("Registry · ${decimals} decimals", html)
        self.assertNotIn("Known token:", html)
        self.assertNotIn("${symbol} · External token · ${mint} · unverified", html)
        self.assertNotIn("External · ${decimals} decimals", html)
        self.assertNotIn("External token: ${symbol} / ${name}", html)
        self.assertIn("External", html)
        self.assertIn("unverified", html)
        self.assertIn("Could not resolve token metadata.", html)
        self.assertIn("Token metadata found, but decimals are unresolved. Quote preview is not safe yet.", html)

    def test_swap_ui_makes_swap_terminal_primary_and_collapses_old_tools(self):
        html = build_ui_html()

        self.assertIn("<title>Web3 Digest — Swap Terminal</title>", html)
        self.assertIn("Web3 Digest — Swap Terminal", html)
        self.assertIn('id="advancedDeveloperTools"', html)
        self.assertIn("Advanced / Developer tools", html)
        self.assertIn('id="advancedPortfolioTools"', html)
        self.assertIn("Advanced / Portfolio and debug tools", html)
        self.assertLess(html.index('id="swapCard"'), html.index('id="summaryCard"'))
        self.assertLess(html.index("Advanced / Developer tools"), html.index('id="swapCard"'))

    def test_swap_ui_includes_wallet_aware_swap_input_controls(self):
        html = build_ui_html()

        self.assertIn("You sell", html)
        self.assertIn("You buy", html)
        self.assertIn('class="app-shell"', html)
        self.assertIn('class="swap-wallet-panel"', html)
        self.assertIn('class="swap-setup-panel"', html)
        self.assertIn('class="swap-actions"', html)
        self.assertIn('class="brand-mark"', html)
        self.assertIn('class="swap-field-label"', html)
        self.assertIn("Compare Solana swap routes, understand costs, and approve safely through Phantom.", html)
        self.assertIn('id="btnSwapDirection"', html)
        self.assertIn('class="swap-direction-button"', html)
        self.assertIn('aria-label="Swap sell and buy tokens"', html)
        sell_start = html.index('id="swapSellCard"')
        sell_end = html.index('id="swapBuyCard"', sell_start)
        sell_block = html[sell_start:sell_end]
        self.assertIn('id="swapFromToken"', sell_block)
        self.assertNotIn('token-symbol-compact', sell_block)
        self.assertIn('id="swapFromTokenIcon"', sell_block)
        self.assertIn('id="swapAmount"', sell_block)
        self.assertIn('id="swapFromBalanceHint"', sell_block)
        self.assertIn('id="btnSwapAmountHalf"', sell_block)
        self.assertIn('id="btnSwapAmountMax"', sell_block)
        self.assertIn('id="swapFromTokenSelector"', sell_block)
        self.assertIn('class="token-pill-arrow swap-token-selector-arrow"', sell_block)
        buy_start = html.index('id="swapBuyCard"')
        buy_end = html.index('id="swapTokenChoices"', buy_start)
        buy_block = html[buy_start:buy_end]
        self.assertIn('id="swapToTokenSelector"', buy_block)
        self.assertIn('id="swapToToken"', buy_block)
        self.assertNotIn('token-symbol-compact', buy_block)
        self.assertIn('id="swapToTokenIcon"', buy_block)
        self.assertIn('class="token-pill-arrow swap-token-selector-arrow"', buy_block)
        self.assertIn(".swap-token-selector {", html)
        self.assertIn("display: flex;", html)
        self.assertIn("border-radius: 999px;", html)
        self.assertIn("background: rgba(3, 10, 20, 0.52);", html)
        self.assertIn("flex: 0 1 68px;", html)
        self.assertIn(".swap-token-selector.is-long-symbol input", html)
        self.assertIn("input.token-symbol-compact", html)
        self.assertIn("#swapToToken.token-symbol-compact", html)
        self.assertIn("function applyTokenSymbolFit(side, symbol)", html)
        self.assertIn("const isLongSymbol = normalized.length >= 5;", html)
        self.assertIn('input?.classList.toggle("token-symbol-compact", isLongSymbol);', html)
        self.assertIn('selector?.classList.toggle("is-long-symbol", isLongSymbol);', html)
        self.assertIn('selector.dataset.longSymbol = isLongSymbol ? "true" : "false";', html)
        self.assertIn("function renderSwapTokenPillIcons()", html)
        self.assertIn("logo_uri: token.logo_uri || token.logoURI || token.icon_uri || token.iconUrl || token.image || token.image_url || \"\"", html)
        self.assertIn("token?.logo_uri ||", html)
        self.assertIn("icon.classList.add(\"token-pill-icon-fallback\");", html)
        self.assertIn("function parseSwapReceiveAmountText(value)", html)
        self.assertIn('text === "—"', html)
        self.assertIn("/preview quote/i.test(text)", html)
        self.assertIn('text.includes("$")', html)
        self.assertIn("replace(/,/g, \"\")", html)
        self.assertIn("function currentSwapReceiveAmountText()", html)
        self.assertIn("function swapSellBuyTokens()", html)
        self.assertIn('bindUiEvent("btnSwapDirection", "click", swapSellBuyTokens);', html)
        self.assertIn('bindUiEvent("swapToTokenSelector", "click", () => openSwapTokenModal("to"));', html)
        swap_direction_start = html.index("function swapSellBuyTokens()")
        swap_direction_end = html.index("function tokenSourceLabel(token)", swap_direction_start)
        swap_direction_block = html[swap_direction_start:swap_direction_end]
        self.assertIn("const receiveAmount = currentSwapReceiveAmountText();", swap_direction_block)
        self.assertIn("amountInput.value = receiveAmount || currentAmount;", swap_direction_block)
        self.assertIn("resetSwapStateForTokenChange({ clearAmount: false });", swap_direction_block)
        self.assertIn('resolveSwapTokenInput("from");', swap_direction_block)
        self.assertIn('resolveSwapTokenInput("to");', swap_direction_block)
        self.assertNotIn("signAndSubmitPreparedSwap", swap_direction_block)
        self.assertNotIn("prepareSwapRoute", swap_direction_block)
        self.assertNotIn("connectPhantom", swap_direction_block)
        self.assertNotIn('id="btnSwapHoldings"', html)
        self.assertNotIn(">Holdings</button>", html)
        self.assertIn('id="swapWalletStrip"', html)
        self.assertIn('id="swapBalanceRefreshDebugWrap"', html)
        self.assertIn('id="swapBalanceRefreshDebug"', html)
        self.assertIn('<details class="card" id="swapBalanceRefreshDebugWrap"', html)
        self.assertIn("Balance refresh diagnostics", html)
        self.assertNotIn("LATEST BALANCE REFRESH DIAGNOSTICS JSON", html)
        self.assertNotIn('<details class="card" id="swapBalanceRefreshDebugWrap" open', html)
        self.assertIn("Connected: not connected", html)
        self.assertIn('id="swapWalletControls"', html)
        self.assertIn('id="btnSwapConnectPhantom"', html)
        self.assertIn('id="btnSwapDisconnectPhantom"', html)
        self.assertIn('id="swapWalletConnectHint"', html)
        self.assertIn("Connect Phantom to prepare and approve swaps.", html)
        self.assertIn("function renderSwapWalletControls()", html)
        self.assertIn('bindUiEvent("btnSwapConnectPhantom", "click", () => connectPhantom(false));', html)
        self.assertIn('bindUiEvent("btnSwapDisconnectPhantom", "click", disconnectPhantom);', html)
        wallet_strip_start = html.index("function renderSwapWalletStrip()")
        wallet_strip_end = html.index("function renderSwapFromBalance()", wallet_strip_start)
        wallet_strip_block = html[wallet_strip_start:wallet_strip_end]
        self.assertIn('"Connected: " + shortenMiddle(phantomPubkey, 6, 6)', wallet_strip_block)
        self.assertIn('"Connected: not connected"', wallet_strip_block)
        self.assertNotIn('"Saved profile: " + latestPortfolioAccount', wallet_strip_block)
        self.assertNotIn('"Assets: " + held.join(" / ")', wallet_strip_block)
        self.assertNotIn('"Account: " + latestPortfolioAccount', wallet_strip_block)
        wallet_controls_start = html.index("function renderSwapWalletControls()")
        wallet_controls_end = html.index("function renderSwapFromBalance()", wallet_controls_start)
        wallet_controls_block = html[wallet_controls_start:wallet_controls_end]
        self.assertIn("connect.disabled = !providerAvailable;", wallet_controls_block)
        self.assertIn("Connected: ", wallet_controls_block)
        self.assertNotIn("signTransaction", wallet_controls_block)
        self.assertNotIn("signAndSubmitPreparedSwap", wallet_controls_block)
        self.assertIn('id="swapFromBalanceHint"', html)
        self.assertIn("Available: connect wallet / refresh balances.", html)
        self.assertIn('id="btnSwapAmountHalf"', html)
        self.assertIn(">50%</button>", html)
        self.assertIn('id="btnSwapAmountMax"', html)
        self.assertIn(">MAX</button>", html)
        self.assertIn('id="swapHoldingsDropdown"', html)
        self.assertIn("function portfolioBalanceRows()", html)
        self.assertIn("function selectedFromHolding()", html)
        self.assertIn("function selectedFromHoldingDiagnostics()", html)
        self.assertIn("function swapWalletAssetLabels(limit=4)", html)
        self.assertIn("const duplicate = keys.some((key) => seen.has(key));", html)
        self.assertIn("keys.forEach((key) => seen.add(key));", html)
        self.assertIn("function setSwapAmountFromHolding(fraction)", html)
        self.assertIn("function openSwapHoldingsDropdown()", html)
        self.assertIn("function selectedFromRecognizedToken()", html)
        self.assertIn("function recognizedSwapTokenAssetKeys()", html)
        self.assertIn("function recognizedSwapTokenForAsset(asset, position=null)", html)
        self.assertIn("function swapPortfolioAssetRequestValue()", html)
        self.assertIn("const assetKey = String(", html)
        self.assertIn('("spl:" + mint)', html)
        self.assertIn("registryToken?.asset_key ||", html)
        self.assertIn("registryToken?.asset ||", html)
        self.assertIn("return String(registryToken.asset_key || registryToken.asset).trim();", html)
        self.assertIn("const recognized = recognizedSwapTokenForAsset(rawAsset, position);", html)
        self.assertIn("const registryAsset = String(registryToken?.asset_key || registryToken?.asset || \"\").trim().toLowerCase();", html)
        self.assertIn("(registryAsset && assetKey === registryAsset)", html)
        self.assertIn("(symbol && assetKey === symbol)", html)
        self.assertIn("splMint || recognizedMint", html)
        self.assertIn("const baseAssets = typedAssets.length ? typedAssets : (currentAssets.length ? currentAssets : [\"sol\", \"usdc\"]);", html)
        self.assertIn("for (const asset of recognizedSwapTokenAssetKeys())", html)
        self.assertIn('const assets = swapPortfolioAssetRequestValue();', html)
        self.assertIn('const force = "true";', html)
        self.assertIn('bindUiEvent("swapFromTokenSelector", "click", () => openSwapTokenModal("from"));', html)
        self.assertIn('bindUiEvent("swapToToken", "click", () => openSwapTokenModal("to"));', html)
        self.assertIn("token_input_value", html)
        self.assertIn("rawAsset.toLowerCase().startsWith(\"spl:\")", html)
        self.assertIn('data-swap-holding-input="${escapeHtml(row.token_input_value)}"', html)
        self.assertIn('$("swapHoldingsDropdown").style.display = "none";', html)
        self.assertIn("const selectedRecognized = selectedFromRecognizedToken();", html)
        self.assertIn("selectedRecognizedHtml", html)
        self.assertIn("Selected token: ${escapeHtml(selectedRecognized.symbol || selectedRecognized.display_name || \"External token\")}", html)
        self.assertIn("Selected token: ${escapeHtml(selectedRecognized.symbol || selectedRecognized.display_name || selectedHolding.label || \"External token\")} · 0", html)
        self.assertIn("You do not currently hold \" + label + \".", html)
        self.assertIn("if (half) half.disabled = !fresh || zeroBalance;", html)
        self.assertIn("if (max) max.disabled = !fresh || zeroBalance;", html)
        self.assertIn("matched_holding_is_zero", html)
        self.assertIn("matched_holding_is_fresh", html)
        self.assertIn("Type or paste a token mint above.", html)
        self.assertIn("No wallet balances loaded yet.", html)
        self.assertIn("MAX keeps SOL reserved for network fees/account setup.", html)
        self.assertIn("const SWAP_SOL_FEE_ACCOUNT_SETUP_BUFFER_SOL = 0.001;", html)
        self.assertIn("const SWAP_DEFAULT_NETWORK_FEE_SOL = 0.0001;", html)
        self.assertNotIn("SWAP_ORCA_SOL_INPUT_SETUP_RESERVE_SOL", html)
        self.assertIn("function formatSwapSnapshotAge(value)", html)
        self.assertIn("const SWAP_BALANCE_FRESH_MS = 10 * 60 * 1000;", html)
        self.assertIn("function isSwapBalanceSnapshotFresh(value)", html)
        self.assertIn("Available snapshot: ", html)
        self.assertIn("Refresh balances to use 50% or MAX.", html)
        self.assertIn("No fresh balance found for this token.", html)
        self.assertIn("Balances may have changed after the last swap — refresh balances to use 50% or MAX.", html)
        self.assertIn("Balances may have changed after the last swap — refresh balances.", html)
        self.assertIn("Balances are from snapshots. Refresh before swapping.", html)
        self.assertNotIn("Balances may be stale after this swap — refresh balances.", html)
        self.assertIn('id="btnSwapRefreshBalances"', html)
        self.assertIn('bindUiEvent("btnSwapRefreshBalances", "click", refreshBalances);', html)
        self.assertIn("const assets = swapPortfolioAssetRequestValue();", html)
        self.assertIn('fetchMaybeJson("/refresh/balances?" + qs({ account, force, assets })', html)
        self.assertIn("requested_assets_sent_by_ui: assets", html)
        self.assertIn("portfolio_assets_returned: Object.keys(latestPortfolioReport?.positions || {})", html)
        self.assertIn("selected_from_holding: selectedFromHoldingDiagnostics()", html)
        self.assertIn("swap balance refresh diagnostics", html)
        self.assertIn("const loaded = await loadReportAndHistory();", html)
        self.assertIn("if (loaded) {", html)
        self.assertIn("swapBalancesStaleAfterSubmit = false;", html)
        self.assertIn("renderSwapBalanceFreshnessHint(selectedFromHolding());", html)
        self.assertIn("position?.balance_ts", html)
        self.assertIn('" · " + age', html)

    def test_swap_ui_token_switch_resets_amount_and_quote_state(self):
        html = build_ui_html()

        reset_start = html.index("function resetSwapStateForTokenChange(options = {})")
        reset_end = html.index("function clearSwapUi()", reset_start)
        reset_block = html[reset_start:reset_end]

        self.assertIn('if (options.clearAmount)', reset_block)
        self.assertIn('amountInput.value = "";', reset_block)
        self.assertIn("resetSwapQuoteDisplay();", reset_block)
        self.assertIn("resetSwapInlineBaseline();", reset_block)

        events_start = html.index('bindUiEvent("swapHoldingsDropdown", "click"')
        events_end = html.index("// init", events_start)
        events_block = html[events_start:events_end]

        self.assertIn('resetSwapStateForTokenChange({ clearAmount: true });', events_block)
        self.assertIn('bindUiEvent("swapFromToken", "input"', events_block)
        self.assertIn('bindUiEvent("swapFromToken", "change"', events_block)
        self.assertIn('bindUiEvent("swapToToken", "input"', events_block)
        self.assertIn('bindUiEvent("swapToToken", "change"', events_block)
        self.assertIn('resetSwapStateForTokenChange({ clearAmount: false });', events_block)

        use_start = html.index("function useResolvedSwapToken(side)")
        use_end = html.index("function resetResolvedSwapTokenSelection(side)", use_start)
        use_block = html[use_start:use_end]
        self.assertIn('resetSwapStateForTokenChange({ clearAmount: side === "from" });', use_block)
        self.assertIn('recognized.symbol || recognized.display_name || recognized.mint', use_block)
        self.assertIn("renderSwapFromBalance();", use_block)
        self.assertIn("renderSwapHoldingsDropdown();", use_block)

    def test_swap_ui_recognized_selected_token_stays_visible_without_holding_row(self):
        html = build_ui_html()
        start = html.index("function renderSwapHoldingsDropdown()")
        end = html.index("function setSwapAmountFromHolding", start)
        dropdown_block = html[start:end]

        self.assertIn("const selectedRecognized = selectedFromRecognizedToken();", dropdown_block)
        self.assertIn("const selectedHolding = selectedFromHolding();", dropdown_block)
        self.assertIn("const hasSelectedRecognizedRow = selectedRecognizedKey && portfolioBalanceRows().some", dropdown_block)
        self.assertIn("selectedHolding && selectedHolding.amount === 0", dropdown_block)
        self.assertIn("Selected token: ${escapeHtml(selectedRecognized.symbol || selectedRecognized.display_name || selectedHolding.label || \"External token\")} · 0", dropdown_block)
        self.assertIn("Selected token: ${escapeHtml(selectedRecognized.symbol || selectedRecognized.display_name || \"External token\")}", dropdown_block)
        self.assertIn("balance not loaded / refresh balances", dropdown_block)

    def test_swap_ui_selected_recognized_zero_balance_is_not_missing(self):
        html = build_ui_html()
        balance_start = html.index("function portfolioBalanceRows()")
        selected_start = html.index("function selectedFromHolding()", balance_start)
        diagnostics_start = html.index("function selectedFromHoldingDiagnostics()", selected_start)
        render_start = html.index("function renderSwapFromBalance()", diagnostics_start)
        dropdown_start = html.index("function renderSwapHoldingsDropdown()", render_start)
        balance_block = html[balance_start:dropdown_start]

        self.assertIn(".filter((row) => Number.isFinite(row.amount))", balance_block)
        self.assertIn("return portfolioBalanceRows().filter((row) => row.amount > 0);", balance_block)
        selected_block = html[selected_start:diagnostics_start]
        self.assertIn("const matches = portfolioBalanceRows().filter((row) => {", selected_block)
        render_block = html[render_start:dropdown_start]
        self.assertIn("const zeroBalance = holding.amount === 0;", render_block)
        self.assertIn("You do not currently hold \" + label + \".", render_block)
        self.assertIn("if (half) half.disabled = !fresh || zeroBalance;", render_block)
        self.assertIn("if (max) max.disabled = !fresh || zeroBalance;", render_block)
        diagnostics_block = html[diagnostics_start:render_start]
        self.assertIn("balance_rows: portfolioBalanceRows().map((row) => ({", diagnostics_block)
        self.assertIn("matched_holding_is_zero", diagnostics_block)
        self.assertIn("matched_holding_is_fresh", diagnostics_block)

    def test_swap_ui_amount_shortcuts_do_not_execute_swaps(self):
        html = build_ui_html()
        start = html.index("function setSwapAmountFromHolding(fraction)")
        end = html.index("async function updateLiveSwapBaseline", start)
        amount_block = html[start:end]

        self.assertIn("holding.amount * fraction", amount_block)
        self.assertNotIn("holding.amount - 0.005", amount_block)
        self.assertIn("defaultSwapSolReserveForMax()", amount_block)
        self.assertIn("holding.amount - defaultSwapSolReserveForMax()", amount_block)
        self.assertIn("if (swapBalancesStaleAfterSubmit)", amount_block)
        self.assertIn("Balances may have changed after the last swap — refresh balances to use 50% or MAX.", amount_block)
        self.assertIn("if (!isSwapBalanceSnapshotFresh(holding.balance_ts))", amount_block)
        self.assertIn("Refresh balances to use 50% or MAX.", amount_block)
        self.assertIn("updateLiveSwapBaseline();", amount_block)
        self.assertNotIn("prepareSwapRoute", amount_block)
        self.assertNotIn("signAndSubmitPreparedSwap", amount_block)
        self.assertNotIn("/swap/execute/submit", amount_block)

    def test_display_asset_maps_registry_asset_keys_to_symbols(self):
        from api.main import display_asset

        self.assertEqual(display_asset("snp500"), "SNP500")
        self.assertEqual(display_asset("spl:3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"), "SNP500")

    def test_solana_balance_refresh_zero_fills_requested_missing_spl_assets(self):
        balances = apply_requested_zero_balances(
            {"sol": 0.049104},
            ["sol", "usdc", "spl:3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"],
        )

        self.assertEqual(balances["sol"], 0.049104)
        self.assertEqual(balances["usdc"], 0.0)
        self.assertEqual(balances["snp500"], 0.0)
        self.assertNotIn("spl:3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump", balances)
        self.assertEqual(
            normalize_solana_requested_asset("spl:3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump"),
            "snp500",
        )

    def test_solana_balance_refresh_normalizes_figure_mint_to_registry_asset(self):
        figure_mint = "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump"

        self.assertEqual(normalize_solana_requested_asset("figure"), "figure")
        self.assertEqual(normalize_solana_requested_asset(figure_mint), "figure")
        self.assertEqual(normalize_solana_requested_asset("spl:" + figure_mint), "figure")

        balances = apply_requested_zero_balances(
            {"figure": 3500.0},
            ["sol", "spl:" + figure_mint],
        )

        self.assertEqual(balances["figure"], 3500.0)
        self.assertNotIn("spl:" + figure_mint, balances)

    def test_refresh_balances_passes_requested_assets_to_solana_refresh_script(self):
        from api.main import refresh_balances

        captured = {}

        def fake_run_cmd(cmd, timeout=60):
            captured["cmd"] = cmd
            return {"returncode": 0, "stdout": "ok", "stderr": ""}

        with (
            patch(
                "api.main.load_accounts",
                return_value={
                    "accounts": {
                        "sol-test": {
                            "chain": "solana",
                            "address": "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                            "default_assets": ["sol", "usdc"],
                        }
                    }
                },
            ),
            patch("api.main._run_cmd", side_effect=fake_run_cmd),
            patch("api.main._write_portfolio_snapshot"),
            patch("api.main.db.get_latest_balances", return_value={"sol": 0.049104, "usdc": 0.0, "snp500": 38089.22}),
        ):
            result = refresh_balances(
                account="sol-test",
                assets="sol,usdc,snp500",
                force=True,
            )

        self.assertEqual(result["refreshed"][0]["account"], "sol-test")
        self.assertIn("--assets", captured["cmd"])
        assets_index = captured["cmd"].index("--assets")
        self.assertEqual(captured["cmd"][assets_index + 1: assets_index + 4], ["sol", "usdc", "snp500"])
        self.assertEqual(result["refreshed"][0]["requested_assets"], ["sol", "usdc", "snp500"])
        self.assertEqual(result["refreshed"][0]["normalized_requested_assets"], ["sol", "usdc", "snp500"])
        self.assertEqual(result["refreshed"][0]["balance_keys_written"], ["snp500", "sol", "usdc"])
        self.assertEqual(result["refreshed"][0]["latest_balances"]["snp500"], 38089.22)

    def test_refresh_balances_diagnostics_normalize_figure_mint(self):
        from api.main import refresh_balances

        figure_mint = "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump"

        def fake_run_cmd(cmd, timeout=60):
            return {"returncode": 0, "stdout": "ok", "stderr": ""}

        with (
            patch(
                "api.main.load_accounts",
                return_value={
                    "accounts": {
                        "sol-test": {
                            "chain": "solana",
                            "address": "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                            "default_assets": ["sol"],
                        }
                    }
                },
            ),
            patch("api.main._run_cmd", side_effect=fake_run_cmd),
            patch("api.main._write_portfolio_snapshot"),
            patch("api.main.db.get_latest_balances", return_value={"figure": 4200.0}),
        ):
            result = refresh_balances(
                account="sol-test",
                assets="sol,spl:" + figure_mint,
                force=True,
            )

        row = result["refreshed"][0]
        self.assertEqual(row["requested_assets"], ["sol", "spl:" + figure_mint])
        self.assertEqual(row["normalized_requested_assets"], ["sol", "figure"])
        self.assertEqual(row["balance_keys_written"], ["figure"])
        self.assertEqual(row["latest_balances"]["figure"], 4200.0)

    def test_swap_ui_external_token_warning_mentions_reference_limits(self):
        html = build_ui_html()

        self.assertIn("External token · unverified", html)
        self.assertIn("External token context available for", html)
        self.assertIn("Market references may be incomplete; confirm the final output in your wallet.", html)
        self.assertIn('box.style.display = "none";', html)
        self.assertNotIn("External token metadata used: ", html)
        self.assertNotIn("External-token market references may be stale or incomplete.", html)
        self.assertNotIn("Use quoted output and wallet confirmation as source of truth.", html)
        self.assertIn("USD estimate unavailable / reference uncertain", html)

    def test_swap_ui_recognized_token_symbol_visible_but_mint_preserved_for_quotes(self):
        html = build_ui_html()

        self.assertIn("function canonicalSwapTokenQuery(side)", html)
        self.assertIn("input.dataset.selectedMint = recognized.mint", html)
        self.assertIn("input.dataset.selectedSymbol = recognized.symbol", html)
        self.assertIn("const selectedValue = recognized.symbol || recognized.display_name || recognized.mint", html)
        self.assertIn('from_token: fromToken', html)
        self.assertIn('to_token: toToken', html)
        self.assertIn('const fromToken = canonicalSwapTokenQuery("from");', html)
        self.assertIn('const toToken = canonicalSwapTokenQuery("to");', html)
        self.assertIn("delete input.dataset.selectedMint", html)

    def test_swap_ui_sell_buy_live_value_and_compact_summary_copy_exists(self):
        html = build_ui_html()

        self.assertIn('id="swapSellValueEstimate"', html)
        self.assertIn('id="swapBuyValueEstimate"', html)
        self.assertIn("Swap summary", html)
        self.assertIn("You sell", html)
        self.assertIn("Market reference", html)
        self.assertIn("Best executable quote", html)
        self.assertIn("Route difference vs reference", html)
        self.assertIn(".swap-summary-grid", html)
        self.assertIn(".swap-summary-value", html)
        self.assertIn("font-size:13px", html)
        self.assertIn("white-space:nowrap", html)
        self.assertIn("text-overflow:ellipsis", html)
        self.assertIn('id="swapSpendValueHint" class="swap-summary-value"', html)
        self.assertIn('id="swapBaselineDeltaHint" class="swap-summary-value"', html)
        self.assertIn('id="swapIdealOutputHint" class="swap-summary-value"', html)
        self.assertIn("Preview Quote to compare routes", html)
        self.assertIn("Preview live routes to compare.", html)
        self.assertIn('sellValue.textContent = "≈ " + inputUsdText;', html)
        self.assertIn('buyValue.textContent = "≈ " + bestUsdText;', html)
        self.assertIn('" · Reference estimate before preview"', html)
        self.assertIn('buyEstimate.textContent = "~" + fmtNum(bestOut, 6) + " " + outputToken;', html)
        self.assertIn('const uncertainUsdText = "USD estimate unavailable / reference uncertain";', html)

        render_start = html.index("function renderSwapInlineBaseline(baseline, delta = null)")
        render_end = html.index("function resetSwapQuoteDisplay()", render_start)
        render_block = html[render_start:render_end]
        delta_branch = render_block[render_block.index("if (delta && idealOut"):render_block.index("} else {", render_block.index("if (delta && idealOut"))]
        pre_preview_branch = render_block[render_block.index("} else {", render_block.index("if (delta && idealOut")):render_block.index("if (deltaLine)", render_block.index("if (delta && idealOut"))]
        self.assertIn("const bestOut = Number(baseline.ideal_output_amount) + Number(delta.output_diff_abs);", delta_branch)
        self.assertIn('ideal.textContent = "~" + fmtNum(bestOut, 6) + " " + outputToken + " ≈ " + bestUsdText;', delta_branch)
        self.assertIn('ideal.textContent = "Preview Quote to compare routes";', pre_preview_branch)
        self.assertNotIn('ideal.textContent = idealOut', pre_preview_branch)

    def test_swap_ui_no_route_state_distinguishes_reference_from_executable_route(self):
        html = build_ui_html()

        self.assertIn("No executable route found for this token/amount.", html)
        self.assertIn("Reference price is available, but no live route was found.", html)
        self.assertIn("Reference pricing is not an executable route.", html)
        preview_start = html.index("async function previewSwap()")
        preview_end = html.index("function mintLabel", preview_start)
        preview_block = html[preview_start:preview_end]
        self.assertIn('if (!quote?.ok || !(bestQuote || recommended))', preview_block)
        self.assertIn('$("swapQuotePreview").textContent = JSON.stringify(quote, null, 2);', preview_block)
        self.assertIn('showSwapStatus("warn", "No executable route found", { quote });', preview_block)
        self.assertNotIn("Jupiter HTTP error", preview_block)

    def test_swap_ui_live_baseline_updates_before_preview_from_amount_tokens_and_resolver(self):
        html = build_ui_html()

        amount_listener_start = html.index('bindUiEvent("swapAmount", "input"')
        amount_listener_end = html.index('bindUiEvent("swapFromToken", "focus"', amount_listener_start)
        amount_listener = html[amount_listener_start:amount_listener_end]
        self.assertIn("updateLiveSwapBaseline();", amount_listener)

        shortcut_start = html.index("function setSwapAmountFromHolding(fraction)")
        shortcut_end = html.index("function defaultSwapSolReserveForMax()", shortcut_start)
        shortcut_block = html[shortcut_start:shortcut_end]
        self.assertIn("updateLiveSwapBaseline();", shortcut_block)

        use_token_start = html.index("function useResolvedSwapToken(side)")
        use_token_end = html.index("function resetResolvedSwapTokenSelection(side)", use_token_start)
        use_token_block = html[use_token_start:use_token_end]
        self.assertIn("updateLiveSwapBaseline();", use_token_block)

        resolver_start = html.index("async function resolveSwapTokenInput(side)")
        resolver_end = html.index("function scheduleSwapTokenResolve(side)", resolver_start)
        resolver_block = html[resolver_start:resolver_end]
        self.assertIn("setTokenResolvePreview(side, res.data.token);", resolver_block)
        self.assertIn("updateLiveSwapBaseline();", resolver_block)

    def test_swap_ui_preflights_sol_requirement_before_phantom(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn("function selectedSolHolding()", html)
        self.assertIn("function preflightSolRequirementBeforePhantom()", html)
        self.assertIn("function preparedSwapEstimatedNetworkFeeSol()", html)
        self.assertIn("function preparedSwapProviderId()", html)
        self.assertIn("function renderSolRequirementBlock(result)", html)
        self.assertIn("selectedSolHolding()", html)
        self.assertIn("isSwapBalanceSnapshotFresh(solHolding.balance_ts)", html)
        self.assertIn('fromToken === "SOL" ? Number(summary.amount ?? $("swapAmount")?.value) : 0', html)
        self.assertIn("const requiredSol = swapAmountSol + estimatedFeeSol + bufferSol;", html)
        self.assertIn("const suggestedMaxSol = Math.max(0, availableSol - estimatedFeeSol - bufferSol);", html)
        self.assertIn("Not enough SOL to approve this route before opening Phantom.", html)
        self.assertIn("Provider: Orca", html)
        self.assertIn("Available SOL: ", html)
        self.assertIn("Swap amount: ", html)
        self.assertIn("Estimated network fee: ", html)
        self.assertIn("Fee/account setup buffer: ", html)
        self.assertIn("Suggested max spend: ", html)
        self.assertIn("const solRequirement = preflightSolRequirementBeforePhantom();", sign_block)
        self.assertIn("renderSolRequirementBlock(solRequirement)", sign_block)
        self.assertLess(
            sign_block.index("preflightSolRequirementBeforePhantom()"),
            sign_block.index("phantomProvider.signTransaction(tx)"),
        )

    def test_swap_ui_preflights_prepared_transaction_before_phantom(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn('fetchMaybeJson("/swap/execute/preflight"', html)
        self.assertIn("function preflightPreparedSwapBeforePhantom()", html)
        self.assertIn("function renderSwapPreflightFailureDetail(preflight)", html)
        self.assertIn("function safeSwapPreflightLogPreview(logs)", html)
        self.assertIn("transaction_base64: latestPreparedSwap?.transaction_base64 || \"\"", html)
        self.assertIn("const preparedPreflight = await preflightPreparedSwapBeforePhantom();", sign_block)
        self.assertIn("This Orca route would likely fail before Phantom approval.", html)
        self.assertIn("This route appears to require additional SOL for account setup/rent.", html)
        self.assertNotIn("Simulation indicates insufficient SOL or account setup/rent requirements.", html)
        self.assertIn("Try a lower amount, add SOL, or choose another route.", html)
        self.assertIn("function findPreflightAlternativeSuggestion(failedProvider, failedVariant)", html)
        self.assertIn("function renderPreflightAlternativeNudge(preflight)", html)
        self.assertIn("renderPreflightAlternativeNudge(preparedPreflight);", sign_block)
        self.assertIn("Simulation category: ", html)
        self.assertNotIn("Logs: ", html)
        self.assertNotIn("Program AToken", html)
        self.assertNotIn("Program Tokenkeg", html)
        self.assertNotIn("requirements..", html)
        self.assertIn("preparedPreflight.simulation_supported === true", sign_block)
        self.assertLess(
            sign_block.index("preflightPreparedSwapBeforePhantom()"),
            sign_block.index("phantomProvider.signTransaction(tx)"),
        )

    def test_swap_ui_preflight_failure_nudges_to_alternative_without_auto_prepare(self):
        html = build_ui_html()

        helper_start = html.index("function findPreflightAlternativeSuggestion(failedProvider, failedVariant)")
        helper_end = html.index("function renderRouteActionButton", helper_start)
        helper_block = html[helper_start:helper_end]

        self.assertIn("quote?.direct_route_check || null", helper_block)
        self.assertIn("quote?.recommended_executable_option || null", helper_block)
        self.assertIn("...(Array.isArray(quote?.other_options) ? quote.other_options : [])", helper_block)
        self.assertIn("if (!isExecutableRouteOption(opt)) continue;", helper_block)
        self.assertIn("if (providerKey === failedProviderKey && variantKey === failedVariantKey) continue;", helper_block)
        self.assertIn("const chosen = executable.find(isDirectLikeRouteOption) || executable[0];", helper_block)
        self.assertIn('"direct route"', helper_block)

        nudge_start = html.index("function renderPreflightAlternativeNudge(preflight)")
        nudge_end = html.index("async function preflightPreparedSwapBeforePhantom", nudge_start)
        nudge_block = html[nudge_start:nudge_end]

        self.assertIn("failed preflight. Try the ", nudge_block)
        self.assertIn("button.type = \"button\";", nudge_block)
        self.assertIn("event.stopPropagation();", nudge_block)
        self.assertIn("showPreflightAlternativeRoute(suggestion);", nudge_block)
        self.assertNotIn("prepareSwapRoute(", nudge_block)
        self.assertIn("routeActionButtonForSuggestion(suggestion)", html)
        self.assertIn('[data-swap-execute="true"]', html)
        self.assertIn(".preflight-alternative-nudge", html)

    def test_swap_ui_renders_preflight_diagnostics_in_debug_json(self):
        html = build_ui_html()

        self.assertIn("let latestSwapPreflightResponse = null;", html)
        self.assertNotIn('id="swapVisiblePreflightDebugWrap"', html)
        self.assertIn('id="swapVisiblePreflightDebug"', html)
        self.assertIn("No preflight check yet.", html)
        self.assertIn('id="swapPreflightDebug"', html)
        self.assertIn("Latest preflight diagnostics", html)
        self.assertIn('<details id="swapDebugWrap" class="card quote-debug-details"', html)
        self.assertIn("Developer quote debug JSON", html)
        self.assertIn('if (payload && kind !== "ok")', html)
        self.assertIn('$("swapDebugWrap").open = false;', html)
        self.assertNotIn('<details class="card" id="swapVisiblePreflightDebugWrap" open', html)
        self.assertNotIn('<details id="swapDebugWrap" class="card quote-debug-details" open', html)
        self.assertIn("function sanitizeSwapPreflightDebug(value)", html)
        self.assertIn("function renderSwapPreflightDebug(response)", html)
        self.assertIn("latestSwapPreflightResponse = sanitizeSwapPreflightDebug(response || null);", html)
        self.assertIn('const visibleBox = $("swapVisiblePreflightDebug");', html)
        self.assertIn("visibleBox.textContent = debugJson;", html)
        self.assertIn("const debugJson = JSON.stringify(latestSwapPreflightResponse, null, 2);", html)
        self.assertIn("renderSwapPreflightDebug(enrichedResult);", html)
        self.assertIn("renderSwapPreflightDebug(enrichedFallback);", html)
        self.assertIn('console.debug("swap preflight", latestSwapPreflightResponse);', html)
        self.assertIn("transaction_diagnostics", html)
        self.assertIn("function enrichSwapPreflightWithSolDiagnostics(preflight)", html)
        self.assertIn("setup_cost_estimate_lamports", html)
        self.assertIn("client_sol_diagnostics", html)
        self.assertIn("input_amount_lamports", html)
        self.assertIn("available_sol_lamports", html)
        self.assertIn("estimated_total_required_lamports", html)
        self.assertIn("estimated_shortfall_lamports", html)
        self.assertIn("suggested_max_input_lamports", html)
        self.assertIn("estimated_non_input_sol_required_lamports", html)
        self.assertIn("estimated_sol_shortfall_lamports", html)
        self.assertIn("account_setup_failure_not_explained_by_sol_balance", html)
        self.assertIn("add_sol_for_account_setup", html)
        self.assertIn("enough_sol_for_setup_but_preflight_failed", html)
        self.assertIn("const enrichedResult = enrichSwapPreflightWithSolDiagnostics(result);", html)

        debug_start = html.index("function sanitizeSwapPreflightDebug(value)")
        debug_end = html.index("function clearSwapQuoteFreshness()", debug_start)
        debug_block = html[debug_start:debug_end]
        self.assertIn('lowered.includes("transaction_base64")', debug_block)
        self.assertIn('lowered.includes("signed_transaction")', debug_block)
        self.assertIn('lowered.includes("rpc_url")', debug_block)
        self.assertIn('lowered.includes("api_key")', debug_block)
        self.assertIn('lowered.includes("apikey")', debug_block)
        self.assertIn('lowered.includes("secret")', debug_block)

    def test_swap_ui_renders_external_token_quote_notice(self):
        html = build_ui_html()

        self.assertIn('id="swapExternalTokenNotice"', html)
        self.assertIn("function renderSwapExternalTokenNotice(quote)", html)
        self.assertIn("Array.isArray(quote?.external_tokens)", html)
        self.assertIn("External token · unverified", html)
        self.assertIn("quote-external-details", html)
        self.assertIn('box.style.display = "none";', html)
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
        self.assertIn("Token stats & holder concentration", html)
        self.assertNotIn('<div style="font-weight:600;">Holder concentration</div>', html)
        self.assertNotIn('color:#e5eefb;">Holder concentration</div>', html)
        self.assertIn("Top holder", html)
        self.assertIn("Top 5", html)
        self.assertIn("Top 10", html)
        self.assertIn("accounts sampled", html)
        self.assertIn("number_of_accounts_used", html)
        self.assertIn("sampled_account_count", html)
        self.assertIn("Open Bubblemaps", html)
        self.assertIn("Based on visible token accounts from Solana RPC. Separate from route ranking.", html)
        self.assertIn("Distribution only — not a safety score.", html)
        self.assertIn('code === "TOKEN_HOLDER_CONCENTRATION_RATE_LIMITED"', html)
        self.assertIn("Holder data unavailable", html)
        self.assertIn("Holder data partially available", html)
        self.assertIn("partial_data_available", html)
        self.assertIn("function renderTokenMarketStatsLine()", html)
        self.assertIn("function selectedTokenMarketStats()", html)
        self.assertIn("function formatCompactUsd(value)", html)
        self.assertIn("function tokenMintMatchesMarketStatsSource(token, source)", html)
        self.assertIn("function tokenMarketStatsValues(source = {})", html)
        self.assertIn("function mergeTokenMarketStats(sources = [])", html)
        self.assertIn("if (!Number.isFinite(n) || n <= 0) return \"\";", html)
        self.assertIn("latestSwapQuoteResponse?.external_tokens", html)
        self.assertIn("latestSwapQuoteResponse?.inline_baseline?.pricing_source_detail", html)
        self.assertIn("pricingSourceDetail?.to_token", html)
        self.assertIn("pricingSourceDetail?.from_token", html)
        self.assertIn("externalTokens.length === 1 ? externalTokens[0] : null", html)
        self.assertIn("matchedExternalToken", html)
        self.assertIn("matchedToToken", html)
        self.assertIn("matchedFromToken", html)
        self.assertIn("liquidity: source?.liquidity_usd ?? source?.liquidity?.usd", html)
        self.assertIn("Liquidity ", html)
        self.assertIn("24h volume ", html)
        self.assertIn("FDV ", html)
        self.assertIn("Mkt cap ", html)
        self.assertIn('return bits.length', html)
        self.assertIn(': "";', html)
        self.assertIn("liquidity_usd", html)
        self.assertIn("volume_24h", html)
        self.assertIn("marketCap", html)
        self.assertIn("let latestHolderConcentrationData = null;", html)
        self.assertIn("latestHolderConcentrationData = data || null;", html)
        self.assertIn("if (latestHolderConcentrationData) {", html)
        self.assertIn("renderHolderConcentration(latestHolderConcentrationData);", html)
        self.assertIn("Holder diagnostics", html)
        self.assertIn("holderDiagnosticsJson", html)
        self.assertIn("rpc_url_source", html)
        self.assertIn("rpc_methods_attempted", html)
        self.assertIn("rate_limited", html)
        self.assertIn("cached", html)
        self.assertIn("Supply found; largest accounts unavailable.", html)
        self.assertIn("const technicalMessage =", html)
        self.assertIn('box.className = "muted";', html)
        self.assertIn('${escapeHtml(technicalMessage)}', html)
        self.assertIn("Solana RPC is rate-limited right now. Try again later.", html)
        self.assertIn("Holder concentration unavailable right now.", html)
        self.assertNotIn('<div style="font-weight:600;">Holder concentration unavailable right now.</div>', html)
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
        self.assertIn('const fromToken = canonicalSwapTokenQuery("from");', html)
        self.assertIn('const toToken = canonicalSwapTokenQuery("to");', html)

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
        self.assertIn("${escapeHtml(cleanRoutePath)}", html)
        self.assertIn("two-hop · Steps: ${escapeHtml(String(routeSteps))}", html)
        self.assertIn("${escapeHtml(routeShape)} · Steps: ${escapeHtml(String(routeSteps))}", html)

    def test_swap_ui_includes_prepare_route_state_and_endpoint_call(self):
        html = build_ui_html()

        self.assertIn('id="swapExecutionStatus"', html)
        self.assertIn('let latestPreparedSwap = null;', html)
        self.assertIn('let swapExecutionState = "idle";', html)
        self.assertIn("function setSwapExecutionStatus(state, text, detail = null)", html)
        status_start = html.index("function setSwapExecutionStatus(state, text, detail = null)")
        status_end = html.index("function sanitizeSwapPreflightDebug", status_start)
        status_block = html[status_start:status_end]
        self.assertIn('const card = $("swapQuoteCard");', status_block)
        self.assertIn('if (card) card.style.display = "block";', status_block)
        self.assertIn('box.style.display = "block";', status_block)
        self.assertIn("async function prepareSwapRoute(routeRequest)", html)
        self.assertIn('fetchMaybeJson("/swap/execute/prepare"', html)
        self.assertIn("provider,", html)
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

    def test_swap_ui_extracts_swap_prepare_error_details(self):
        html = build_ui_html()

        self.assertIn("function extractSwapPrepareErrorDetail(data)", html)
        self.assertIn("const error = data?.error || {};", html)
        self.assertIn("code: compactSwapPrepareErrorText(error.code)", html)
        self.assertIn("message: compactSwapPrepareErrorText(error.message)", html)
        self.assertIn("detail: compactSwapPrepareErrorText(error.detail)", html)

    def test_swap_ui_maps_jupiter_auth_prepare_error_to_jup_api_key_copy(self):
        html = build_ui_html()

        self.assertIn('code === "SWAP_EXECUTION_JUPITER_AUTH_REQUIRED"', html)
        self.assertIn("Jupiter authorization is required for execution prepare. Configure JUP_API_KEY and preview again.", html)

    def test_swap_ui_maps_rate_limited_prepare_error(self):
        html = build_ui_html()

        self.assertIn('code === "SWAP_EXECUTION_RATE_LIMITED"', html)
        self.assertIn("Jupiter is rate-limited right now. Try again later.", html)

    def test_swap_ui_maps_prepare_failed_error(self):
        html = build_ui_html()

        self.assertIn('code === "SWAP_EXECUTION_PREPARE_FAILED"', html)
        self.assertIn("Swap preparation failed. Preview again.", html)

    def test_swap_ui_prepare_failure_logs_backend_response(self):
        html = build_ui_html()
        start = html.index("async function prepareSwapRoute(routeRequest)")
        end = html.index("function isPhantomUserRejection", start)
        prepare_block = html[start:end]

        self.assertIn('console.warn("Swap execution prepare failed"', prepare_block)
        self.assertIn("response: redactSwapPrepareFailureResponse(res.data)", prepare_block)

    def test_swap_ui_prepare_failure_displays_backend_error_code_detail(self):
        html = build_ui_html()
        start = html.index("async function prepareSwapRoute(routeRequest)")
        end = html.index("function isPhantomUserRejection", start)
        prepare_block = html[start:end]

        self.assertIn("const errorDetail = extractSwapPrepareErrorDetail(res.data);", prepare_block)
        self.assertIn('"Provider detail: " + errorDetail.providerDetail', prepare_block)
        self.assertIn('"Provider detail: " + errorDetail.providerMessage', prepare_block)
        self.assertIn('"Execution error: " + errorDetail.code', prepare_block)

    def test_swap_ui_prepare_failure_does_not_render_transaction_base64(self):
        html = build_ui_html()
        start = html.index("async function prepareSwapRoute(routeRequest)")
        end = html.index("function isPhantomUserRejection", start)
        prepare_block = html[start:end]

        self.assertNotIn("transaction_base64", prepare_block)
        self.assertNotIn("swapTransaction", prepare_block)

    def test_swap_ui_prepare_route_requires_phantom_and_does_not_sign(self):
        html = build_ui_html()
        start = html.index("async function prepareSwapRoute(routeRequest)")
        end = html.index("function isPhantomUserRejection", start)
        prepare_block = html[start:end]

        self.assertIn("Connect Phantom to prepare this swap.", prepare_block)
        self.assertIn("if (!activeWalletPubkey)", prepare_block)
        self.assertIn("SWAP_EXECUTABLE_PROVIDERS.has(provider)", prepare_block)
        self.assertIn("SWAP_EXECUTABLE_VARIANTS[provider]", prepare_block)
        self.assertIn("setSwapPreparedActionVisible(true);", prepare_block)
        self.assertNotIn("signTransaction", prepare_block)
        self.assertNotIn("sendRawTransaction", prepare_block)
        self.assertNotIn("VersionedTransaction", prepare_block)
        self.assertNotIn("signAndSubmitPreparedSwap", prepare_block)

    def test_swap_ui_blocks_prepare_when_fresh_from_balance_is_insufficient(self):
        html = build_ui_html()

        self.assertIn("function validateSwapInputBalanceBeforePrepare(amount)", html)
        self.assertIn("const holding = selectedFromHolding();", html)
        self.assertIn("const fresh = isSwapBalanceSnapshotFresh(holding.balance_ts) && !swapBalancesStaleAfterSubmit;", html)
        self.assertIn("requested <= available", html)
        self.assertIn("You do not currently hold \" + label + \".", html)
        self.assertIn("Insufficient \" + label + \" balance for this swap.", html)
        self.assertIn("You only have \" + availableText + \" \" + label + \", but you entered \" + requestedText + \" \" + label", html)
        self.assertIn("Enter an amount within your available balance.", html)

        start = html.index("async function prepareSwapRoute(routeRequest)")
        end = html.index("function isPhantomUserRejection", start)
        prepare_block = html[start:end]
        self.assertIn("const inputBalanceCheck = validateSwapInputBalanceBeforePrepare(amount);", prepare_block)
        self.assertIn("if (inputBalanceCheck.ok === false)", prepare_block)
        self.assertIn("latestPreparedSwap = null;", prepare_block)
        self.assertIn("renderSwapPreflightDebug(null);", prepare_block)
        self.assertIn("setSwapPreparedActionVisible(false);", prepare_block)
        self.assertIn("setSwapExecutionStatus(\"failed\", inputBalanceCheck.message, inputBalanceCheck.detail);", prepare_block)
        self.assertLess(
            prepare_block.index("validateSwapInputBalanceBeforePrepare(amount)"),
            prepare_block.index('fetchMaybeJson("/swap/execute/prepare"'),
        )

    def test_swap_ui_renders_swap_button_for_supported_executable_cards(self):
        html = build_ui_html()

        self.assertIn("function isExecutableRouteOption(opt)", html)
        self.assertIn('"jupiter-metis"', html)
        self.assertIn('"raydium-trade-api"', html)
        self.assertIn('"orca-whirlpool"', html)
        self.assertIn('"pumpswap"', html)
        executable_providers_block = html[
            html.index("const SWAP_EXECUTABLE_PROVIDERS"):
            html.index("const SWAP_EXECUTABLE_VARIANTS")
        ]
        self.assertIn('"pumpswap"', executable_providers_block)
        self.assertIn('"meteora-dlmm"', executable_providers_block)
        self.assertIn('"raydium_quote"', html)
        self.assertIn('"orca_whirlpool_quote"', html)
        self.assertIn('"meteora_dlmm_quote"', html)
        self.assertIn('"pumpswap_quote"', html)
        self.assertIn('"meteora-dlmm": new Set(["meteora_dlmm_quote"])', html)
        self.assertIn("Swap via Meteora", html)
        self.assertNotIn('"phantom-routing-api"', executable_providers_block)
        self.assertIn("SWAP_EXECUTABLE_PROVIDERS.has(provider)", html)
        self.assertIn("supportedVariants?.has(opt?.variant_id) === true", html)
        self.assertIn("opt?.execution_readiness?.execution_ready === true", html)
        self.assertIn("opt?.is_clickable === true", html)
        self.assertIn("opt?.is_comparison_only !== true", html)
        self.assertIn('opt?.execution_status === "executable_capable"', html)
        self.assertIn("!!opt?.variant_id", html)
        self.assertIn('data-swap-execute="true"', html)
        self.assertNotIn('data-swap-execute="true" disabled', html)
        self.assertIn('data-provider="${escapeHtml(opt.provider)}"', html)
        self.assertIn('data-variant-id="${escapeHtml(opt.variant_id)}"', html)
        self.assertIn('const role = cardRole || opt.kind || "route";', html)
        self.assertIn('data-card-role="${escapeHtml(role)}"', html)
        self.assertIn("Swap via Raydium", html)
        self.assertIn("Swap via Orca", html)
        self.assertIn("Swap via PumpSwap", html)
        self.assertNotIn("Execution-ready via", html)
        self.assertNotIn("Comparison-only - no swap action available yet.", html)

    def test_swap_ui_direct_route_uses_direct_variant_for_prepare(self):
        html = build_ui_html()

        self.assertIn('showDirectAction: true,', html)
        self.assertIn('cardRole: "direct"', html)
        self.assertIn('renderRouteActionButton(executableRouteButtonLabel(opt), opt, opts.cardRole || "direct")', html)
        self.assertIn("variant_id: button.dataset.variantId", html)
        self.assertNotIn("Try direct route", html)

    def test_swap_ui_prepare_click_uses_event_delegation_and_preserves_preview_flow(self):
        html = build_ui_html()

        self.assertIn("function handleSwapExecuteClick(event)", html)
        self.assertIn('event.target?.closest?.(\'[data-swap-execute="true"]\')', html)
        self.assertIn("if (button.disabled) return;", html)
        self.assertIn("function bindUiEvent(id, type, handler)", html)
        self.assertIn("if (!el) return null;", html)
        self.assertIn('document.addEventListener("click", handleSwapExecuteClick);', html)
        self.assertNotIn('$("swapCard").addEventListener("click", handleSwapExecuteClick);', html)
        self.assertIn('.modal-backdrop { position: fixed; inset: 0; display: none;', html)
        self.assertIn('z-index: 50; pointer-events: none;', html)
        self.assertIn('.modal-backdrop.is-open { display: flex; pointer-events: auto; }', html)
        self.assertIn('if (event.target?.id === "swapSuccessTxCopy") copySwapSuccessSignature();', html)
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
        self.assertIn('bindUiEvent("btnSignPreparedSwap", "click", signAndSubmitPreparedSwap);', html)
        self.assertIn('bindUiEvent("swapSignAcknowledgement", "change", updateSwapSignButtonState);', html)
        self.assertIn("Swap submitted", html)
        self.assertIn("Transaction is confirming on Solana.", html)
        self.assertIn("Confirming on Solana", html)
        self.assertIn('renderSwapSuccessRow("Route", details.provider)', html)
        self.assertIn("View on Solscan", html)
        self.assertIn('renderSwapSuccessRow("Expected receive", details.expected)', html)
        self.assertNotIn("Swap submitted successfully", html)
        self.assertNotIn("Swap successful", html)
        self.assertIn("Balances may have changed after the last swap — refresh balances.", html)
        self.assertIn('id="swapSuccessModal"', html)
        self.assertIn('id="swapSuccessModalPanel"', html)
        self.assertIn('id="swapSuccessModalTitle"', html)
        self.assertIn('id="swapSuccessModalBody"', html)
        self.assertIn('id="swapSuccessExplorerLink"', html)
        self.assertIn('id="swapSuccessRocket"', html)
        self.assertIn('id="swapSuccessRocketLogo"', html)
        self.assertIn('id="swapSuccessRocketSymbol"', html)
        self.assertIn('id="swapSuccessCheck"', html)
        self.assertIn('id="swapSuccessBalanceStatus"', html)
        self.assertIn('id="swapSuccessTxCopy"', html)
        self.assertIn('id="btnCloseSwapSuccessModal"', html)
        self.assertIn("function showSwapSuccessModal(details)", html)
        self.assertIn("function updateSwapSuccessModalState(state)", html)
        self.assertIn("function pollSwapConfirmationStatus(signature)", html)
        self.assertIn("SWAP_CONFIRMATION_POLL_INTERVAL_MS = 1500", html)
        self.assertIn("SWAP_CONFIRMATION_POLL_TIMEOUT_MS = 20000", html)
        self.assertIn("function closeSwapSuccessModal()", html)
        self.assertIn("function swapSuccessVariantForToken(symbol)", html)
        self.assertIn("function swapSuccessTokenVisual(summary)", html)
        self.assertIn('return normalized === "SOL" || normalized === "USDC" ? "neutral" : "risk-on";', html)
        self.assertIn('renderSwapSuccessRow("Sold", details.spent)', html)
        self.assertIn('renderSwapSuccessRow("Expected receive", details.expected)', html)
        self.assertIn('renderSwapSuccessRow("Route", details.provider)', html)
        self.assertIn("renderSwapSuccessTxRow(details.signature)", html)
        self.assertIn('String(details.tokenFallback || "").slice(0, 4)', html)
        self.assertIn("rocketLogo.onerror", html)
        self.assertIn("function copySwapSuccessSignature()", html)
        self.assertIn("function appendUsdEstimateText(baseText, usdValue)", html)
        self.assertIn("function preparedSwapQuoteOption(summary)", html)
        self.assertIn("function preparedSwapModalUsdEstimates(summary)", html)
        self.assertIn("function preparedSwapDisplayCost(summary)", html)
        self.assertIn("const modalUsdEstimates = preparedSwapModalUsdEstimates(summary);", html)
        self.assertIn("const spentWithUsd = appendUsdEstimateText(", html)
        self.assertIn("const expectedWithUsd = appendUsdEstimateText(", html)
        self.assertIn("modalUsdEstimates.spentUsd", html)
        self.assertIn("modalUsdEstimates.expectedUsd", html)
        self.assertIn("matchedOption?.estimated_output_usd", html)
        self.assertIn("baseline.input_usd_value", html)
        self.assertIn("outputUsdPrice * expectedAmount", html)
        self.assertIn("const swapCostText = preparedSwapDisplayCost(summary);", html)
        self.assertIn("spent: spentWithUsd", html)
        self.assertIn("expected: expectedWithUsd", html)
        self.assertIn("swapCost: swapCostText", html)
        self.assertIn("signature,", html)
        self.assertIn("variant: tokenVisual.variant", html)
        self.assertIn("tokenLogoUri: tokenVisual.logoUri", html)
        self.assertIn("tokenFallback: tokenVisual.fallback", html)
        self.assertIn('title.textContent = "Swap complete";', html)
        self.assertIn('subtitle.textContent = "Your swap was confirmed on Solana.";', html)
        self.assertIn('statusText.textContent = "Confirmed on Solana";', html)
        self.assertIn('title.textContent = "Swap failed";', html)
        self.assertIn('statusText.textContent = "Still confirming";', html)
        self.assertNotIn('renderSwapSuccessRow("Received"', html)
        self.assertIn('fetchMaybeJson("/swap/transaction/status?" + qs({ signature }))', html)
        self.assertIn('updateSwapSuccessModalState("complete");', html)
        self.assertIn('updateSwapSuccessModalState("failed");', html)
        self.assertIn('updateSwapSuccessModalState("timeout");', html)
        self.assertIn("Network: Solana mainnet", html)
        self.assertIn(".swap-success-rocket", html)
        self.assertIn("@keyframes swap-rocket-launch", html)
        self.assertIn("@keyframes swap-check-pulse", html)
        self.assertIn("@media (prefers-reduced-motion: reduce)", html)
        self.assertIn('modal.classList.add("is-open")', html)
        self.assertIn('bindUiEvent("btnCloseSwapSuccessModal", "click", closeSwapSuccessModal);', html)
        self.assertIn('if (event.target?.id === "swapSuccessTxCopy") copySwapSuccessSignature();', html)
        self.assertIn("Swap failed.", html)
        self.assertIn("Swap was rejected in Phantom.", html)
        self.assertIn("Quote expired. Preview again.", html)

    def test_swap_success_modal_only_runs_after_successful_submit_signature(self):
        html = build_ui_html()
        sign_start = html.index("async function signAndSubmitPreparedSwap()")
        sign_end = html.index("function handleSwapExecuteClick", sign_start)
        sign_block = html[sign_start:sign_end]

        self.assertIn('signature = submitResponse.data?.signature;', sign_block)
        self.assertIn("renderSwapSubmittedSuccess(signature);", sign_block)
        self.assertNotIn("showSwapSuccessModal(", sign_block)

        success_start = html.index("function renderSwapSubmittedSuccess(signature)")
        success_end = html.index("async function signAndSubmitPreparedSwap()", success_start)
        success_block = html[success_start:success_end]
        self.assertIn("showSwapSuccessModal({", success_block)
        self.assertIn("setCompactSubmittedStatus(signature);", success_block)
        self.assertIn("provider: providerLabel", success_block)
        self.assertIn("spent,", success_block)
        self.assertIn("expected,", success_block)
        self.assertIn("explorer,", success_block)
        self.assertIn("signature,", success_block)
        self.assertIn("pollSwapConfirmationStatus(signature);", success_block)
        self.assertNotIn('title.textContent = "Swap complete";', success_block)

        signing_catch = sign_block[sign_block.index("swap signing error:"):sign_block.index("if (!signedTx)")]
        self.assertNotIn("renderSwapSubmittedSuccess", signing_catch)
        self.assertNotIn("showSwapSuccessModal", signing_catch)

    def test_swap_ui_includes_runtime_error_helpers(self):
        html = build_ui_html()

        self.assertIn("function compactSwapRuntimeErrorText(value)", html)
        self.assertIn("function swapRuntimeErrorDetail(err)", html)
        self.assertIn("function swapRuntimeFailureMessage(phase, err)", html)
        self.assertIn("Reason: ", html)
        self.assertIn("Provider detail: ", html)
        self.assertIn("transaction_base64|swapTransaction", html)
        self.assertIn("api[-_]?key", html)

    def test_swap_ui_signing_runtime_failure_copy_exists(self):
        html = build_ui_html()

        self.assertIn("Could not read prepared swap transaction. Preview again.", html)
        self.assertIn("Phantom signing failed.", html)
        self.assertIn("Phantom signing did not return a signed transaction.", html)
        self.assertIn("Transaction submission failed.", html)
        self.assertIn("Transaction submission was blocked by RPC.", html)
        self.assertIn("RPC is rate-limited. Try again later.", html)
        self.assertIn("Swap cannot be submitted yet. Configure SWAP_SUBMIT_RPC_URL.", html)
        self.assertIn("Quote expired. Preview again.", html)

    def test_swap_ui_signing_failure_logs_phase_specific_errors(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn('console.error("swap deserialize error:", err);', sign_block)
        self.assertIn('console.error("swap signing error:", err);', sign_block)
        self.assertIn('console.error("swap submit error:", err);', sign_block)

    def test_swap_ui_signing_displays_execution_phase_detail(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn("Execution phase: deserialize", sign_block)
        self.assertIn("Execution phase: signing", sign_block)
        self.assertIn("Execution phase: submit", sign_block)

    def test_swap_ui_signing_does_not_render_transaction_base64_in_status(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        for line in sign_block.splitlines():
            if "setSwapExecutionStatus(" in line:
                self.assertNotIn("transaction_base64", line)
                self.assertNotIn("swapTransaction", line)

    def test_swap_ui_signing_requires_prepared_swap_phantom_and_versioned_tx(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn("if (!latestPreparedSwap || !latestPreparedSwap.transaction_base64)", sign_block)
        self.assertIn("latestPreparedSwap?.submit_preflight?.can_submit === false", html)
        self.assertIn("const ack = $(\"swapSignAcknowledgement\");", sign_block)
        self.assertIn("if (!ack?.checked)", sign_block)
        self.assertIn("Confirm you understand this is a real mainnet swap before signing.", sign_block)
        self.assertIn('latestPreparedSwap.transaction_format !== "versioned"', sign_block)
        self.assertIn("if (!phantomProvider || !activeWalletPubkey)", sign_block)
        self.assertIn("if (!solanaWeb3?.VersionedTransaction?.deserialize)", sign_block)
        self.assertIn("Swap signing is not supported in this browser session.", sign_block)
        self.assertIn("Connect Phantom to continue.", sign_block)

    def test_swap_ui_preflight_failure_clears_prepared_state_before_phantom(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]
        failure_start = sign_block.index("if (preparedPreflight && preparedPreflight.ok === false)")
        failure_end = sign_block.index("let tx;", failure_start)
        failure_block = sign_block[failure_start:failure_end]

        self.assertIn("latestPreparedSwap = null;", failure_block)
        self.assertIn("setSwapPreparedActionVisible(false);", failure_block)
        self.assertIn("This route would likely fail before Phantom approval.", failure_block)
        self.assertLess(
            failure_block.index("setSwapPreparedActionVisible(false);"),
            failure_block.index("setSwapExecutionStatus("),
        )
        self.assertNotIn("phantomProvider.signTransaction(tx)", failure_block)

    def test_swap_ui_signing_deserializes_signs_submits_and_confirms(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn("Uint8Array.from(atob(transactionBase64), c => c.charCodeAt(0))", sign_block)
        self.assertIn("solanaWeb3.VersionedTransaction.deserialize(bytes)", sign_block)
        self.assertIn("phantomProvider.signTransaction(tx)", sign_block)
        self.assertIn("bytesToBase64(signedTx.serialize())", sign_block)
        self.assertIn('fetchMaybeJson("/swap/execute/submit"', sign_block)
        self.assertIn("signed_transaction_base64: signedTransactionBase64", sign_block)
        self.assertIn("skip_preflight: false", sign_block)
        self.assertIn('preflight_commitment: "confirmed"', sign_block)
        self.assertIn("MAINNET_EXPLORER_BASE", html)
        self.assertNotIn("sendRawTransaction", sign_block)

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

    def test_swap_ui_signing_uses_backend_submit_not_browser_rpc(self):
        html = build_ui_html()
        start = html.index("async function signAndSubmitPreparedSwap()")
        end = html.index("function handleSwapExecuteClick", start)
        sign_block = html[start:end]

        self.assertIn("/swap/execute/submit", sign_block)
        self.assertIn("signed_transaction_base64", sign_block)
        self.assertIn("SWAP_SUBMIT_FORBIDDEN", html)
        self.assertIn("SWAP_SUBMIT_RATE_LIMITED", html)
        self.assertIn("SWAP_SUBMIT_FAILED", html)
        self.assertIn("MAINNET_EXPLORER_BASE", html)
        self.assertIn("renderSwapSubmittedSuccess(signature)", sign_block)
        self.assertNotIn("MAINNET_RPC_URL", html)
        self.assertNotIn("DEVNET_RPC_URL", sign_block)
        self.assertNotIn("DEVNET_EXPLORER_BASE", sign_block)

    def test_swap_ui_prepared_summary_renders_mainnet_guardrails(self):
        html = build_ui_html()

        self.assertIn("function renderPreparedSwapSummary(prepared)", html)
        self.assertIn("Prepared swap", html)
        self.assertIn("Route: ${escapeHtml(routeLabel)}", html)
        self.assertIn('prepared?.execution_surface_label || summary.provider_label || "Jupiter"', html)
        self.assertIn("From:", html)
        self.assertIn("To:", html)
        self.assertIn("Estimated receive:", html)
        self.assertIn("Minimum receive:", html)
        self.assertIn("Slippage:", html)
        self.assertIn("Network: Solana mainnet", html)
        self.assertIn("Phantom may require extra SOL for network fees or account setup beyond the entered amount.", html)
        self.assertNotIn("Keep extra SOL for network fees before approving in Phantom.</div>`", html)
        self.assertIn("This is a real mainnet transaction. Review in Phantom before signing.", html)

        start = html.index("function renderPreparedSwapSummary(prepared)")
        end = html.index("function resetSwapExecutionPrepare", start)
        summary_block = html[start:end]
        self.assertNotIn('lines.push("<div style="', summary_block)
        self.assertNotIn("transaction_base64", summary_block)

    def test_swap_ui_prepare_reset_clears_acknowledgement_and_disables_sign_button(self):
        html = build_ui_html()

        self.assertIn("function setSwapPreparedActionVisible(visible)", html)
        self.assertIn('const card = $("swapQuoteCard");', html)
        self.assertIn("if (card && visible) card.style.display = \"block\";", html)
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
        self.assertEqual(option["execution_status"], "executable_capable")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_trade_api")
        self.assertEqual(option["cost_transparency"]["ranking_basis"], "highest_receive_amount")
        self.assertEqual(
            option["cost_transparency"]["network_fee_scope"],
            "unavailable_for_quote_only_preview",
        )
        self.assertTrue(option["cost_transparency"]["explicit_fees_may_be_reflected_in_output"])
        self.assertFalse(option["is_comparison_only"])
        self.assertTrue(option["is_clickable"])
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

    def test_build_pumpswap_quote_payload_includes_known_amm_pool_addresses_for_audit(self):
        payload = _build_pumpswap_quote_payload(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint="CvPrreLgpZ9tjjoyk8qAwiAFvuEXooU7wL25hanApump",
            amount_raw=1000000000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            known_amm_pool_addresses=[
                "Gc5npgagnWZonKjkuRqMLMxyYbJzirRAw7fFn6jJnwe8",
                "Gc5npgagnWZonKjkuRqMLMxyYbJzirRAw7fFn6jJnwe8",
            ],
        )

        self.assertEqual(
            payload["known_amm_pool_addresses"],
            ["Gc5npgagnWZonKjkuRqMLMxyYbJzirRAw7fFn6jJnwe8"],
        )
        self.assertTrue(payload["discover_canonical_pool"])
        self.assertEqual(payload["discovery_mode"], "canonical_pumpswap_pool")

    def test_known_pumpswap_amm_pool_addresses_from_meta_reads_pair_address(self):
        addresses = _known_pumpswap_amm_pool_addresses_from_meta(
            {"pair_address": "Gc5npgagnWZonKjkuRqMLMxyYbJzirRAw7fFn6jJnwe8"},
            {
                "pricing_source_detail": {
                    "pair_address": "AnotherPumpAmmPool11111111111111111111111"
                }
            },
            None,
        )

        self.assertEqual(
            addresses,
            [
                "AnotherPumpAmmPool11111111111111111111111",
                "Gc5npgagnWZonKjkuRqMLMxyYbJzirRAw7fFn6jJnwe8",
            ],
        )

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
        self.assertEqual(payload["unsupported_pair_reason"], "pumpswap_direct_sol_pair_only")
        self.assertIn("SOL <-> pump-token canonical pools only", payload["unsupported_pair_detail"])
        self.assertIn("composed route", payload["unsupported_pair_detail"])

    def test_build_pumpswap_quote_payload_supports_external_pump_token_to_sol(self):
        payload = _build_pumpswap_quote_payload(
            input_mint="3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump",
            output_mint=METEORA_DLMM_SOL_MINT,
            amount_raw=20_000_000_000,
            slippage_bps=50,
            rpc_url="https://example.invalid",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertEqual(payload["pool_candidates"], [])
        self.assertTrue(payload["discover_canonical_pool"])
        self.assertEqual(payload["discovery_mode"], "canonical_pumpswap_pool")
        self.assertNotIn("unsupported_pair", payload)

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

    def test_pumpswap_quote_helper_reports_canonical_pool_discovery_diagnostics(self):
        source = Path("tools/pumpswap_quote_research.mjs").read_text()

        self.assertIn("PUMP_AMM_PROGRAM_ID", source)
        self.assertIn("function canonicalPoolNotFoundError", source)
        self.assertIn("connection.getAccountInfo(poolKey)", source)
        self.assertIn("candidate_pool_address", source)
        self.assertIn("candidate_pool_addresses", source)
        self.assertIn("account_exists", source)
        self.assertIn("account_owner", source)
        self.assertIn("expected_program_id", source)
        self.assertIn("rejection_reason", source)
        self.assertIn('"ACCOUNT_NOT_FOUND"', source)
        self.assertIn('"NOT_CANONICAL_POOL"', source)
        self.assertIn("direct SOL <-> pump-token canonical pool", source)
        self.assertIn("No direct canonical PumpSwap pool was found for this token.", source)
        self.assertIn("Jupiter may still route through Pump.fun Amm as one leg of a multi-hop route.", source)
        self.assertIn("known_amm_pool_addresses", source)
        self.assertIn("function inspectKnownPumpAmmPools", source)
        self.assertIn('"known-pump-amm-pool"', source)
        self.assertIn('"TOKEN_NOT_DIRECT_SOL_PAIR"', source)
        self.assertIn('"POOL_DOES_NOT_MATCH_REQUESTED_PAIR"', source)
        self.assertIn("matches_requested_pair", source)
        self.assertIn("known_pool_diagnostics", source)

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
        self.assertEqual(option["actionability"]["actionability_status"], "benchmark_only")
        self.assertFalse(option["actionability"]["can_build_transaction"])
        self.assertFalse(option["actionability"]["can_handoff"])
        self.assertFalse(option["actionability"]["transaction_payload_present"])
        self.assertFalse(option["actionability"]["route_id_present"])
        self.assertFalse(option["actionability"]["handoff_url_present"])
        self.assertIn("no safe transaction build or handoff path", option["explanation"])

    def test_normalize_phantom_quote_option_detects_but_does_not_expose_action_payloads(self):
        quote = {
            "ok": True,
            "status_code": 200,
            "first_quote_buyAmount": "83843388",
            "quoteResponse": {
                "quotes": [
                    {
                        "id": "quote-123",
                        "route_id": "route-123",
                        "transaction_base64": "hidden-base64",
                        "deeplink_url": "phantom://swap/mock",
                        "buyAmount": "83843388",
                        "sellAmount": "1000000000",
                        "baseProvider": {"id": "phantom", "name": "Phantom"},
                        "sources": [{"name": "Phantom Route", "proportion": "1"}],
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

        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["actionability"]["transaction_payload_present"])
        self.assertTrue(option["actionability"]["route_id_present"])
        self.assertTrue(option["actionability"]["quote_id_present"])
        self.assertTrue(option["actionability"]["handoff_url_present"])
        self.assertFalse(option["actionability"]["can_build_transaction"])
        self.assertFalse(option["actionability"]["can_handoff"])
        self.assertNotIn("hidden-base64", json.dumps(option["actionability"]))
        self.assertNotIn("phantom://swap/mock", json.dumps(option["actionability"]))

    def test_normalize_pumpswap_quote_option_marks_single_pool_executable(self):
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
        self.assertEqual(option["execution_status"], "executable_capable")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_native_pool_sdk")
        self.assertFalse(option["is_comparison_only"])
        self.assertTrue(option["is_clickable"])
        self.assertEqual(option["route_shape"], "single-pool")
        self.assertEqual(option["estimated_output"], 45.0)
        self.assertIsNone(option["min_received"])
        self.assertFalse(option["explicit_route_fees"]["has_explicit_fees"])
        self.assertEqual(option["_sort_out_amount_raw"], 45000000)

    def test_normalize_pumpswap_quote_option_keeps_unsupported_shape_quote_only(self):
        quote = {
            "ok": True,
            "provider": "pumpswap",
            "direction": "unsupported_direction",
            "pool": {
                "address": "GseMAnNDvntR5uFePZ51yZBXzNSn7GdFPkfHwfr6d77J",
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
            "in_amount_raw": "1000000000",
            "out_amount_raw": "45000000",
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

        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])

    def test_normalize_meteora_dlmm_quote_option_marks_single_pool_executable(self):
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
        self.assertEqual(option["execution_status"], "executable_capable")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_native_pool")
        self.assertEqual(option["cost_transparency"]["benchmark_gap_scope"], "reference_comparison_not_fee")
        self.assertEqual(option["cost_transparency"]["cost_completeness"], "partial")
        self.assertFalse(option["is_comparison_only"])
        self.assertTrue(option["is_clickable"])
        self.assertEqual(option["route_label"], "Meteora DLMM")
        self.assertEqual(option["route_shape"], "single-pool")
        self.assertEqual(option["estimated_output"], 84.019465)
        self.assertEqual(option["min_received"], 83.599367)
        self.assertEqual(option["explicit_route_fees"]["route_fee_items"][0]["fee_token"], "SOL")
        self.assertEqual(option["route_steps"][0]["pool_address"], quote["pool"]["address"])
        self.assertEqual(option["raw_quote"]["discovery"]["selected_pool"]["tvl"], 100000)
        self.assertEqual(option["_sort_out_amount_raw"], 84019465)
        self.assertIn("Execution prepare is available", option["explanation"])

    def test_normalize_meteora_dlmm_missing_prepare_data_stays_quote_only(self):
        quote = {
            "ok": True,
            "provider": "meteora_dlmm",
            "pool": {"address": "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6"},
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "84019465",
            "min_out_amount_raw": "83599367",
            "bin_arrays": [],
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

        self.assertEqual(option["execution_status"], "quote_only")
        self.assertTrue(option["is_comparison_only"])
        self.assertFalse(option["is_clickable"])
        self.assertIn("missing pool/bin-array data", option["explanation"])

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
        self.assertEqual(option["execution_status"], "executable_capable")
        self.assertTrue(option["supports_current_pair"])
        self.assertEqual(option["quote_source_type"], "venue_native_pool_sdk")
        self.assertFalse(option["is_comparison_only"])
        self.assertTrue(option["is_clickable"])
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

    def test_direct_route_selection_excludes_phantom_benchmark_routes(self):
        def option(variant_id, provider, surface, output):
            return {
                "variant_id": variant_id,
                "provider": provider,
                "execution_surface_label": surface,
                "supports_current_pair": True,
                "estimated_output_raw": str(output),
                "route_labels": [surface],
                "_sort_out_amount_raw": output,
                "route_shape": "single-pool",
                "route_step_count": 1,
            }

        phantom = option("phantom_quote", "phantom-routing-api", "Phantom", 999)
        phantom["route_shape"] = "wallet-routing"
        phantom["is_comparison_only"] = True
        phantom["is_clickable"] = False
        orca = option("orca_whirlpool_quote", "orca-whirlpool", "Orca", 800)
        orca["is_comparison_only"] = False
        orca["is_clickable"] = True

        selected = _select_direct_route_option([phantom, orca])

        self.assertEqual(selected["provider"], "orca-whirlpool")
        self.assertNotEqual(selected["provider"], "phantom-routing-api")

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
        self.assertFalse(meteora_option["is_comparison_only"])
        self.assertTrue(meteora_option["is_clickable"])
        self.assertEqual(meteora_option["execution_status"], "executable_capable")
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
        meteora_option = next(opt for opt in visible if opt and opt["provider"] == "meteora-dlmm")
        self.assertFalse(meteora_option["is_comparison_only"])
        self.assertTrue(meteora_option["is_clickable"])
        self.assertEqual(meteora_option["execution_status"], "executable_capable")
        self.assertIsNotNone(meteora_option["estimated_output_usd"])
        phantom_option = next(opt for opt in visible if opt and opt["provider"] == "phantom-routing-api")
        self.assertTrue(phantom_option["is_comparison_only"])
        self.assertFalse(phantom_option["is_clickable"])
        self.assertEqual(phantom_option["execution_status"], "quote_only")
        self.assertIsNotNone(phantom_option["estimated_output_usd"])
        orca_option = next(opt for opt in visible if opt and opt["provider"] == "orca-whirlpool")
        self.assertFalse(orca_option["is_comparison_only"])
        self.assertTrue(orca_option["is_clickable"])
        self.assertEqual(orca_option["execution_status"], "executable_capable")
        self.assertIsNotNone(orca_option["estimated_output_usd"])

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

        meteora_option = next(opt for opt in visible if opt and opt["provider"] == "meteora-dlmm")
        self.assertEqual(meteora_option["quote_status"], "live")
        self.assertEqual(meteora_option["execution_status"], "executable_capable")
        self.assertFalse(meteora_option["is_comparison_only"])
        self.assertTrue(meteora_option["is_clickable"])
        self.assertIsNotNone(meteora_option["estimated_output_usd"])
        phantom_option = next(opt for opt in visible if opt and opt["provider"] == "phantom-routing-api")
        self.assertEqual(phantom_option["quote_status"], "live")
        self.assertEqual(phantom_option["execution_status"], "quote_only")
        self.assertTrue(phantom_option["is_comparison_only"])
        self.assertFalse(phantom_option["is_clickable"])
        self.assertIsNotNone(phantom_option["estimated_output_usd"])
        orca_option = next(opt for opt in visible if opt and opt["provider"] == "orca-whirlpool")
        self.assertEqual(orca_option["quote_status"], "live")
        self.assertEqual(orca_option["execution_status"], "executable_capable")
        self.assertFalse(orca_option["is_comparison_only"])
        self.assertTrue(orca_option["is_clickable"])
        self.assertIsNotNone(orca_option["estimated_output_usd"])

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
            self.assertEqual(meteora_option["execution_status"], "executable_capable")
            self.assertFalse(meteora_option["is_comparison_only"])
            self.assertTrue(meteora_option["is_clickable"])
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
            self.assertEqual(orca_option["execution_status"], "executable_capable")
            self.assertFalse(orca_option["is_comparison_only"])
            self.assertTrue(orca_option["is_clickable"])
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
        self.assertFalse(response["recommended_option"]["is_comparison_only"])
        self.assertTrue(response["recommended_option"]["is_clickable"])
        self.assertEqual(response["recommended_option"]["execution_status"], "executable_capable")
        self.assertTrue(response["recommended_option"]["execution_readiness"]["execution_ready"])
        self.assertAlmostEqual(response["recommended_option"]["estimated_output"], 45.0)
        self.assertAlmostEqual(response["recommended_option"]["estimated_output_usd"], 0.00081)
        self.assertEqual(response["recommended_executable_option"]["provider"], "pumpswap")
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
        self.assertFalse(response["recommended_option"]["is_comparison_only"])
        self.assertTrue(response["recommended_option"]["is_clickable"])
        self.assertEqual(response["recommended_option"]["execution_status"], "executable_capable")
        self.assertEqual(response["recommended_executable_option"]["provider"], "meteora-dlmm")
        self.assertEqual(
            response["recommended_executable_option"]["execution_status"],
            "executable_capable",
        )
        self.assertEqual(response["summary"]["recommended_variant_id"], "meteora_dlmm_quote")
        self.assertEqual(
            response["summary"]["recommended_executable_variant_id"],
            "meteora_dlmm_quote",
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
        self.assertIn("jupiter-metis", other_providers)
        self.assertIn("raydium-trade-api", other_providers)
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
        self.assertFalse(response["recommended_option"]["is_comparison_only"])
        self.assertTrue(response["recommended_option"]["is_clickable"])
        self.assertEqual(response["recommended_option"]["execution_status"], "executable_capable")
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
        self.assertEqual(phantom_option["label"], "Benchmark-only quote")
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
        self.assertFalse(response["direct_route_check"]["is_comparison_only"])
        self.assertTrue(response["direct_route_check"]["is_clickable"])
        self.assertEqual(response["direct_route_check"]["execution_status"], "executable_capable")
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

    def test_swap_quote_keeps_phantom_benchmark_only_when_it_has_best_output(self):
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

        self.assertEqual(response["best_quote_option"]["provider"], "phantom-routing-api")
        self.assertEqual(response["best_quote_option"]["variant_id"], "phantom_quote")
        self.assertEqual(response["best_benchmark_quote_option"]["provider"], "phantom-routing-api")
        self.assertEqual(response["recommended_option"]["provider"], "jupiter-metis")
        self.assertEqual(response["recommended_option"]["variant_id"], "recommended_default")
        self.assertNotEqual(response["recommended_option"]["provider"], "phantom-routing-api")
        self.assertFalse(response["recommended_option"]["is_comparison_only"])
        self.assertTrue(response["recommended_option"]["is_clickable"])
        self.assertEqual(response["recommended_option"]["execution_status"], "executable_capable")
        self.assertEqual(response["summary"]["recommended_variant_id"], "recommended_default")
        self.assertTrue(response["summary"]["recommended_is_executable"])
        self.assertEqual(response["summary"]["best_benchmark_variant_id"], "phantom_quote")
        self.assertEqual(response["recommended_executable_option"]["provider"], "jupiter-metis")
        self.assertNotEqual(response["recommended_executable_option"]["provider"], "phantom-routing-api")
        self.assertTrue(response["recommended_executable_option"]["is_clickable"])
        self.assertNotEqual(response["direct_route_check"]["provider"], "phantom-routing-api")
        phantom_option = next(
            opt for opt in response["other_options"] if opt["provider"] == "phantom-routing-api"
        )
        self.assertEqual(phantom_option["label"], "Benchmark-only quote")
        self.assertTrue(phantom_option["is_comparison_only"])
        self.assertFalse(phantom_option["is_clickable"])
        self.assertEqual(phantom_option["execution_status"], "quote_only")
        self.assertEqual(phantom_option["estimated_output_raw"], "90000000")
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
        result = swap_execute_prepare(self._base_swap_execute_prepare_payload(provider="unknown-provider"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_PROVIDER_NOT_IMPLEMENTED")

    def test_swap_execute_prepare_rejects_pumpswap_unsupported_variant_safely(self):
        result = swap_execute_prepare(self._base_swap_execute_prepare_payload(provider="PumpSwap"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_UNSUPPORTED_ROUTE")

    def test_get_swap_execution_provider_returns_jupiter_provider(self):
        provider = get_swap_execution_provider("jupiter-metis")

        self.assertIsNotNone(provider)
        self.assertEqual(provider["provider"], "jupiter-metis")
        self.assertEqual(provider["execution_surface_label"], "Jupiter")
        self.assertTrue(callable(provider["prepare"]))

    def test_prepare_swap_transaction_with_provider_blocks_unimplemented_provider(self):
        result = prepare_swap_transaction_with_provider(
            provider_id="unknown-provider",
            input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            output_meta={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
            amount=1.0,
            amount_raw=1000000000,
            slippage_bps=50,
            variant_id="recommended_default",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            from_token_query="SOL",
            to_token_query="USDC",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_PROVIDER_NOT_IMPLEMENTED")

    def test_get_swap_execution_provider_returns_orca_provider_with_capability_enabled(self):
        provider = get_swap_execution_provider("orca-whirlpool")

        self.assertIsNotNone(provider)
        self.assertEqual(provider["provider"], "orca-whirlpool")
        self.assertEqual(provider["execution_surface_label"], "Orca")
        self.assertTrue(callable(provider["prepare"]))
        self.assertTrue(SWAP_EXECUTION_PROVIDER_CAPABILITIES["orca-whirlpool"]["prepare"])
        self.assertTrue(SWAP_EXECUTION_PROVIDER_CAPABILITIES["orca-whirlpool"]["submit"])

    def test_get_swap_execution_provider_returns_raydium_provider_with_capability_enabled(self):
        provider = get_swap_execution_provider("raydium-trade-api")

        self.assertIsNotNone(provider)
        self.assertEqual(provider["provider"], "raydium-trade-api")
        self.assertEqual(provider["execution_surface_label"], "Raydium")
        self.assertTrue(callable(provider["prepare"]))
        self.assertTrue(SWAP_EXECUTION_PROVIDER_CAPABILITIES["raydium-trade-api"]["prepare"])
        self.assertTrue(SWAP_EXECUTION_PROVIDER_CAPABILITIES["raydium-trade-api"]["submit"])

    def test_get_swap_execution_provider_returns_pumpswap_provider_with_capability_enabled(self):
        provider = get_swap_execution_provider("pumpswap")

        self.assertIsNotNone(provider)
        self.assertEqual(provider["provider"], "pumpswap")
        self.assertEqual(provider["execution_surface_label"], "PumpSwap")
        self.assertTrue(callable(provider["prepare"]))
        self.assertTrue(SWAP_EXECUTION_PROVIDER_CAPABILITIES["pumpswap"]["prepare"])
        self.assertTrue(SWAP_EXECUTION_PROVIDER_CAPABILITIES["pumpswap"]["submit"])
        self.assertEqual(SWAP_EXECUTION_PROVIDER_CAPABILITIES["pumpswap"]["status"], "executable_v1")

    def test_swap_execute_prepare_accepts_jupiter_provider_alias(self):
        quote = self._mock_jupiter_execution_quote()
        with (
            patch.dict(os.environ, {}, clear=True),
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
            patch.dict(os.environ, {}, clear=True),
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
        self.assertEqual(
            result["submit_preflight"],
            {
                "can_submit": False,
                "network": "solana",
                "required_config": "SWAP_SUBMIT_RPC_URL",
                "configured_source": None,
            },
        )

    def test_swap_execute_prepare_marks_submit_preflight_configured_without_leaking_url(self):
        quote = self._mock_jupiter_execution_quote()
        with (
            patch.dict(os.environ, {"SWAP_SUBMIT_RPC_URL": "https://rpc.example?api-key=SECRET"}, clear=True),
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

        encoded = json.dumps(result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["submit_preflight"]["can_submit"])
        self.assertEqual(result["submit_preflight"]["configured_source"], "SWAP_SUBMIT_RPC_URL")
        self.assertNotIn("rpc.example", encoded)
        self.assertNotIn("api-key", encoded)
        self.assertNotIn("SECRET", encoded)

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

    def _fake_urlopen_response(self, payload):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        return FakeResponse()

    def _mock_raydium_execution_quote(self):
        return {
            "success": True,
            "data": {
                "outputAmount": "85000000",
                "otherAmountThreshold": "84575000",
                "slippageBps": 50,
            },
        }

    def test_fetch_raydium_swap_transaction_maps_http_errors(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "https://transaction-v1.raydium.io/transaction/swap-base-in",
                429,
                "Too Many Requests",
                {},
                io.BytesIO(b"too many requests"),
            ),
        ):
            limited = _fetch_raydium_swap_transaction(
                swap_response={"success": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "https://transaction-v1.raydium.io/transaction/swap-base-in",
                403,
                "Forbidden",
                {},
                io.BytesIO(b"forbidden"),
            ),
        ):
            forbidden = _fetch_raydium_swap_transaction(
                swap_response={"success": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "https://transaction-v1.raydium.io/transaction/swap-base-in",
                500,
                "Server Error",
                {},
                io.BytesIO(b"error"),
            ),
        ):
            failed = _fetch_raydium_swap_transaction(
                swap_response={"success": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(limited["error"]["code"], "SWAP_EXECUTION_RAYDIUM_RATE_LIMITED")
        self.assertEqual(forbidden["error"]["code"], "SWAP_EXECUTION_RAYDIUM_FORBIDDEN")
        self.assertEqual(failed["error"]["code"], "SWAP_EXECUTION_RAYDIUM_PREPARE_FAILED")

    def test_fetch_raydium_swap_transaction_success_false_returns_safe_provider_message(self):
        with patch(
            "urllib.request.urlopen",
            return_value=self._fake_urlopen_response({
                "success": False,
                "msg": "insufficient liquidity for requested amount",
                "code": "LIQUIDITY_LOW",
            }),
        ):
            result = _fetch_raydium_swap_transaction(
                swap_response={"success": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_RAYDIUM_PREPARE_FAILED")
        self.assertEqual(result["error"]["provider_message"], "insufficient liquidity for requested amount")
        self.assertEqual(result["error"]["provider_code"], "LIQUIDITY_LOW")

    def test_fetch_raydium_swap_transaction_success_false_does_not_leak_payloads_or_urls(self):
        with patch(
            "urllib.request.urlopen",
            return_value=self._fake_urlopen_response({
                "success": False,
                "message": "see https://raydium.example?api-key=SECRET",
                "code": "PREPARE_FAILED",
                "data": {
                    "transaction_base64": "raydium-secret-transaction",
                    "url": "https://raydium.example?api-key=SECRET",
                },
                "error": {
                    "message": "fallback https://raydium.example?api-key=SECRET",
                    "data": {"transaction": "raydium-secret-transaction"},
                },
            }),
        ):
            result = _fetch_raydium_swap_transaction(
                swap_response={"success": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        encoded = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_RAYDIUM_PREPARE_FAILED")
        self.assertNotIn("raydium-secret-transaction", encoded)
        self.assertNotIn("transaction_base64", encoded)
        self.assertNotIn("api-key", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("raydium.example", encoded)

    def test_fetch_raydium_swap_transaction_success_false_does_not_leak_transaction_markers(self):
        cases = [
            ("msg", "transaction_base64=SECRET_TX"),
            ("message", "swapTransaction=SECRET_TX"),
            ("msg", "signed_transaction=SECRET_TX"),
        ]

        for key, provider_text in cases:
            with self.subTest(key=key, provider_text=provider_text):
                with patch(
                    "urllib.request.urlopen",
                    return_value=self._fake_urlopen_response({
                        "success": False,
                        key: provider_text,
                        "code": "PREPARE_FAILED",
                        "data": {
                            "transaction_base64": "SECRET_TX",
                            "swapTransaction": "SECRET_TX",
                            "signed_transaction": "SECRET_TX",
                        },
                    }),
                ):
                    result = _fetch_raydium_swap_transaction(
                        swap_response={"success": True},
                        user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                    )

                encoded = json.dumps(result)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_RAYDIUM_PREPARE_FAILED")
                self.assertNotIn("provider_message", result["error"])
                self.assertNotIn("SECRET_TX", encoded)
                self.assertNotIn("transaction_base64", encoded)
                self.assertNotIn("swapTransaction", encoded)
                self.assertNotIn("signed_transaction", encoded)

    def test_fetch_raydium_swap_transaction_rejects_missing_or_multiple_transactions(self):
        with patch(
            "urllib.request.urlopen",
            return_value=self._fake_urlopen_response({"success": True, "data": []}),
        ):
            missing = _fetch_raydium_swap_transaction(
                swap_response={"success": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with patch(
            "urllib.request.urlopen",
            return_value=self._fake_urlopen_response({
                "success": True,
                "data": [{"transaction": "tx1"}, {"transaction": "tx2"}],
            }),
        ):
            multiple = _fetch_raydium_swap_transaction(
                swap_response={"success": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(missing["error"]["code"], "SWAP_EXECUTION_RAYDIUM_TRANSACTION_MISSING")
        self.assertEqual(
            multiple["error"]["code"],
            "SWAP_EXECUTION_RAYDIUM_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
        )

    def test_fetch_raydium_swap_transaction_returns_single_transaction_and_payload(self):
        captured = {}

        def fake_urlopen(req, timeout=20):
            captured["url"] = req.full_url
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return self._fake_urlopen_response({
                "success": True,
                "data": [{"transaction": "raydium-base64tx"}],
            })

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = _fetch_raydium_swap_transaction(
                swap_response={"success": True, "data": {"outputAmount": "1"}},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                tx_version="V0",
                wrap_sol=True,
                unwrap_sol=False,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["transaction_base64"], "raydium-base64tx")
        self.assertEqual(captured["url"], "https://transaction-v1.raydium.io/transaction/swap-base-in")
        self.assertEqual(captured["payload"]["wallet"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertEqual(captured["payload"]["txVersion"], "V0")
        self.assertTrue(captured["payload"]["wrapSol"])
        self.assertFalse(captured["payload"]["unwrapSol"])
        self.assertEqual(captured["payload"]["computeUnitPriceMicroLamports"], "10000")
        self.assertIn("swapResponse", captured["payload"])

    def test_raydium_prepare_token_accounts_derive_usdc_input_for_usdc_to_sol(self):
        self.assertEqual(
            _derive_solana_associated_token_account(
                owner="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                mint=METEORA_DLMM_USDC_MINT,
            ),
            "GwWhFWPZm8hxqksYzRv5FYoZsVGYgTuYS6uRkodqEDcV",
        )
        accounts = _raydium_prepare_token_accounts(
            input_mint=METEORA_DLMM_USDC_MINT,
            output_mint=METEORA_DLMM_SOL_MINT,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertFalse(accounts["wrap_sol"])
        self.assertTrue(accounts["unwrap_sol"])
        self.assertEqual(
            accounts["input_account"],
            "GwWhFWPZm8hxqksYzRv5FYoZsVGYgTuYS6uRkodqEDcV",
        )
        self.assertIsNone(accounts["output_account"])

    def test_raydium_prepare_token_accounts_derive_usdc_output_for_sol_to_usdc(self):
        accounts = _raydium_prepare_token_accounts(
            input_mint=METEORA_DLMM_SOL_MINT,
            output_mint=METEORA_DLMM_USDC_MINT,
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
        )

        self.assertTrue(accounts["wrap_sol"])
        self.assertFalse(accounts["unwrap_sol"])
        self.assertIsNone(accounts["input_account"])
        self.assertEqual(
            accounts["output_account"],
            "GwWhFWPZm8hxqksYzRv5FYoZsVGYgTuYS6uRkodqEDcV",
        )

    def test_raydium_fetch_swap_transaction_sends_input_and_output_accounts_when_provided(self):
        captured = {}

        def fake_urlopen(req, timeout=20):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return self._fake_urlopen_response({
                "success": True,
                "data": [{"transaction": "raydium-base64tx"}],
            })

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = _fetch_raydium_swap_transaction(
                swap_response={"success": True, "data": {"outputAmount": "1"}},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                wrap_sol=False,
                unwrap_sol=True,
                input_account="inputAta",
                output_account=None,
            )

        self.assertTrue(result["ok"])
        self.assertFalse(captured["payload"]["wrapSol"])
        self.assertTrue(captured["payload"]["unwrapSol"])
        self.assertEqual(captured["payload"]["inputAccount"], "inputAta")
        self.assertNotIn("outputAccount", captured["payload"])

    def test_fetch_raydium_swap_transaction_allows_compute_unit_price_override(self):
        captured = {}

        def fake_urlopen(req, timeout=20):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return self._fake_urlopen_response({
                "success": True,
                "data": [{"transaction": "raydium-base64tx"}],
            })

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = _fetch_raydium_swap_transaction(
                swap_response={"success": True, "data": {"outputAmount": "1"}},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                compute_unit_price_micro_lamports="25000",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(captured["payload"]["computeUnitPriceMicroLamports"], "25000")

    def test_raydium_prepare_rebuilds_quote_and_returns_normalized_response(self):
        quote = self._mock_raydium_execution_quote()
        with (
            patch("api.main._fetch_raydium_quote", return_value=quote) as fetch_quote,
            patch(
                "api.main._fetch_raydium_swap_transaction",
                return_value={
                    "ok": True,
                    "transaction_base64": "raydium-base64tx",
                    "raw": {"data": [{"transaction": "raydium-base64tx"}]},
                },
            ) as fetch_swap,
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(
                    provider="raydium-trade-api",
                    variant_id="raydium_quote",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "raydium-trade-api")
        self.assertEqual(result["execution_surface_label"], "Raydium")
        self.assertEqual(result["execution_status"], "prepared")
        self.assertEqual(result["transaction_base64"], "raydium-base64tx")
        self.assertEqual(result["transaction_format"], "versioned")
        self.assertEqual(result["quote_summary"]["estimated_output_raw"], "85000000")
        self.assertEqual(result["quote_summary"]["variant_id"], "raydium_quote")
        self.assertIn("quote_refreshed_before_execution", result["warnings"])
        fetch_quote.assert_called_once()
        self.assertEqual(fetch_quote.call_args.args[0]["txVersion"], "V0")
        fetch_swap.assert_called_once()
        self.assertEqual(fetch_swap.call_args.kwargs["user_public_key"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertEqual(fetch_swap.call_args.kwargs["tx_version"], "V0")
        self.assertTrue(fetch_swap.call_args.kwargs["wrap_sol"])
        self.assertFalse(fetch_swap.call_args.kwargs["unwrap_sol"])
        self.assertIsNone(fetch_swap.call_args.kwargs["input_account"])
        self.assertEqual(
            fetch_swap.call_args.kwargs["output_account"],
            "GwWhFWPZm8hxqksYzRv5FYoZsVGYgTuYS6uRkodqEDcV",
        )

    def test_raydium_prepare_usdc_to_sol_passes_input_ata_and_unwraps_sol(self):
        quote = self._mock_raydium_execution_quote()
        with (
            patch("api.main._fetch_raydium_quote", return_value=quote),
            patch(
                "api.main._fetch_raydium_swap_transaction",
                return_value={
                    "ok": True,
                    "transaction_base64": "raydium-base64tx",
                    "raw": {"data": [{"transaction": "raydium-base64tx"}]},
                },
            ) as fetch_swap,
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(
                    provider="raydium-trade-api",
                    variant_id="raydium_quote",
                    from_token="USDC",
                    to_token="SOL",
                    amount=1.0,
                )
            )

        self.assertTrue(result["ok"])
        self.assertFalse(fetch_swap.call_args.kwargs["wrap_sol"])
        self.assertTrue(fetch_swap.call_args.kwargs["unwrap_sol"])
        self.assertEqual(
            fetch_swap.call_args.kwargs["input_account"],
            "GwWhFWPZm8hxqksYzRv5FYoZsVGYgTuYS6uRkodqEDcV",
        )
        self.assertIsNone(fetch_swap.call_args.kwargs["output_account"])

    def test_raydium_prepare_rejects_non_raydium_variant(self):
        result = prepare_swap_transaction_with_provider(
            provider_id="raydium-trade-api",
            input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            output_meta={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
            amount=1.0,
            amount_raw=1000000000,
            slippage_bps=50,
            variant_id="recommended_default",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            from_token_query="SOL",
            to_token_query="USDC",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_UNSUPPORTED_ROUTE")

    def test_raydium_prepare_does_not_mutate_token_meta(self):
        before = json.dumps(TOKEN_META, sort_keys=True)
        quote = self._mock_raydium_execution_quote()
        with (
            patch("api.main._fetch_raydium_quote", return_value=quote),
            patch(
                "api.main._fetch_raydium_swap_transaction",
                return_value={
                    "ok": True,
                    "transaction_base64": "raydium-base64tx",
                    "raw": {"data": [{"transaction": "raydium-base64tx"}]},
                },
            ),
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(
                    provider="raydium-trade-api",
                    variant_id="raydium_quote",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

    def test_swap_execute_submit_rejects_missing_signed_transaction(self):
        result = swap_execute_submit({"network": "solana", "signed_transaction_base64": ""})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_SUBMIT_SIGNED_TRANSACTION_REQUIRED")

    def test_swap_execute_submit_rejects_unsupported_network(self):
        result = swap_execute_submit({"network": "ethereum", "signed_transaction_base64": "AQID"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_SUBMIT_UNSUPPORTED_NETWORK")

    def test_swap_execute_submit_requires_configured_rpc(self):
        with patch.dict(os.environ, {}, clear=True):
            result = swap_execute_submit({"network": "solana", "signed_transaction_base64": "AQID"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_SUBMIT_RPC_CONFIG_MISSING")

    def test_swap_execute_submit_returns_signature_on_mocked_success(self):
        with (
            patch.dict(os.environ, {"SWAP_SUBMIT_RPC_URL": "https://rpc.example?api-key=secret"}, clear=True),
            patch(
                "api.main._fetch_solana_send_transaction",
                return_value={"ok": True, "signature": "signature123", "status": "submitted"},
            ) as submit,
        ):
            result = swap_execute_submit({
                "network": "solana",
                "signed_transaction_base64": "AQID",
                "skip_preflight": False,
                "preflight_commitment": "confirmed",
            })

        self.assertTrue(result["ok"])
        self.assertEqual(result["signature"], "signature123")
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["rpc"]["source"], "SWAP_SUBMIT_RPC_URL")
        self.assertNotIn("rpc.example", json.dumps(result))
        self.assertNotIn("AQID", json.dumps(result))
        submit.assert_called_once()
        self.assertEqual(submit.call_args.kwargs["signed_transaction_base64"], "AQID")

    def test_swap_execute_submit_does_not_mutate_token_meta(self):
        before = json.dumps(TOKEN_META, sort_keys=True)
        with (
            patch.dict(os.environ, {"SOLANA_RPC_URL": "https://rpc.example"}, clear=True),
            patch(
                "api.main._fetch_solana_send_transaction",
                return_value={"ok": True, "signature": "signature123", "status": "submitted"},
            ),
        ):
            result = swap_execute_submit({"network": "solana", "signed_transaction_base64": "AQID"})

        self.assertTrue(result["ok"])
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

    def test_fetch_solana_signature_status_maps_confirmed_status(self):
        class Response:
            status_code = 200
            ok = True

            def json(self):
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "value": [{
                            "confirmationStatus": "confirmed",
                            "confirmations": 3,
                            "err": None,
                        }]
                    },
                }

        with patch("api.main.requests.post", return_value=Response()) as post:
            result = _fetch_solana_signature_status(signature="sig123", rpc_url="https://rpc.example")

        self.assertTrue(result["ok"])
        self.assertEqual(result["signature"], "sig123")
        self.assertEqual(result["confirmation_status"], "confirmed")
        self.assertTrue(result["confirmed"])
        self.assertFalse(result["finalized"])
        self.assertIsNone(result["err"])
        self.assertEqual(post.call_args.kwargs["json"]["method"], "getSignatureStatuses")
        self.assertTrue(post.call_args.kwargs["json"]["params"][1]["searchTransactionHistory"])

    def test_fetch_solana_signature_status_maps_failed_status(self):
        class Response:
            status_code = 200
            ok = True

            def json(self):
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "value": [{
                            "confirmationStatus": "processed",
                            "confirmations": 0,
                            "err": {"InstructionError": [0, "Custom"]},
                        }]
                    },
                }

        with patch("api.main.requests.post", return_value=Response()):
            result = _fetch_solana_signature_status(signature="sig123", rpc_url="https://rpc.example")

        self.assertTrue(result["ok"])
        self.assertFalse(result["confirmed"])
        self.assertFalse(result["finalized"])
        self.assertEqual(result["err"], {"InstructionError": [0, "Custom"]})

    def test_swap_transaction_status_requires_configured_rpc(self):
        with patch.dict(os.environ, {}, clear=True):
            result = swap_transaction_status("sig123")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_STATUS_RPC_CONFIG_MISSING")

    def test_swap_transaction_status_returns_safe_confirmed_status(self):
        with (
            patch.dict(os.environ, {"SWAP_SUBMIT_RPC_URL": "https://rpc.example?api-key=secret"}, clear=True),
            patch(
                "api.main._fetch_solana_signature_status",
                return_value={
                    "ok": True,
                    "signature": "sig123",
                    "confirmation_status": "finalized",
                    "confirmations": None,
                    "confirmed": True,
                    "finalized": True,
                    "err": None,
                },
            ) as status,
        ):
            result = swap_transaction_status("sig123")

        self.assertTrue(result["ok"])
        self.assertEqual(result["signature"], "sig123")
        self.assertEqual(result["confirmation_status"], "finalized")
        self.assertTrue(result["confirmed"])
        self.assertTrue(result["finalized"])
        self.assertIsNone(result["err"])
        self.assertEqual(result["rpc"]["source"], "SWAP_SUBMIT_RPC_URL")
        self.assertNotIn("rpc.example", json.dumps(result))
        status.assert_called_once_with(signature="sig123", rpc_url="https://rpc.example?api-key=secret")

    def test_fetch_solana_send_transaction_maps_http_errors(self):
        class Response:
            def __init__(self, status_code, text=""):
                self.status_code = status_code
                self.text = text
                self.ok = status_code < 400

            def json(self):
                return {}

        with patch("api.main.requests.post", return_value=Response(403, "Access forbidden")):
            forbidden = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example",
            )
        with patch("api.main.requests.post", return_value=Response(429, "Too many requests")):
            limited = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example",
            )

        self.assertEqual(forbidden["error"]["code"], "SWAP_SUBMIT_FORBIDDEN")
        self.assertEqual(limited["error"]["code"], "SWAP_SUBMIT_RATE_LIMITED")

    def test_fetch_solana_send_transaction_redacts_generic_http_error_body(self):
        class Response:
            status_code = 500
            ok = False
            text = "upstream failed for https://rpc.example?api-key=SECRET"

            def json(self):
                return {}

        with patch("api.main.requests.post", return_value=Response()):
            result = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example?api-key=SECRET",
            )

        result_json = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_SUBMIT_FAILED")
        self.assertEqual(result["error"]["status_code"], 500)
        self.assertNotIn("SECRET", result_json)
        self.assertNotIn("api-key", result_json)
        self.assertNotIn("rpc.example", result_json)
        self.assertEqual(result["error"]["detail"], "RPC returned an HTTP error.")

    def test_fetch_solana_send_transaction_maps_rpc_errors_and_success(self):
        class Response:
            status_code = 200
            ok = True
            text = ""

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

        with patch("api.main.requests.post", return_value=Response({"error": {"code": 403, "message": "Access forbidden"}})):
            forbidden = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example",
            )
        with patch("api.main.requests.post", return_value=Response({"error": {"code": -32005, "message": "Too many requests"}})):
            limited = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example",
            )
        with patch("api.main.requests.post", return_value=Response({"error": {"code": -32000, "message": "simulation failed"}})):
            failed = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example",
            )
        with patch("api.main.requests.post", return_value=Response({"result": "signature123"})):
            success = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example",
            )

        self.assertEqual(forbidden["error"]["code"], "SWAP_SUBMIT_FORBIDDEN")
        self.assertEqual(limited["error"]["code"], "SWAP_SUBMIT_RATE_LIMITED")
        self.assertEqual(failed["error"]["code"], "SWAP_SUBMIT_FAILED")
        self.assertTrue(success["ok"])
        self.assertEqual(success["signature"], "signature123")

    def test_fetch_solana_send_transaction_sanitizes_rpc_error_payloads(self):
        class Response:
            status_code = 200
            ok = True
            text = ""

            def json(self):
                return {
                    "error": {
                        "code": -32000,
                        "message": "simulation failed",
                        "signed_transaction_base64": "AQID",
                        "params": ["AQID"],
                        "data": {
                            "transaction": "AQID",
                            "url": "https://rpc.example?api-key=SECRET",
                        },
                    }
                }

        with patch("api.main.requests.post", return_value=Response()):
            result = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example?api-key=SECRET",
            )

        result_json = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_SUBMIT_FAILED")
        self.assertEqual(result["error"]["rpc_error"]["code"], -32000)
        self.assertEqual(result["error"]["rpc_error"]["message"], "simulation failed")
        self.assertNotIn("AQID", result_json)
        self.assertNotIn("signed_transaction_base64", result_json)
        self.assertNotIn("api-key", result_json)
        self.assertNotIn("SECRET", result_json)
        self.assertNotIn("rpc.example", result_json)
        self.assertNotIn("transaction", result_json)
        self.assertNotIn("params", result_json)
        self.assertNotIn("data", result_json)

    def test_fetch_solana_send_transaction_sanitizes_rate_limit_and_forbidden_rpc_errors(self):
        class Response:
            status_code = 200
            ok = True
            text = ""

            def __init__(self, error):
                self.error = error

            def json(self):
                return {"error": self.error}

        leaked_error = {
            "code": -32005,
            "message": "Too many requests",
            "data": {"transaction": "AQID", "url": "https://rpc.example?api-key=SECRET"},
            "params": ["AQID"],
        }
        forbidden_error = {
            "code": 403,
            "message": "Access forbidden",
            "data": {"signed_transaction_base64": "AQID"},
        }

        with patch("api.main.requests.post", return_value=Response(leaked_error)):
            limited = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example?api-key=SECRET",
            )
        with patch("api.main.requests.post", return_value=Response(forbidden_error)):
            forbidden = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url="https://rpc.example?api-key=SECRET",
            )

        limited_json = json.dumps(limited)
        forbidden_json = json.dumps(forbidden)
        self.assertEqual(limited["error"]["code"], "SWAP_SUBMIT_RATE_LIMITED")
        self.assertEqual(forbidden["error"]["code"], "SWAP_SUBMIT_FORBIDDEN")
        for payload in (limited_json, forbidden_json):
            self.assertNotIn("AQID", payload)
            self.assertNotIn("signed_transaction_base64", payload)
            self.assertNotIn("api-key", payload)
            self.assertNotIn("SECRET", payload)
            self.assertNotIn("rpc.example", payload)
            self.assertNotIn("transaction", payload)
            self.assertNotIn("params", payload)
            self.assertNotIn("data", payload)

    def test_fetch_solana_send_transaction_redacts_request_exception_secrets(self):
        secret_url = "https://example-rpc.com/?api-key=SECRET&token=ALSOSECRET"
        exc = requests.RequestException(f"Connection failed for {secret_url}")

        with patch("api.main.requests.post", side_effect=exc):
            result = _fetch_solana_send_transaction(
                signed_transaction_base64="AQID",
                rpc_url=secret_url,
            )

        result_json = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_SUBMIT_FAILED")
        self.assertNotIn("SECRET", result_json)
        self.assertNotIn("ALSOSECRET", result_json)

    def test_swap_execute_preflight_requires_transaction_and_rpc_without_leaking_url(self):
        missing = swap_execute_preflight({"network": "solana", "transaction_base64": ""})
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["error_category"], "unsupported")
        self.assertNotIn("transaction_base64", json.dumps(missing))

        with patch.dict(os.environ, {}, clear=True):
            result = swap_execute_preflight({
                "network": "solana",
                "provider": "orca-whirlpool",
                "variant_id": "orca_whirlpool_quote",
                "transaction_base64": "AQID",
            })

        result_json = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertFalse(result["simulation_supported"])
        self.assertEqual(result["error_category"], "rpc_unavailable")
        self.assertNotIn("AQID", result_json)
        self.assertNotIn("transaction_base64", result_json)
        self.assertNotIn("api-key", result_json)

    def test_decode_solana_transaction_diagnostics_exposes_safe_preflight_metadata(self):
        payer = "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL"
        transaction_base64 = _test_versioned_swap_transaction_base64(payer=payer)

        diagnostics = _decode_solana_transaction_diagnostics(
            transaction_base64,
            expected_user_public_key=payer,
        )

        self.assertTrue(diagnostics["decode_ok"])
        self.assertEqual(diagnostics["transaction_version"], "v0")
        self.assertEqual(diagnostics["fee_payer"], payer)
        self.assertTrue(diagnostics["fee_payer_matches_expected_user"])
        self.assertTrue(diagnostics["expected_user_account_present"])
        self.assertEqual(diagnostics["ata_create_count"], 1)
        self.assertEqual(len(diagnostics["ata_create_details"]), 1)
        self.assertEqual(diagnostics["ata_create_details"][0]["instruction_index"], 0)
        self.assertEqual(diagnostics["ata_create_details"][0]["payer"], payer)
        self.assertEqual(diagnostics["ata_create_details"][0]["ata_account"], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.assertEqual(diagnostics["ata_create_details"][0]["owner"], payer)
        self.assertEqual(diagnostics["ata_create_details"][0]["mint"], "So11111111111111111111111111111111111111112")
        self.assertEqual(diagnostics["ata_create_details"][0]["account_indexes"], [0, 5, 0, 4, 3, 2])
        self.assertEqual(diagnostics["token_program_instruction_count"], 1)
        self.assertEqual(diagnostics["system_program_instruction_count"], 1)
        self.assertTrue(diagnostics["uses_associated_token_program"])
        self.assertTrue(diagnostics["uses_token_program"])
        self.assertTrue(diagnostics["uses_wrapped_sol_mint"])
        self.assertEqual(diagnostics["wsol_ata_account"], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.assertFalse(diagnostics["has_system_transfer_to_wsol_account"])
        self.assertFalse(diagnostics["has_token_sync_native"])
        self.assertFalse(diagnostics["native_sol_wrap_complete"])
        self.assertFalse(diagnostics["loaded_address_resolution_available"])
        self.assertIn("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL", diagnostics["program_ids"])
        self.assertIn("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", diagnostics["program_ids"])

    def test_decode_solana_transaction_diagnostics_detects_native_sol_wrap(self):
        payer = "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL"
        transaction_base64 = _test_versioned_swap_transaction_base64(
            payer=payer,
            include_native_sol_wrap=True,
            include_close_account=True,
        )

        diagnostics = _decode_solana_transaction_diagnostics(
            transaction_base64,
            expected_user_public_key=payer,
        )

        self.assertTrue(diagnostics["uses_wrapped_sol_mint"])
        self.assertTrue(diagnostics["has_system_transfer_to_wsol_account"])
        self.assertTrue(diagnostics["has_token_sync_native"])
        self.assertTrue(diagnostics["has_token_close_account"])
        self.assertTrue(diagnostics["native_sol_wrap_complete"])
        self.assertEqual(diagnostics["wsol_ata_account"], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.assertEqual(diagnostics["wsol_wrap_lamports_detected"], 18_999_040)
        self.assertEqual(diagnostics["system_transfer_details"][0]["destination"], diagnostics["wsol_ata_account"])
        self.assertEqual(diagnostics["token_sync_native_details"][0]["account"], diagnostics["wsol_ata_account"])
        self.assertEqual(diagnostics["token_close_account_details"][0]["account"], diagnostics["wsol_ata_account"])
        self.assertIn("system_transfer", json.dumps(diagnostics["instruction_details"]))
        self.assertIn("token_sync_native", json.dumps(diagnostics["instruction_details"]))

    def test_swap_execute_preflight_simulates_without_returning_transaction(self):
        payer = "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL"
        transaction_base64 = _test_versioned_swap_transaction_base64(payer=payer)
        with (
            patch.dict(os.environ, {"SWAP_PREPARE_RPC_URL": "https://rpc.example?api-key=SECRET"}, clear=True),
            patch("api.main._fetch_solana_rent_exempt_lamports", return_value={
                "ok": True,
                "lamports": 2039280,
                "source": "rpc_getMinimumBalanceForRentExemption_165",
            }),
            patch("api.main._fetch_solana_simulate_transaction", return_value={
                "ok": True,
                "provider": "orca-whirlpool",
                "variant_id": "orca_whirlpool_quote",
                "simulation_supported": True,
                "error_category": None,
                "message": "Preflight simulation passed.",
                "logs_preview": [],
                "transaction_diagnostics": {"decode_ok": True},
            }) as simulate,
        ):
            result = swap_execute_preflight({
                "network": "solana",
                "provider": "orca-whirlpool",
                "variant_id": "orca_whirlpool_quote",
                "transaction_base64": transaction_base64,
                "user_public_key": payer,
            })

        self.assertTrue(result["ok"])
        self.assertEqual(simulate.call_args.kwargs["transaction_base64"], transaction_base64)
        self.assertEqual(simulate.call_args.kwargs["rpc_url"], "https://rpc.example?api-key=SECRET")
        self.assertEqual(simulate.call_args.kwargs["provider"], "orca-whirlpool")
        self.assertEqual(simulate.call_args.kwargs["transaction_diagnostics"]["fee_payer"], payer)
        self.assertEqual(simulate.call_args.kwargs["setup_cost_estimate"]["setup_cost_estimate_lamports"], 2039280)
        result_json = json.dumps(result)
        self.assertNotIn(transaction_base64, result_json)
        self.assertNotIn("transaction_base64", result_json)
        self.assertNotIn("SECRET", result_json)

    def test_build_swap_setup_cost_estimate_uses_rpc_rent_for_ata_creates(self):
        diagnostics = {
            "ata_create_details": [{
                "instruction_index": 0,
                "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "ata_account": "ata111111111111111111111111111111111111111",
                "owner": "owner11111111111111111111111111111111111111",
                "payer": "payer11111111111111111111111111111111111111",
            }]
        }
        with patch("api.main._fetch_solana_rent_exempt_lamports", return_value={
            "ok": True,
            "lamports": 2_039_280,
            "source": "rpc_getMinimumBalanceForRentExemption_165",
        }) as rent:
            estimate = _build_swap_setup_cost_estimate(diagnostics, "https://rpc.example?api-key=SECRET")

        rent.assert_called_once()
        self.assertEqual(estimate["setup_cost_estimate_lamports"], 2_039_280)
        self.assertEqual(estimate["setup_cost_estimate_sol"], 0.00203928)
        self.assertEqual(estimate["setup_cost_estimate_source"], "rpc_getMinimumBalanceForRentExemption_165")
        self.assertEqual(estimate["setup_cost_components"][0]["kind"], "ata_create")
        self.assertEqual(estimate["setup_cost_components"][0]["mint"], "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        self.assertNotIn("SECRET", json.dumps(estimate))

    def test_build_swap_setup_cost_estimate_labels_fallback_rent(self):
        diagnostics = {"ata_create_details": [{"instruction_index": 0}]}
        with patch("api.main._fetch_solana_rent_exempt_lamports", return_value={
            "ok": False,
            "lamports": 2_039_280,
            "source": "fallback_spl_token_account_rent_exempt_lamports",
        }):
            estimate = _build_swap_setup_cost_estimate(diagnostics, "https://rpc.example?api-key=SECRET")

        self.assertEqual(estimate["setup_cost_estimate_lamports"], 2_039_280)
        self.assertEqual(estimate["setup_cost_estimate_source"], "fallback_spl_token_account_rent_exempt_lamports")
        self.assertEqual(estimate["setup_cost_components"][0]["source"], "fallback_spl_token_account_rent_exempt_lamports")
        self.assertNotIn("SECRET", json.dumps(estimate))

    def test_fetch_solana_simulate_transaction_classifies_insufficient_funds_safely(self):
        class Response:
            status_code = 200
            ok = True
            text = ""

            def json(self):
                return {
                    "result": {
                        "value": {
                            "err": {"InstructionError": [0, "Custom"]},
                            "logs": [
                                "Program log: insufficient funds for rent",
                                "https://rpc.example?api-key=SECRET",
                                "transaction_base64=AQID",
                            ],
                        }
                    }
                }

        with patch("api.main.requests.post", return_value=Response()) as post:
            result = _fetch_solana_simulate_transaction(
                transaction_base64="AQID",
                rpc_url="https://rpc.example?api-key=SECRET",
                provider="orca-whirlpool",
                variant_id="orca_whirlpool_quote",
                transaction_diagnostics={"decode_ok": True, "fee_payer": "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL"},
            )

        request_payload = post.call_args.kwargs["json"]
        self.assertEqual(request_payload["method"], "simulateTransaction")
        self.assertFalse(request_payload["params"][1]["sigVerify"])
        self.assertTrue(request_payload["params"][1]["replaceRecentBlockhash"])
        self.assertEqual(request_payload["params"][1]["encoding"], "base64")

        result_json = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertTrue(result["simulation_supported"])
        self.assertEqual(result["error_category"], "insufficient_funds")
        self.assertEqual(result["provider"], "orca-whirlpool")
        self.assertIn("insufficient funds for rent", result["logs_preview"][0])
        self.assertIn("insufficient funds for rent", result["logs_tail"][0])
        self.assertEqual(result["simulation_error_summary"], "InstructionError[0]: Custom")
        self.assertEqual(result["raw_simulation_error"], {"InstructionError": [0, "Custom"]})
        self.assertEqual(result["failing_instruction_index"], 0)
        self.assertEqual(result["transaction_diagnostics"]["fee_payer"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertNotIn("AQID", result_json)
        self.assertNotIn("transaction_base64", result_json)
        self.assertNotIn("api-key", result_json)
        self.assertNotIn("SECRET", result_json)

    def test_fetch_solana_simulate_transaction_reports_meteora_program_error_after_successful_ata_logs(self):
        class Response:
            status_code = 200
            ok = True
            text = ""

            def json(self):
                return {
                    "result": {
                        "value": {
                            "err": {"InstructionError": [4, {"Custom": 6043}]},
                            "logs": [
                                "Program ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL invoke [1]",
                                "Program log: CreateIdempotent",
                                "Program ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL success",
                                "Program 11111111111111111111111111111111 invoke [1]",
                                "Program 11111111111111111111111111111111 success",
                                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA invoke [1]",
                                "Program TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA success",
                                "Program MeteoraDLMM111111111111111111111111111111 invoke [1]",
                                "Program log: Instruction: Swap2",
                                "Program MeteoraDLMM111111111111111111111111111111 failed: custom program error: 0x179b",
                            ],
                            "unitsConsumed": 123456,
                        }
                    }
                }

        diagnostics = {
            "decode_ok": True,
            "instruction_program_ids": [
                "ComputeBudget111111111111111111111111111111",
                "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
                "11111111111111111111111111111111",
                "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                "MeteoraDLMM111111111111111111111111111111",
            ],
        }
        with patch("api.main.requests.post", return_value=Response()):
            result = _fetch_solana_simulate_transaction(
                transaction_base64="AQID",
                rpc_url="https://rpc.example",
                provider="meteora-dlmm",
                variant_id="meteora_dlmm_quote",
                transaction_diagnostics=diagnostics,
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "meteora_program_error")
        self.assertNotEqual(result["error_category"], "account_setup")
        self.assertEqual(result["simulation_error_summary"], "InstructionError[4]: {'Custom': 6043}")
        self.assertEqual(result["failing_instruction_index"], 4)
        self.assertEqual(result["failing_program_id"], "MeteoraDLMM111111111111111111111111111111")
        self.assertEqual(result["units_consumed"], 123456)
        self.assertIn("failed: custom program error", result["logs_tail"][-1])

    def test_fetch_solana_simulate_transaction_classifies_token_program_error(self):
        class Response:
            status_code = 200
            ok = True
            text = ""

            def json(self):
                return {
                    "result": {
                        "value": {
                            "err": {"InstructionError": [2, "IncorrectProgramId"]},
                            "logs": [
                                "Program log: CreateIdempotent",
                                "Program log: Error: IncorrectProgramId",
                            ],
                        }
                    }
                }

        with patch("api.main.requests.post", return_value=Response()):
            result = _fetch_solana_simulate_transaction(
                transaction_base64="AQID",
                rpc_url="https://rpc.example",
                provider="meteora-dlmm",
                variant_id="meteora_dlmm_quote",
                transaction_diagnostics={"decode_ok": True},
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "token_program_error")
        self.assertEqual(result["simulation_error_summary"], "InstructionError[2]: IncorrectProgramId")

    def test_swap_ui_passes_wallet_to_preflight_and_keeps_diagnostics_out_of_default_copy(self):
        html = build_ui_html()
        self.assertIn('user_public_key: phantomProvider?.publicKey?.toString?.() || phantomPubkey || ""', html)
        self.assertIn("Technical diagnostics available in debug.", html)
        self.assertIn("transaction_diagnostics?.decode_ok", html)
        self.assertNotIn("Program AToken", html)
        self.assertNotIn("Program Tokenkeg", html)

    def test_swap_execute_preflight_response_can_include_account_candidates(self):
        class Response:
            status_code = 200
            ok = True
            text = ""

            def json(self):
                return {
                    "result": {
                        "value": {
                            "err": {
                                "InstructionError": [
                                    0,
                                    "Attempt to debit an account but found no record of a prior credit.",
                                ]
                            },
                            "logs": [
                                "Program log: account EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL has insufficient funds",
                            ],
                        }
                    }
                }

        with patch("api.main.requests.post", return_value=Response()):
            result = _fetch_solana_simulate_transaction(
                transaction_base64="AQID",
                rpc_url="https://rpc.example",
                provider="orca-whirlpool",
                variant_id="orca_whirlpool_quote",
                transaction_diagnostics={"decode_ok": True},
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_category"], "insufficient_funds")
        self.assertIn("insufficient_account_candidates", result)
        self.assertIn("EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL", result["insufficient_account_candidates"])

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

    def _mock_orca_execution_quote(self):
        return {
            "ok": True,
            "provider": "orca_whirlpool",
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "85000000",
            "min_out_amount_raw": "84575000",
            "slippage_bps": 50,
            "pool": {"address": "orca_pool", "name": "SOL-USDC"},
        }

    def _fake_subprocess_result(self, payload: dict, returncode: int = 0):
        return subprocess.CompletedProcess(
            args=["node", "tools/orca_whirlpool_prepare.mjs"],
            returncode=returncode,
            stdout=json.dumps(payload),
            stderr="",
        )

    def test_fetch_orca_whirlpool_swap_transaction_rejects_missing_or_multiple_transactions(self):
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({"ok": True, "transactions": []}),
            ),
        ):
            missing = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": True,
                    "transactions": [{"transaction": "tx1"}, {"transaction": "tx2"}],
                }),
            ),
        ):
            multiple = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(missing["error"]["code"], "SWAP_EXECUTION_ORCA_TRANSACTION_MISSING")
        self.assertEqual(
            multiple["error"]["code"],
            "SWAP_EXECUTION_ORCA_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
        )

    def test_fetch_orca_whirlpool_swap_transaction_maps_helper_failures(self):
        with patch("pathlib.Path.exists", return_value=False):
            missing_helper = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({"ok": False, "error": {"message": "failed"}}, returncode=1),
            ),
        ):
            failed = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(missing_helper["error"]["code"], "SWAP_EXECUTION_ORCA_HELPER_FAILED")
        self.assertEqual(failed["error"]["code"], "SWAP_EXECUTION_ORCA_PREPARE_FAILED")

    def test_fetch_orca_whirlpool_swap_transaction_returns_safe_helper_diagnostics(self):
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": False,
                    "error": {
                        "code": "ORCA_PREPARE_FAILED",
                        "message": "missing pool tick arrays",
                        "detail": "quote_response.pool.address missing",
                    },
                }, returncode=1),
            ),
        ):
            result = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_ORCA_PREPARE_FAILED")
        self.assertEqual(result["error"]["provider_code"], "ORCA_PREPARE_FAILED")
        self.assertEqual(result["error"]["provider_message"], "missing pool tick arrays")
        self.assertEqual(result["error"]["provider_detail"], "quote_response.pool.address missing")

    def test_fetch_orca_whirlpool_swap_transaction_passes_configured_rpc_url_to_helper(self):
        captured = {}

        def fake_run(*args, **kwargs):
            captured.update(json.loads(kwargs["input"]))
            return self._fake_subprocess_result({
                "ok": True,
                "transaction_base64": "orca-base64tx",
            })

        with (
            patch.dict(os.environ, {"SWAP_PREPARE_RPC_URL": "https://rpc.example?api-key=SECRET"}, clear=True),
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(captured["rpc_url"], "https://rpc.example?api-key=SECRET")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("api-key", json.dumps(result))
        self.assertNotIn("rpc.example", json.dumps(result))

    def test_fetch_orca_whirlpool_swap_transaction_maps_helper_error_codes_safely(self):
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": False,
                    "error": {
                        "code": "ORCA_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
                        "message": "multiple",
                        "transaction_base64": "orca-secret-transaction",
                    },
                }, returncode=1),
            ),
        ):
            multiple = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": False,
                    "error": {
                        "code": "INVALID_QUOTE_RESPONSE",
                        "message": "bad request",
                        "detail": "see https://orca.example?api-key=SECRET",
                        "transaction_base64": "orca-secret-transaction",
                        "data": {
                            "transaction_base64": "orca-secret-transaction",
                            "url": "https://orca.example?api-key=SECRET",
                        },
                    },
                }, returncode=1),
            ),
        ):
            helper_failed = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(
            multiple["error"]["code"],
            "SWAP_EXECUTION_ORCA_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
        )
        self.assertEqual(helper_failed["error"]["code"], "SWAP_EXECUTION_ORCA_HELPER_FAILED")
        self.assertNotIn("orca-secret-transaction", json.dumps(multiple))
        self.assertNotIn("orca-secret-transaction", json.dumps(helper_failed))
        self.assertNotIn("api-key", json.dumps(helper_failed))
        self.assertNotIn("SECRET", json.dumps(helper_failed))
        self.assertNotIn("orca.example", json.dumps(helper_failed))

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": False,
                    "error": {
                        "code": "ORCA_PREPARE_FAILED",
                        "message": "failed",
                        "detail": "transaction_base64=orca-secret-transaction",
                    },
                }, returncode=1),
            ),
        ):
            unsafe_detail = _fetch_orca_whirlpool_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(unsafe_detail["error"]["code"], "SWAP_EXECUTION_ORCA_PREPARE_FAILED")
        self.assertNotIn("provider_detail", unsafe_detail["error"])
        self.assertNotIn("orca-secret-transaction", json.dumps(unsafe_detail))
        self.assertNotIn("transaction_base64", json.dumps(unsafe_detail))

    def test_fetch_orca_whirlpool_swap_transaction_rejects_camel_case_transaction_markers(self):
        cases = [
            ("message", "transactionBase64=SECRET_TX"),
            ("detail", "signedTransaction=SECRET_TX"),
        ]

        for key, provider_text in cases:
            with self.subTest(key=key, provider_text=provider_text):
                with (
                    patch("pathlib.Path.exists", return_value=True),
                    patch(
                        "subprocess.run",
                        return_value=self._fake_subprocess_result({
                            "ok": False,
                            "error": {
                                "code": "ORCA_PREPARE_FAILED",
                                key: provider_text,
                            },
                        }, returncode=1),
                    ),
                ):
                    result = _fetch_orca_whirlpool_swap_transaction(
                        quote_response={"ok": True},
                        user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                    )

                encoded = json.dumps(result)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_ORCA_PREPARE_FAILED")
                self.assertNotIn("provider_message", result["error"])
                self.assertNotIn("provider_detail", result["error"])
                self.assertNotIn("SECRET_TX", encoded)
                self.assertNotIn("transactionBase64", encoded)
                self.assertNotIn("signedTransaction", encoded)
                self.assertNotIn("transactionbase64", encoded)
                self.assertNotIn("signedtransaction", encoded)

    def test_orca_whirlpool_prepare_helper_exists_and_is_prepare_only(self):
        source = Path("tools/orca_whirlpool_prepare.mjs").read_text()

        self.assertIn("for await (const chunk of process.stdin)", source)
        self.assertIn("writeJson", source)
        self.assertIn("safeScalar", source)
        self.assertIn("request.rpc_url || quote.rpc_url", source)
        self.assertIn('setNativeMintWrappingStrategy("ata")', source)
        self.assertNotIn('setNativeMintWrappingStrategy("none")', source)
        self.assertIn('"transactionbase64"', source)
        self.assertIn('"signedtransaction"', source)
        self.assertIn("transaction_base64", source)
        self.assertNotIn("console.log", source)
        self.assertNotIn("sendTransaction", source)
        self.assertNotIn("signTransaction", source)
        self.assertNotIn("/swap/execute/submit", source)

    def test_orca_prepare_rebuilds_quote_and_returns_normalized_response(self):
        quote = self._mock_orca_execution_quote()
        with (
            patch("api.main._fetch_orca_whirlpool_quote", return_value=quote) as fetch_quote,
            patch(
                "api.main._fetch_orca_whirlpool_swap_transaction",
                return_value={
                    "ok": True,
                    "transaction_base64": "orca-base64tx",
                    "raw": {"transactions": [{"transaction": "orca-base64tx"}]},
                },
            ) as fetch_swap,
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(
                    provider="orca-whirlpool",
                    variant_id="orca_whirlpool_quote",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "orca-whirlpool")
        self.assertEqual(result["execution_surface_label"], "Orca")
        self.assertEqual(result["execution_status"], "prepared")
        self.assertEqual(result["transaction_base64"], "orca-base64tx")
        self.assertEqual(result["transaction_format"], "versioned")
        self.assertEqual(result["quote_summary"]["estimated_output_raw"], "85000000")
        self.assertEqual(result["quote_summary"]["variant_id"], "orca_whirlpool_quote")
        self.assertIn("quote_refreshed_before_execution", result["warnings"])
        fetch_quote.assert_called_once()
        self.assertEqual(fetch_quote.call_args.args[0]["amount_raw"], "1000000000")
        fetch_swap.assert_called_once()
        self.assertEqual(fetch_swap.call_args.kwargs["user_public_key"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")

    def test_orca_prepare_rejects_unsupported_variant(self):
        result = prepare_swap_transaction_with_provider(
            provider_id="orca-whirlpool",
            input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            output_meta={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
            amount=1.0,
            amount_raw=1000000000,
            slippage_bps=50,
            variant_id="recommended_default",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            from_token_query="SOL",
            to_token_query="USDC",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_ORCA_UNSUPPORTED_ROUTE")

    def test_orca_prepare_does_not_mutate_token_meta(self):
        quote = self._mock_orca_execution_quote()
        before = json.dumps(TOKEN_META, sort_keys=True)
        with (
            patch("api.main._fetch_orca_whirlpool_quote", return_value=quote),
            patch(
                "api.main._fetch_orca_whirlpool_swap_transaction",
                return_value={
                    "ok": True,
                    "transaction_base64": "orca-base64tx",
                    "raw": {"transactions": [{"transaction": "orca-base64tx"}]},
                },
            ),
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(
                    provider="orca-whirlpool",
                    variant_id="orca_whirlpool_quote",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

    def test_orca_prepare_stops_failed_refreshed_quote_before_helper(self):
        failed_quote = {
            "ok": False,
            "error": {
                "code": "NO_USABLE_DISCOVERED_POOL",
                "message": "No Orca pool produced a quote.",
                "detail": "missing Orca pool address required for prepare",
            },
        }
        with (
            patch("api.main._fetch_orca_whirlpool_quote", return_value=failed_quote),
            patch("api.main._fetch_orca_whirlpool_swap_transaction") as fetch_swap,
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(
                    provider="orca-whirlpool",
                    variant_id="orca_whirlpool_quote",
                    from_token="USDC",
                    to_token="SOL",
                )
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_ORCA_PREPARE_FAILED")
        self.assertEqual(result["error"]["provider_code"], "NO_USABLE_DISCOVERED_POOL")
        self.assertEqual(result["error"]["provider_message"], "No Orca pool produced a quote.")
        self.assertIn("quote_response_keys", result["error"])
        self.assertIn("quote_error_keys", result["error"])
        fetch_swap.assert_not_called()
        encoded = json.dumps(result)
        self.assertNotIn("transaction_base64", encoded)
        self.assertNotIn("api-key", encoded)
        self.assertNotIn("SECRET", encoded)

    def _mock_pumpswap_execution_quote(self):
        return {
            "ok": True,
            "provider": "pumpswap",
            "direction": "buy_base_with_quote",
            "pool": {
                "address": "GseMAnNDvntR5uFePZ51yZBXzNSn7GdFPkfHwfr6d77J",
                "name": "canonical-pumpswap-pool",
            },
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
            "in_amount_raw": "1000000000",
            "out_amount_raw": "45000000",
            "min_out_amount_raw": "44775000",
            "slippage_bps": 50,
        }

    def test_fetch_pumpswap_swap_transaction_rejects_missing_or_multiple_transactions(self):
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({"ok": True, "transactions": []}),
            ),
        ):
            missing = _fetch_pumpswap_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": True,
                    "transactions": [{"transaction": "tx1"}, {"transaction": "tx2"}],
                }),
            ),
        ):
            multiple = _fetch_pumpswap_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(missing["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_TRANSACTION_MISSING")
        self.assertEqual(
            multiple["error"]["code"],
            "SWAP_EXECUTION_PUMPSWAP_MULTIPLE_TRANSACTIONS_UNSUPPORTED",
        )

    def test_fetch_pumpswap_swap_transaction_maps_helper_failures(self):
        with patch("pathlib.Path.exists", return_value=False):
            missing_helper = _fetch_pumpswap_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": False,
                    "error": {"code": "PUMPSWAP_PREPARE_NOT_IMPLEMENTED", "message": "not implemented"},
                }, returncode=1),
            ),
        ):
            helper_failed = _fetch_pumpswap_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": False,
                    "error": {"code": "PUMPSWAP_PREPARE_FAILED", "message": "pool state invalid"},
                }, returncode=1),
            ),
        ):
            prepare_failed = _fetch_pumpswap_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertEqual(missing_helper["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED")
        self.assertEqual(helper_failed["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_HELPER_FAILED")
        self.assertEqual(prepare_failed["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_PREPARE_FAILED")
        self.assertEqual(prepare_failed["error"]["provider_message"], "pool state invalid")

    def test_fetch_pumpswap_swap_transaction_returns_normalized_transaction_when_mocked(self):
        captured = {}

        def fake_run(*args, **kwargs):
            captured.update(json.loads(kwargs["input"]))
            return self._fake_subprocess_result({
                "ok": True,
                "transaction_base64": "pumpswap-base64tx",
            })

        with (
            patch.dict(os.environ, {"SWAP_PREPARE_RPC_URL": "https://rpc.example?api-key=SECRET"}, clear=True),
            patch("pathlib.Path.exists", return_value=True),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = _fetch_pumpswap_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["transaction_base64"], "pumpswap-base64tx")
        self.assertEqual(captured["user_public_key"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertEqual(captured["tx_version"], "V0")
        self.assertEqual(captured["rpc_url"], "https://rpc.example?api-key=SECRET")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("api-key", json.dumps(result))
        self.assertNotIn("rpc.example", json.dumps(result))

    def test_fetch_pumpswap_swap_transaction_sanitizes_error_payloads(self):
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch(
                "subprocess.run",
                return_value=self._fake_subprocess_result({
                    "ok": False,
                    "error": {
                        "code": "PUMPSWAP_PREPARE_FAILED",
                        "message": "transaction_base64=SECRET_TX",
                        "detail": "https://pump.example?api-key=SECRET",
                        "data": {
                            "transaction_base64": "SECRET_TX",
                            "url": "https://pump.example?api-key=SECRET",
                        },
                    },
                }, returncode=1),
            ),
        ):
            result = _fetch_pumpswap_swap_transaction(
                quote_response={"ok": True},
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        encoded = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_PREPARE_FAILED")
        self.assertNotIn("provider_message", result["error"])
        self.assertNotIn("provider_detail", result["error"])
        self.assertNotIn("SECRET_TX", encoded)
        self.assertNotIn("transaction_base64", encoded)
        self.assertNotIn("api-key", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("pump.example", encoded)

    def test_fresh_pumpswap_execution_quote_rejects_failed_quote_response(self):
        with patch(
            "api.main._fetch_pumpswap_quote",
            return_value={
                "ok": False,
                "error": {
                    "code": "UNHANDLED_ERROR",
                    "message": "Unhandled PumpSwap quote helper error.",
                    "details": {"message": "Endpoint URL must start with http or https."},
                },
            },
        ):
            result = _fetch_fresh_pumpswap_execution_quote(
                input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
                output_meta={"mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump", "decimals": 6},
                amount_raw=10000000,
                slippage_bps=50,
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_PREPARE_FAILED")
        self.assertEqual(result["error"]["provider_code"], "UNHANDLED_ERROR")
        self.assertEqual(result["error"]["provider_message"], "Unhandled PumpSwap quote helper error.")
        self.assertEqual(result["error"]["provider_detail"], "Endpoint URL must start with http or https.")

    def test_fresh_pumpswap_execution_quote_does_not_pass_error_envelope_to_prepare_helper(self):
        with patch(
            "api.main._fetch_pumpswap_quote",
            return_value={
                "ok": False,
                "error": {
                    "code": "PUMPSWAP_UNSUPPORTED_ROUTE",
                    "message": "transaction_base64=SECRET_TX",
                    "details": {"message": "https://pump.example?api-key=SECRET"},
                },
            },
        ):
            result = _fetch_fresh_pumpswap_execution_quote(
                input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
                output_meta={"mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump", "decimals": 6},
                amount_raw=10000000,
                slippage_bps=50,
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        encoded = json.dumps(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_PREPARE_FAILED")
        self.assertNotIn("provider_message", result["error"])
        self.assertNotIn("provider_detail", result["error"])
        self.assertNotIn("SECRET_TX", encoded)
        self.assertNotIn("transaction_base64", encoded)
        self.assertNotIn("api-key", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("pump.example", encoded)

    def test_pumpswap_prepare_rebuilds_quote_and_returns_normalized_response_when_mocked(self):
        quote = self._mock_pumpswap_execution_quote()
        before = json.dumps(TOKEN_META, sort_keys=True)
        with (
            patch("api.main._fetch_pumpswap_quote", return_value=quote) as fetch_quote,
            patch(
                "api.main._fetch_pumpswap_swap_transaction",
                return_value={
                    "ok": True,
                    "transaction_base64": "pumpswap-base64tx",
                    "raw": {"transaction_base64": "pumpswap-base64tx"},
                },
            ) as fetch_swap,
        ):
            result = swap_execute_prepare(
                self._base_swap_execute_prepare_payload(
                    provider="pumpswap",
                    variant_id="pumpswap_quote",
                    to_token="7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump",
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "pumpswap")
        self.assertEqual(result["execution_surface_label"], "PumpSwap")
        self.assertEqual(result["execution_status"], "prepared")
        self.assertEqual(result["transaction_base64"], "pumpswap-base64tx")
        self.assertEqual(result["transaction_format"], "versioned")
        self.assertEqual(result["quote_summary"]["estimated_output_raw"], "45000000")
        self.assertEqual(result["quote_summary"]["variant_id"], "pumpswap_quote")
        self.assertIn("quote_refreshed_before_execution", result["warnings"])
        fetch_quote.assert_called_once()
        self.assertEqual(fetch_quote.call_args.args[0]["amount_raw"], "1000000000")
        fetch_swap.assert_called_once()
        self.assertEqual(fetch_swap.call_args.kwargs["user_public_key"], "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL")
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

    def test_pumpswap_prepare_rejects_unsupported_variant(self):
        result = prepare_swap_transaction_with_provider(
            provider_id="pumpswap",
            input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            output_meta={"mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump", "decimals": 6},
            amount=1.0,
            amount_raw=1000000000,
            slippage_bps=50,
            variant_id="recommended_default",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            from_token_query="SOL",
            to_token_query="FIGURE",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_PUMPSWAP_UNSUPPORTED_ROUTE")

    def test_pumpswap_prepare_helper_exists_and_is_prepare_only(self):
        source = Path("tools/pumpswap_prepare.mjs").read_text()

        self.assertIn("for await (const chunk of process.stdin)", source)
        self.assertIn("writeJson", source)
        self.assertIn("safeScalar", source)
        self.assertIn("function normalizePumpSwapDirection", source)
        self.assertIn('direction === "buy_base_with_quote"', source)
        self.assertIn('direction === "sell_base_for_quote"', source)
        self.assertIn("normalizedDirection", source)
        self.assertIn("OnlinePumpAmmSdk", source)
        self.assertIn("PUMP_AMM_SDK.buyQuoteInput", source)
        self.assertIn("PUMP_AMM_SDK.sellBaseInput", source)
        self.assertIn("new TransactionMessage", source)
        self.assertIn("new VersionedTransaction", source)
        self.assertIn("request.rpc_url || quote.rpc_url || process.env.SOLANA_RPC_URL || DEFAULT_RPC_URL", source)
        self.assertIn('"transactionbase64"', source)
        self.assertIn('"signedtransaction"', source)
        self.assertNotIn("console.log", source)
        self.assertNotIn("sendTransaction", source)
        self.assertNotIn("signTransaction", source)
        self.assertNotIn("/swap/execute/submit", source)

    def test_meteora_dlmm_prepare_helper_exists_and_is_prepare_only(self):
        source = Path("tools/meteora_dlmm_prepare.mjs").read_text()

        self.assertIn("readInputArgOrStdin", source)
        self.assertIn("process.argv[2]", source)
        self.assertIn("DLMM.create", source)
        self.assertIn("dlmmPool.swap", source)
        self.assertIn("ensureBinArrayBitmapExtensionWritable", source)
        self.assertIn("binArrayBitmapExtension", source)
        self.assertIn("meta.isWritable = true", source)
        self.assertIn("bin_array_bitmap_extension_marked_writable", source)
        self.assertIn("instruction_diagnostics", source)
        self.assertIn("account_metas", source)
        self.assertIn("include_diagnostics", source)
        self.assertIn("new TransactionMessage", source)
        self.assertIn("new VersionedTransaction", source)
        self.assertIn('transaction_format: "versioned"', source)
        self.assertIn('"transactionbase64"', source)
        self.assertIn('"signedtransaction"', source)
        self.assertNotIn("console.log", source)
        self.assertNotIn("sendTransaction", source)
        self.assertNotIn("signTransaction", source)
        self.assertNotIn("/swap/execute/submit", source)

    def test_meteora_dlmm_prepare_dry_run_helper_exists_and_hides_transaction_by_default(self):
        source = Path("tools/meteora_dlmm_prepare_dry_run.mjs").read_text()

        self.assertIn("readInputArgOrStdin", source)
        self.assertIn("process.argv[2]", source)
        self.assertIn("quoteHelperPath", source)
        self.assertIn("prepareHelperPath", source)
        self.assertIn("transaction_base64_present", source)
        self.assertIn("transaction_base64_length", source)
        self.assertIn("include_transaction_base64", source)
        self.assertIn("include_diagnostics", source)
        self.assertIn("prepare_diagnostics", source)
        self.assertIn("writable_account_patch", source)
        self.assertIn("request.includeTransactionBase64 === true", source)
        self.assertIn("result.transaction_base64 = transactionBase64", source)
        self.assertNotIn("sendTransaction", source)
        self.assertNotIn("signTransaction", source)
        self.assertNotIn("/swap/execute/submit", source)

    def test_meteora_dlmm_prepare_dry_run_rejects_non_single_pool_by_source_gate(self):
        source = Path("tools/meteora_dlmm_prepare_dry_run.mjs").read_text()

        self.assertIn('routeShape !== "single-pool"', source)
        self.assertIn("METEORA_DLMM_DRY_RUN_UNSUPPORTED_ROUTE", source)
        self.assertIn("METEORA_DLMM_DRY_RUN_POOL_MISSING", source)
        self.assertIn("METEORA_DLMM_DRY_RUN_BIN_ARRAYS_MISSING", source)
        self.assertIn("Only single-pool Meteora DLMM routes are supported", source)

    def test_meteora_dlmm_prepare_helper_rejects_two_hop_and_missing_pool(self):
        base_payload = {
            "user_public_key": "EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            "pool_address": "3tdsJ4hX5yhfWzjvYjzp7NQ4zoyEoJ9RuqGpWr3x6wmg",
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "amount_raw": "1000000000",
            "min_out_amount_raw": "84900000",
            "slippage_bps": 50,
            "bin_arrays": ["8oaT3tYHjpuQJnE1tdv6UQV8kF2CPvDQpFK2bMMp6eAX"],
            "route_shape": "single-pool",
            "tx_version": "V0",
        }

        cases = [
            ({"route_shape": "two-hop"}, "METEORA_DLMM_UNSUPPORTED_ROUTE"),
            ({"pool_address": ""}, "INVALID_PUBLIC_KEY"),
            ({"bin_arrays": []}, "METEORA_DLMM_BIN_ARRAYS_REQUIRED"),
        ]
        for override, expected_code in cases:
            payload = {**base_payload, **override}
            with self.subTest(expected_code=expected_code):
                proc = subprocess.run(
                    ["node", "tools/meteora_dlmm_prepare.mjs", json.dumps(payload)],
                    capture_output=True,
                    text=True,
                    cwd=Path(__file__).resolve().parent,
                    timeout=10,
                )
                data = json.loads(proc.stdout)

                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(data["ok"])
                self.assertEqual(data["error"]["code"], expected_code)

    def _mock_meteora_execution_quote(self, **overrides):
        quote = {
            "provider": "meteora_dlmm",
            "pool": {"address": "3tdsJ4hX5yhfWzjvYjzp7NQ4zoyEoJ9RuqGpWr3x6wmg"},
            "input_mint": METEORA_DLMM_SOL_MINT,
            "output_mint": METEORA_DLMM_USDC_MINT,
            "in_amount_raw": "1000000000",
            "out_amount_raw": "85000000",
            "min_out_amount_raw": "84900000",
            "slippage_bps": 50,
            "bin_arrays": ["8oaT3tYHjpuQJnE1tdv6UQV8kF2CPvDQpFK2bMMp6eAX"],
            "route_shape": "single-pool",
        }
        quote.update(overrides)
        return quote

    def test_meteora_prepare_rejects_unsupported_variant(self):
        result = prepare_swap_transaction_with_provider(
            provider_id="meteora-dlmm",
            input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            output_meta={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
            amount=1.0,
            amount_raw=1000000000,
            slippage_bps=50,
            variant_id="recommended_default",
            user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            from_token_query="SOL",
            to_token_query="USDC",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_METEORA_UNSUPPORTED_ROUTE")

    def test_meteora_prepare_rejects_two_hop_quote(self):
        quote = self._mock_meteora_execution_quote(route_shape="two-hop", leg_quotes=[{"pool": "mock"}])
        with patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": quote}):
            result = _prepare_meteora_dlmm_swap_transaction(
                input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
                output_meta={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
                amount=1.0,
                amount_raw=1000000000,
                slippage_bps=50,
                variant_id="meteora_dlmm_quote",
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                from_token_query="SOL",
                to_token_query="USDC",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_METEORA_UNSUPPORTED_ROUTE")
        self.assertIn("two-hop", result["error"]["provider_detail"])

    def test_meteora_prepare_rejects_missing_pool_or_bin_arrays(self):
        cases = [
            self._mock_meteora_execution_quote(pool={}),
            self._mock_meteora_execution_quote(bin_arrays=[]),
        ]
        for quote in cases:
            with self.subTest(quote=quote):
                with patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": quote}):
                    result = _prepare_meteora_dlmm_swap_transaction(
                        input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
                        output_meta={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
                        amount=1.0,
                        amount_raw=1000000000,
                        slippage_bps=50,
                        variant_id="meteora_dlmm_quote",
                        user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                        from_token_query="SOL",
                        to_token_query="USDC",
                    )

                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "SWAP_EXECUTION_METEORA_PREPARE_FAILED")

    def test_fetch_meteora_dlmm_swap_transaction_normalizes_helper_success(self):
        helper_json = json.dumps({
            "ok": True,
            "provider": "meteora-dlmm",
            "transaction_format": "versioned",
            "transaction_base64": "meteora-base64tx",
        })

        def fake_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(args=["node"], returncode=0, stdout=helper_json, stderr="")

        with patch("api.main.subprocess.run", side_effect=fake_run) as run:
            result = _fetch_meteora_dlmm_swap_transaction(
                quote_response=self._mock_meteora_execution_quote(),
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["transaction_base64"], "meteora-base64tx")
        sent_payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(sent_payload["pool_address"], "3tdsJ4hX5yhfWzjvYjzp7NQ4zoyEoJ9RuqGpWr3x6wmg")
        self.assertEqual(sent_payload["route_shape"], "single-pool")
        self.assertEqual(sent_payload["tx_version"], "V0")

    def test_meteora_prepare_normalizes_mocked_success_with_single_pool_capability_enabled(self):
        quote = self._mock_meteora_execution_quote()
        before = json.dumps(TOKEN_META, sort_keys=True)
        with (
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value={"ok": True, "data": quote}),
            patch(
                "api.main._fetch_meteora_dlmm_swap_transaction",
                return_value={
                    "ok": True,
                    "transaction_base64": "meteora-base64tx",
                    "raw": {"transaction_format": "versioned"},
                },
            ),
        ):
            result = _prepare_meteora_dlmm_swap_transaction(
                input_meta={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9, "symbol": "SOL"},
                output_meta={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6, "symbol": "USDC"},
                amount=1.0,
                amount_raw=1000000000,
                slippage_bps=50,
                variant_id="meteora_dlmm_quote",
                user_public_key="EUaGMYfk7KFfCn8XPdRNVPNC4pvg3vyGYXovkyuWitUL",
                from_token_query="SOL",
                to_token_query="USDC",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["provider"], "meteora-dlmm")
        self.assertEqual(result["execution_surface_label"], "Meteora")
        self.assertEqual(result["transaction_format"], "versioned")
        self.assertEqual(result["transaction_base64"], "meteora-base64tx")
        self.assertEqual(result["quote_summary"]["variant_id"], "meteora_dlmm_quote")
        self.assertIn("meteora_dlmm_prepare_research_only", result["warnings"])
        self.assertTrue(SWAP_EXECUTION_PROVIDER_CAPABILITIES["meteora-dlmm"]["prepare"])
        self.assertTrue(SWAP_EXECUTION_PROVIDER_CAPABILITIES["meteora-dlmm"]["submit"])
        self.assertEqual(SWAP_EXECUTION_PROVIDER_CAPABILITIES["meteora-dlmm"]["status"], "executable_v1_single_pool")
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

    def _readiness_jupiter_option(self, **overrides):
        option = {
            "provider": "jupiter-metis",
            "variant_id": "recommended_default",
            "is_comparison_only": False,
            "is_clickable": True,
            "execution_status": "executable_capable",
        }
        option.update(overrides)
        return option

    def test_swap_execution_readiness_marks_jupiter_prepare_available(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
        )

        self.assertTrue(result["execution_ready"])
        self.assertEqual(result["execution_stage"], "prepare_available")
        self.assertEqual(result["execution_provider"], "jupiter-metis")
        self.assertEqual(result["provider_status"], "executable_v1")
        self.assertTrue(result["prepare_capable"])
        self.assertTrue(result["submit_capable"])
        self.assertEqual(result["reasons"], [])

    def test_swap_execution_provider_capability_matrix_covers_quote_universes(self):
        expected = {
            "jupiter-metis",
            "raydium-trade-api",
            "orca-whirlpool",
            "meteora-dlmm",
            "pumpswap",
            "phantom-routing-api",
            "phoenix-clob",
        }

        self.assertTrue(expected.issubset(set(SWAP_EXECUTION_PROVIDER_CAPABILITIES)))
        jupiter = SWAP_EXECUTION_PROVIDER_CAPABILITIES["jupiter-metis"]
        self.assertTrue(jupiter["prepare"])
        self.assertTrue(jupiter["submit"])

        for provider_id in {"raydium-trade-api", "orca-whirlpool", "meteora-dlmm", "pumpswap"}:
            capability = SWAP_EXECUTION_PROVIDER_CAPABILITIES[provider_id]
            self.assertTrue(capability["prepare"])
            self.assertTrue(capability["submit"])
            if provider_id == "meteora-dlmm":
                self.assertEqual(capability["status"], "executable_v1_single_pool")
            else:
                self.assertEqual(capability["status"], "executable_v1")

        for provider_id in expected - {"jupiter-metis", "raydium-trade-api", "orca-whirlpool", "meteora-dlmm", "pumpswap"}:
            capability = SWAP_EXECUTION_PROVIDER_CAPABILITIES[provider_id]
            self.assertFalse(capability["prepare"])
            self.assertFalse(capability["submit"])

    def test_swap_execution_provider_capability_unknown_fallback_is_safe(self):
        capability = get_swap_execution_provider_capability("unknown-provider")

        self.assertEqual(capability["provider"], "unknown-provider")
        self.assertFalse(capability["quote"])
        self.assertFalse(capability["prepare"])
        self.assertFalse(capability["submit"])
        self.assertEqual(capability["status"], "unknown")

    def test_swap_execution_readiness_marks_raydium_prepare_available(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(
                provider="raydium-trade-api",
                variant_id="raydium_quote",
            ),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
        )

        self.assertTrue(result["execution_ready"])
        self.assertEqual(result["execution_stage"], "prepare_available")
        self.assertEqual(result["execution_provider"], "raydium-trade-api")
        self.assertEqual(result["provider_status"], "executable_v1")
        self.assertTrue(result["prepare_capable"])
        self.assertTrue(result["submit_capable"])

    def test_swap_execution_readiness_marks_orca_prepare_available(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(
                provider="orca-whirlpool",
                variant_id="orca_whirlpool_quote",
            ),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
        )

        self.assertTrue(result["execution_ready"])
        self.assertEqual(result["execution_stage"], "prepare_available")
        self.assertEqual(result["execution_provider"], "orca-whirlpool")
        self.assertEqual(result["provider_status"], "executable_v1")
        self.assertTrue(result["prepare_capable"])
        self.assertTrue(result["submit_capable"])

    def test_swap_execution_readiness_marks_meteora_single_pool_prepare_available(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(
                provider="meteora-dlmm",
                variant_id="meteora_dlmm_quote",
            ),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
        )

        self.assertTrue(result["execution_ready"])
        self.assertEqual(result["execution_stage"], "prepare_available")
        self.assertEqual(result["execution_provider"], "meteora-dlmm")
        self.assertEqual(result["provider_status"], "executable_v1_single_pool")
        self.assertTrue(result["prepare_capable"])
        self.assertTrue(result["submit_capable"])

    def test_swap_execution_readiness_marks_pumpswap_prepare_available(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(
                provider="pumpswap",
                variant_id="pumpswap_quote",
            ),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump", "decimals": 6},
        )

        self.assertTrue(result["execution_ready"])
        self.assertEqual(result["execution_stage"], "prepare_available")
        self.assertEqual(result["execution_provider"], "pumpswap")
        self.assertEqual(result["provider_status"], "executable_v1")
        self.assertTrue(result["prepare_capable"])
        self.assertTrue(result["submit_capable"])

    def test_swap_execution_readiness_rejects_unsupported_non_jupiter_providers(self):
        for provider_id in ("phantom-routing-api", "phoenix-clob"):
            result = build_swap_execution_readiness(
                self._readiness_jupiter_option(provider=provider_id, variant_id=f"{provider_id}_quote"),
                from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
                to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
            )
            self.assertFalse(result["execution_ready"])
            self.assertEqual(result["execution_stage"], "quote_only")
            self.assertIn("NON_JUPITER_ROUTE", result["reasons"])

    def test_swap_execution_readiness_rejects_executable_provider_unsupported_variant(self):
        for provider_id in ("raydium-trade-api", "orca-whirlpool", "meteora-dlmm", "pumpswap"):
            result = build_swap_execution_readiness(
                self._readiness_jupiter_option(provider=provider_id, variant_id="recommended_default"),
                from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
                to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
            )
            self.assertFalse(result["execution_ready"])
            self.assertIn("UNSUPPORTED_VARIANT", result["reasons"])

    def test_swap_execution_readiness_marks_comparison_only_quote_only(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(is_comparison_only=True),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
        )

        self.assertFalse(result["execution_ready"])
        self.assertIn("COMPARISON_ONLY_ROUTE", result["reasons"])

    def test_swap_execution_readiness_blocks_missing_decimals(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": "CustomMint111", "decimals": None},
        )

        self.assertFalse(result["execution_ready"])
        self.assertIn("TOKEN_DECIMALS_UNAVAILABLE", result["reasons"])

    def test_swap_execution_readiness_blocks_unsupported_network(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
            network="ethereum",
        )

        self.assertFalse(result["execution_ready"])
        self.assertIn("UNSUPPORTED_NETWORK", result["reasons"])

    def test_swap_execution_readiness_blocks_unsupported_variant(self):
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(variant_id="pumpswap_quote"),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
        )

        self.assertFalse(result["execution_ready"])
        self.assertIn("UNSUPPORTED_VARIANT", result["reasons"])

    def test_swap_execution_readiness_does_not_mutate_token_meta(self):
        before = json.dumps(TOKEN_META, sort_keys=True)
        result = build_swap_execution_readiness(
            self._readiness_jupiter_option(),
            from_resolution={"mint": METEORA_DLMM_SOL_MINT, "decimals": 9},
            to_resolution={"mint": METEORA_DLMM_USDC_MINT, "decimals": 6},
        )

        self.assertTrue(result["execution_ready"])
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

    def test_swap_quote_adds_execution_readiness_metadata(self):
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
        unsupported = {"ok": False, "error": {"status_code": 400, "detail": "unsupported"}}

        with (
            patch("api.main._fetch_jupiter_quote", return_value=jupiter_quote),
            patch("api.main._try_fetch_raydium_quote", return_value=unsupported),
            patch("api.main._try_fetch_meteora_dlmm_quote", return_value=unsupported),
            patch("api.main._try_fetch_orca_whirlpool_quote", return_value=unsupported),
            patch("api.main._try_fetch_phantom_quote", return_value=unsupported),
            patch("api.main._try_fetch_phoenix_quote", return_value=unsupported),
            patch("api.main._try_fetch_pumpswap_quote", return_value=unsupported),
            patch("api.main._resolve_quote_reference_prices_usd", return_value={}),
        ):
            response = swap_quote(from_token="SOL", to_token="USDC", amount=1.0)

        self.assertIn("execution_readiness", response["recommended_option"])
        self.assertIn("execution_readiness", response["recommended_executable_option"])
        self.assertIn("execution_readiness", response["direct_route_check"])
        self.assertTrue(response["recommended_executable_option"]["execution_readiness"]["execution_ready"])
        self.assertEqual(
            response["recommended_executable_option"]["execution_readiness"]["execution_stage"],
            "prepare_available",
        )

    def test_swap_ui_renders_execution_readiness_labels(self):
        html = build_ui_html()

        self.assertNotIn("Execution-ready via Jupiter", html)
        self.assertNotIn("Execution-ready via Raydium", html)
        self.assertNotIn("Execution-ready via Orca", html)
        self.assertNotIn("Execution-ready via PumpSwap", html)
        self.assertNotIn("Comparison-only - no swap action available yet.", html)
        self.assertIn("function swapExecutionReadinessReasonLabel(reason)", html)
        self.assertIn("NON_JUPITER_ROUTE: \"Quote-only route.\"", html)
        self.assertIn("COMPARISON_ONLY_ROUTE: \"Comparison-only route.\"", html)
        self.assertIn("TOKEN_DECIMALS_UNAVAILABLE: \"Token decimals unavailable.\"", html)
        self.assertIn("execution_research: \"Quote-only\"", html)
        self.assertIn("benchmark_quote_only: \"Benchmark\"", html)
        self.assertIn("advanced_research: \"Quote-only\"", html)

    def test_swap_ui_button_gating_requires_supported_executable_readiness(self):
        html = build_ui_html()
        start = html.index("function isExecutableRouteOption(opt)")
        end = html.index("function renderRouteActionButton", start)
        gate = html[start:end]

        self.assertIn("SWAP_EXECUTABLE_PROVIDERS.has(provider)", gate)
        self.assertIn("supportedVariants?.has(opt?.variant_id) === true", gate)
        self.assertIn("opt?.execution_readiness?.execution_ready === true", gate)
        self.assertIn("opt?.execution_readiness?.prepare_capable === true", gate)
        self.assertIn("opt?.execution_readiness?.submit_capable === true", gate)
        self.assertIn("opt?.is_clickable === true", gate)
        self.assertIn("opt?.is_comparison_only !== true", gate)
        self.assertIn('opt?.execution_status === "executable_capable"', gate)

    def test_execution_readiness_audit_tool_defaults_and_pair_parsing(self):
        from tools import execution_readiness_audit as audit

        self.assertIn("SOL:USDC", audit.DEFAULT_PAIRS)
        self.assertIn("SOL:BONK", audit.DEFAULT_PAIRS)
        self.assertIn("SOL:WIF", audit.DEFAULT_PAIRS)

        parser = audit.build_parser()
        args = parser.parse_args(["--pair", "SOL:USDC", "--pair", "SOL:WIF"])
        pairs = audit.build_pairs(args)
        self.assertEqual([pair.label for pair in pairs], ["SOL:USDC", "SOL:WIF"])

    def test_execution_readiness_audit_tool_reports_provider_capabilities(self):
        from tools import execution_readiness_audit as audit

        rows = [
            {
                "pair": "SOL:USDC",
                "quote_ok": True,
                "best_surface": "Jupiter",
                "jupiter_ready": True,
                "stage": "prepare_available",
                "provider_status": "executable_v1",
                "provider_label": "Jupiter",
                "prepare_capable": True,
                "submit_capable": True,
                "prepare_checked": False,
                "prepare_ok": None,
                "error_code": None,
                "external": False,
            }
        ]

        text = audit.render_text_report(rows)
        self.assertIn("provider_status", text)
        self.assertIn("provider_label", text)
        self.assertIn("prepare_capable", text)
        self.assertIn("submit_capable", text)
        self.assertIn("executable_v1", text)

    def test_execution_readiness_audit_prepare_requires_user_public_key(self):
        from tools import execution_readiness_audit as audit

        parser = audit.build_parser()
        missing_key = parser.parse_args(["--pair", "SOL:USDC", "--check-prepare"])
        with_key = parser.parse_args([
            "--pair",
            "SOL:USDC",
            "--check-prepare",
            "--user-public-key",
            "Wallet111",
        ])

        self.assertFalse(audit.should_check_prepare(missing_key))
        self.assertTrue(audit.should_check_prepare(with_key))

    def test_execution_readiness_audit_prepare_provider_defaults_and_supports_raydium(self):
        from tools import execution_readiness_audit as audit

        parser = audit.build_parser()
        default_args = parser.parse_args([])
        raydium_args = parser.parse_args(["--prepare-provider", "raydium-trade-api"])

        self.assertEqual(default_args.prepare_provider, "jupiter-metis")
        self.assertEqual(raydium_args.prepare_provider, "raydium-trade-api")

    def test_execution_readiness_audit_raydium_prepare_payload(self):
        from tools import execution_readiness_audit as audit

        pair = audit.AuditPair(from_token="SOL", to_token="USDC")
        payload = audit.prepare_payload(
            pair,
            {"provider": "raydium-trade-api", "variant_id": "ignored"},
            1.25,
            "Wallet111",
            provider="raydium-trade-api",
        )

        self.assertEqual(payload["provider"], "raydium-trade-api")
        self.assertEqual(payload["variant_id"], "raydium_quote")
        self.assertEqual(payload["network"], "solana")
        self.assertEqual(payload["user_public_key"], "Wallet111")

    def test_execution_readiness_audit_selects_raydium_option(self):
        from tools import execution_readiness_audit as audit

        quote_data = {
            "recommended_executable_option": {"provider": "jupiter-metis", "variant_id": "recommended_default"},
            "other_options": [
                {"provider": "meteora-dlmm", "variant_id": "meteora_dlmm_quote"},
                {"provider": "raydium-trade-api", "variant_id": "raydium_quote"},
            ],
        }

        option = audit.prepare_option_for_provider(quote_data, "raydium-trade-api")
        self.assertIsNotNone(option)
        self.assertEqual(option["variant_id"], "raydium_quote")

    def test_execution_readiness_audit_raydium_missing_option_reports_error(self):
        from tools import execution_readiness_audit as audit

        parser = audit.build_parser()
        args = parser.parse_args([
            "--pair",
            "SOL:USDC",
            "--check-prepare",
            "--user-public-key",
            "Wallet111",
            "--prepare-provider",
            "raydium-trade-api",
        ])
        quote_response = {
            "ok": True,
            "status": 200,
            "data": {
                "ok": True,
                "recommended_executable_option": {
                    "provider": "jupiter-metis",
                    "variant_id": "recommended_default",
                    "execution_readiness": {"execution_ready": True},
                },
                "other_options": [],
                "summary": {"uses_external_tokens": False},
            },
        }

        with patch("tools.execution_readiness_audit._request_json", return_value=quote_response):
            row = audit.audit_pair(args, audit.AuditPair(from_token="SOL", to_token="USDC"))

        self.assertFalse(row["prepare_checked"])
        self.assertFalse(row["prepare_ok"])
        self.assertEqual(row["error_code"], "RAYDIUM_OPTION_NOT_FOUND")

    def test_execution_readiness_audit_raydium_records_transaction_presence_without_payload(self):
        from tools import execution_readiness_audit as audit

        parser = audit.build_parser()
        args = parser.parse_args([
            "--pair",
            "SOL:USDC",
            "--check-prepare",
            "--user-public-key",
            "Wallet111",
            "--prepare-provider",
            "raydium-trade-api",
            "--json",
        ])
        quote_response = {
            "ok": True,
            "status": 200,
            "data": {
                "ok": True,
                "recommended_executable_option": {
                    "provider": "jupiter-metis",
                    "variant_id": "recommended_default",
                    "execution_readiness": {"execution_ready": True},
                },
                "other_options": [
                    {
                        "provider": "raydium-trade-api",
                        "variant_id": "raydium_quote",
                        "execution_surface_label": "Raydium",
                    }
                ],
                "summary": {"uses_external_tokens": False},
            },
        }
        prepare_response = {
            "ok": True,
            "status": 200,
            "data": {
                "ok": True,
                "transaction_base64": "raydium-secret-transaction",
                "transaction_format": "versioned",
            },
        }

        with patch("tools.execution_readiness_audit._request_json", side_effect=[quote_response, prepare_response]):
            row = audit.audit_pair(args, audit.AuditPair(from_token="SOL", to_token="USDC"))

        self.assertTrue(row["prepare_checked"])
        self.assertTrue(row["prepare_ok"])
        self.assertTrue(row["transaction_present"])
        self.assertEqual(row["transaction_format"], "versioned")
        self.assertNotIn("transaction_base64", row)
        self.assertNotIn("raydium-secret-transaction", json.dumps(row))

    def test_execution_readiness_audit_tool_has_no_sign_or_submit_path(self):
        source = Path("tools/execution_readiness_audit.py").read_text()

        self.assertNotIn("/swap/execute/submit", source)
        self.assertNotIn("signTransaction", source)
        self.assertNotIn("sendRawTransaction", source)

    def test_execution_readiness_audit_tool_does_not_mutate_token_meta(self):
        from tools import execution_readiness_audit as audit

        before = json.dumps(TOKEN_META, sort_keys=True)
        parser = audit.build_parser()
        args = parser.parse_args(["--pair", "SOL:USDC"])
        pairs = audit.build_pairs(args)

        self.assertEqual([pair.label for pair in pairs], ["SOL:USDC"])
        self.assertEqual(json.dumps(TOKEN_META, sort_keys=True), before)

if __name__ == "__main__":
    unittest.main()
