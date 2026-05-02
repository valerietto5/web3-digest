# token_registry.py
# Minimal manual registry for Solana SPL tokens.
# Key: SPL mint address
# Value: metadata used for display and (optionally) pricing.

from __future__ import annotations

from typing import Dict, TypedDict


class TokenMeta(TypedDict, total=False):
    asset: str          # our internal asset key, e.g. "usdc"
    symbol: str         # display symbol, e.g. "USDC"
    name: str           # human name
    display_name: str   # UI display name
    mint: str           # Solana mint address used by quote APIs
    decimals: int       # SPL/native token decimals
    coingecko_id: str   # CoinGecko "id" for /simple/price, e.g. "usd-coin"
    dexscreener: bool
    dexscreener_chain_id: str
    tags: list[str]
    verified: bool
    default_enabled: bool
    supported_pair_hints: list[dict]
    known_pool_candidates: dict


SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
WIF_MINT = "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"
POPCAT_MINT = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
CHAD_MINT = "8i93CHmhcqtCWMvaAdiTngwbQMQRKFW6g2ojnyhUpump"
SPX6900_MINT = "J3NKxxXZcnNiMjKw9hYb2K4LUxgwB6t1FtPtQVsv3KFr"
DOCS_PUMP_MINT = "7LSsEoJGhLeZzGvDofTdNg7M3JttxQqGWNLo6vWMpump"

NATIVE_TOKENS: Dict[str, TokenMeta] = {
    "SOL": {
        "asset": "sol",
        "symbol": "SOL",
        "name": "Solana",
        "display_name": "Solana",
        "mint": SOL_MINT,
        "decimals": 9,
        "coingecko_id": "solana",
        "dexscreener_chain_id": "solana",
        "tags": ["native", "blue_chip"],
        "verified": True,
        "default_enabled": True,
    },
}


# Known SPL mints (Solana)
TOKENS: Dict[str, TokenMeta] = {

    "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump": {
        "asset": "snp500",
        "symbol": "SNP500",
        "name": "SNP500",
        "display_name": "SNP500",
        "mint": "3yr17ZEE6wvCG7e3qD51XsfeSoSSKuCKptVissoopump",
        "dexscreener": True,
        "dexscreener_chain_id": "solana",
        "tags": ["meme"],
        "verified": False,
        "default_enabled": False,
    },
    # USDC (Solana)
    USDC_MINT: {
        "asset": "usdc",
        "symbol": "USDC",
        "name": "USD Coin",
        "display_name": "USD Coin",
        "mint": USDC_MINT,
        "decimals": 6,
        "coingecko_id": "usd-coin",
        "dexscreener_chain_id": "solana",
        "tags": ["stablecoin"],
        "verified": True,
        "default_enabled": True,
    },
    # USDT (Solana)
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {
        "asset": "usdt",
        "symbol": "USDT",
        "name": "Tether",
        "display_name": "Tether",
        "mint": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "decimals": 6,
        "coingecko_id": "tether",
        "dexscreener_chain_id": "solana",
        "tags": ["stablecoin"],
        "verified": True,
        "default_enabled": False,
    },
    # Example meme (only useful if you ever hold it)
    # BONK (Solana)
    BONK_MINT: {
        "asset": "bonk",
        "symbol": "BONK",
        "name": "Bonk",
        "display_name": "Bonk",
        "mint": BONK_MINT,
        "decimals": 5,
        "coingecko_id": "bonk",
        "dexscreener_chain_id": "solana",
        "tags": ["meme", "curated"],
        "verified": True,
        "default_enabled": True,
    },
    # dogwifhat (Solana)
    WIF_MINT: {
        "asset": "wif",
        "symbol": "WIF",
        "name": "dogwifhat",
        "display_name": "dogwifhat",
        "mint": WIF_MINT,
        "decimals": 6,
        "coingecko_id": "dogwifhat",
        "dexscreener_chain_id": "solana",
        "tags": ["meme", "curated"],
        "verified": True,
        "default_enabled": True,
    },
    # Popcat (Solana)
    POPCAT_MINT: {
        "asset": "popcat",
        "symbol": "POPCAT",
        "name": "Popcat",
        "display_name": "Popcat",
        "mint": POPCAT_MINT,
        "decimals": 9,
        "coingecko_id": "popcat",
        "dexscreener_chain_id": "solana",
        "tags": ["meme", "curated"],
        "verified": True,
        "default_enabled": True,
    },
    # CHAD (Solana, CoinGecko chad-3)
    CHAD_MINT: {
        "asset": "chad",
        "symbol": "CHAD",
        "name": "CHAD",
        "display_name": "CHAD",
        "mint": CHAD_MINT,
        "decimals": 6,
        "coingecko_id": "chad-3",
        "dexscreener_chain_id": "solana",
        "tags": ["meme", "curated"],
        "verified": True,
        "default_enabled": True,
    },
    # SPX6900 (Wormhole on Solana)
    SPX6900_MINT: {
        "asset": "spx6900",
        "symbol": "SPX6900",
        "name": "SPX6900",
        "display_name": "SPX6900",
        "mint": SPX6900_MINT,
        "decimals": 8,
        "coingecko_id": "spx6900",
        "dexscreener_chain_id": "solana",
        "tags": ["meme", "curated"],
        "verified": True,
        "default_enabled": True,
    },
    DOCS_PUMP_MINT: {
        "asset": "figure",
        "symbol": "FIGURE",
        "name": "Action Figure",
        "display_name": "Action Figure",
        "mint": DOCS_PUMP_MINT,
        "decimals": 6,
        "dexscreener": True,
        "dexscreener_chain_id": "solana",
        "tags": ["meme", "pumpfun", "pumpswap", "experimental"],
        "verified": False,
        "default_enabled": True,
        "supported_pair_hints": [
            {"input": "SOL", "output": "FIGURE"},
            {"input": "FIGURE", "output": "SOL"},
        ],
        "known_pool_candidates": {
            "pumpswap": [
                {
                    "address": "GseMAnNDvntR5uFePZ51yZBXzNSn7GdFPkfHwfr6d77J",
                    "name": "official-docs-example",
                    "base_mint": DOCS_PUMP_MINT,
                    "quote_mint": SOL_MINT,
                }
            ]
        },
    },
}


def _with_mint(mint: str, meta: TokenMeta) -> TokenMeta:
    out: TokenMeta = dict(meta)
    out.setdefault("mint", mint)
    out.setdefault("display_name", out.get("name") or out.get("symbol") or mint)
    return out


def get_token_meta_by_symbol(symbol: str, *, default_enabled_only: bool = True) -> TokenMeta | None:
    """
    Resolve a curated token by display symbol for swap/quote surfaces.

    This is intentionally registry-backed so API endpoints do not need their own
    growing token metadata list as meme-token coverage expands.
    """
    wanted = str(symbol or "").strip().upper()
    if not wanted:
        return None

    native = NATIVE_TOKENS.get(wanted)
    if native:
        if default_enabled_only and not native.get("default_enabled"):
            return None
        return _with_mint(native["mint"], native)

    for mint, meta in TOKENS.items():
        if (meta.get("symbol") or "").strip().upper() != wanted:
            continue
        if default_enabled_only and not meta.get("default_enabled"):
            return None
        return _with_mint(mint, meta)

    return None


def default_swap_token_meta_by_symbol() -> Dict[str, TokenMeta]:
    out: Dict[str, TokenMeta] = {}
    for symbol, meta in NATIVE_TOKENS.items():
        if meta.get("default_enabled"):
            out[symbol] = _with_mint(meta["mint"], meta)

    for mint, meta in TOKENS.items():
        symbol = (meta.get("symbol") or "").strip().upper()
        if symbol and meta.get("default_enabled"):
            out[symbol] = _with_mint(mint, meta)

    return out


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
