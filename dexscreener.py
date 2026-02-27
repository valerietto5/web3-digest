from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import requests


@dataclass(frozen=True)
class DexPair:
    price_usd: float
    liquidity_usd: float
    url: str


def _to_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def fetch_best_pair_price_usd_solana(
    mint: str,
    *,
    min_liquidity_usd: float = 5_000.0,
    timeout: int = 10,
) -> Optional[DexPair]:
    """
    Returns best DexScreener pair for a Solana mint, chosen by highest liquidity USD,
    but only if liquidity >= min_liquidity_usd.

    Tries two endpoint shapes for robustness.
    """
    urls = [
        f"https://api.dexscreener.com/token-pairs/v1/solana/{mint}",
        f"https://api.dexscreener.com/latest/dex/tokens/{mint}",
    ]

    pairs: list[dict[str, Any]] = []

    for url in urls:
        try:
            r = requests.get(url, timeout=timeout)
            if not r.ok:
                continue
            data = r.json()

            # Endpoint A returns a list of pairs
            if isinstance(data, list):
                pairs = data
                break

            # Endpoint B returns {"pairs": [...]}
            if isinstance(data, dict) and isinstance(data.get("pairs"), list):
                pairs = data["pairs"]
                break
        except requests.RequestException:
            continue

    if not pairs:
        return None

    best: Optional[DexPair] = None
    for p in pairs:
        liq = _to_float((p.get("liquidity") or {}).get("usd"))
        price = _to_float(p.get("priceUsd"))
        link = str(p.get("url") or "")

        if liq < min_liquidity_usd or price <= 0:
            continue

        cand = DexPair(price_usd=price, liquidity_usd=liq, url=link)
        if best is None or cand.liquidity_usd > best.liquidity_usd:
            best = cand

    return best