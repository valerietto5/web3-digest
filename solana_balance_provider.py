from __future__ import annotations

from typing import Dict
from providers.solana_rpc import get_sol_balance_lamports, get_spl_token_balances
from token_registry import mint_to_asset_key


USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def fetch_solana_owner_balances(address: str) -> Dict[str, float]:
    out: Dict[str, float] = {}

    lamports = get_sol_balance_lamports(address)
    out["sol"] = lamports / 1_000_000_000

    DUST_MIN = 1e-6

    tokens = get_spl_token_balances(address)
    for t in tokens:
        amt = float(t.amount_ui)
        if amt <= 0:
            continue
        if amt < DUST_MIN:
            continue

        key = mint_to_asset_key(t.mint)
        out[key] = out.get(key, 0.0) + amt


    return out

