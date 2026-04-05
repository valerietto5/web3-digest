# token_registry.py
# Minimal manual registry for Solana SPL tokens.
# Key: SPL mint address
# Value: metadata used for display and (optionally) pricing.

from __future__ import annotations

from typing import Dict, TypedDict, Optional


class TokenMeta(TypedDict, total=False):
    asset: str          # our internal asset key, e.g. "usdc"
    symbol: str         # display symbol, e.g. "USDC"
    name: str           # human name
    coingecko_id: str   # CoinGecko "id" for /simple/price, e.g. "usd-coin"


# Known SPL mints (Solana)
TOKENS: Dict[str, TokenMeta] = {

    "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump": {
        "symbol": "SNP500",
        "name": "SNP500",
        "dexscreener": True,
},
    # USDC (Solana)
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {
        "asset": "usdc",
        "symbol": "USDC",
        "name": "USD Coin",
        "coingecko_id": "usd-coin",
    },
    # USDT (Solana)
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {
        "asset": "usdt",
        "symbol": "USDT",
        "name": "Tether",
        "coingecko_id": "tether",
    },
    # Example meme (only useful if you ever hold it)
    # BONK (Solana)
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": {
        "asset": "bonk",
        "symbol": "BONK",
        "name": "Bonk",
        "coingecko_id": "bonk",
    },
}


def mint_to_asset_key(mint: str) -> str:
    """
    If we recognize the mint, return a normal asset key like "usdc".
    Otherwise return our fallback key "spl:<mint>".
    """
    meta = TOKENS.get(mint)
    if meta and meta.get("asset"):
        return meta["asset"].lower()
    return f"spl:{mint}"


def asset_key_to_symbol(asset: str) -> str:
    """
    Display helper:
    - "sol" -> "SOL"
    - "usdc" -> "USDC"
    - "spl:<mint>" -> "SPL:<short>"
    """
    a = asset.lower()
    if a.startswith("spl:"):
        mint = a.split(":", 1)[1]
        return f"SPL:{mint[:4]}…{mint[-4:]}"
    return a.upper()
