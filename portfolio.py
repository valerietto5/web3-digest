from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from datetime import datetime, timezone
from datetime import timedelta
from db import get_latest_balances_with_ts, get_latest_prices_with_ts, get_price_history, get_price_at_or_before



MAX_24H_GAP_HOURS = 30  # 24h target + 6h wiggle room


def _baseline_ok(target_dt: datetime, baseline_ts: str | None) -> bool:
    if not baseline_ts:
        return False
    bdt = datetime.fromisoformat(baseline_ts)
    gap_hours = (target_dt - bdt).total_seconds() / 3600.0
    if gap_hours < 0:
        return False  # baseline can't be after the target
    return gap_hours <= MAX_24H_GAP_HOURS


def _safe_pct(now_val: float, then_val: float) -> float | None:
    if then_val == 0:
        return None
    return (now_val - then_val) / then_val * 100.0


def _normalize_price_row(row) -> tuple[str | None, float | None]:
    """
    Normalize db.get_price_at_or_before output into (ts_iso, price_float).

    Supports:
      - (ts, price)
      - (price, ts)
      - {"ts": ..., "price": ...} / {"timestamp": ..., "value": ...}
      - None
    """
    if row is None:
        return None, None

    if isinstance(row, tuple) and len(row) >= 2:
        a, b = row[0], row[1]
        if isinstance(a, str):
            return a, float(b)
        if isinstance(b, str):
            return b, float(a)
        return None, None

    if isinstance(row, dict):
        ts = row.get("ts") or row.get("timestamp")
        px = row.get("price") or row.get("value")
        return (ts, float(px)) if (ts is not None and px is not None) else (None, None)

    return None, None






@dataclass(frozen=True)
class PortfolioPosition:
    asset: str
    amount: float
    balance_ts: str
    price: float
    price_ts: str
    value: float  # amount * price

    prev_price: float | None
    prev_price_ts: str | None
    price_change: float | None
    price_change_pct: float | None
    value_change: float | None
    # ---- 24h baseline (price-based) ----
    price_24h: float | None
    price_24h_ts: str | None
    price_change_24h: float | None
    price_change_pct_24h: float | None
    value_change_24h: float | None  # mark-to-market on current amount
    baseline_24h_valid: bool

@dataclass(frozen=True)
class PortfolioReport:
    account: str
    currency: str
    generated_at: str
    total_value: float
    positions: dict[str, PortfolioPosition]
    missing_prices: list[str]
    missing_balances: list[str]
    stale_prices: list[str]
    prices_updated: str
    balances_updated: str

    prev_total_value: float | None
    total_change: float | None
    total_change_pct: float | None
    change_label: str
    # ---- 24h portfolio deltas (mark-to-market on current holdings) ----
    target_24h: str
    mtm_total_value_24h: float | None
    mtm_total_change_24h: float | None
    mtm_total_change_pct_24h: float | None
    missing_24h_prices: list[str]
    change_24h_label: str



def human_age(ts: str, now: datetime) -> str:
    dt = datetime.fromisoformat(ts)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "in the future"  # defensive, should not happen

    if seconds < 10:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"

    days = hours // 24
    rem_hours = hours % 24
    return f"{days}d {rem_hours}h ago"



def compute_portfolio_report(
    account: str,
    assets: Iterable[str],
    currency: str = "usd",
) -> PortfolioReport:
    """
    Wallet-domain function:
    - pulls latest balances for account
    - pulls latest prices for assets in currency
    - computes per-asset values and total

    Returns a structured report suitable for UI.
    """
    assets = list(assets)
    generated_at = datetime.now(timezone.utc).isoformat()
    now_dt = datetime.fromisoformat(generated_at)
    target_24h_dt = now_dt - timedelta(hours=24)
    target_24h = target_24h_dt.isoformat()

    mtm_prev_total_24h = 0.0
    missing_24h_prices: list[str] = []

    price_ts_list: list[str] = []
    balance_ts_list: list[str] = []


    STALE_AFTER_MIN = 10
    stale_prices: list[str] = []

    prev_total = 0.0
    missing_prev_prices: list[str] = []


    balances = get_latest_balances_with_ts(account=account, assets=assets)
    prices = get_latest_prices_with_ts(assets=assets, currency=currency)


    positions: dict[str, PortfolioPosition] = {}
    total = 0.0

    missing_prices: list[str] = []
    missing_balances: list[str] = []

    for asset in assets:
        bal = balances.get(asset)
        if bal is None:
            missing_balances.append(asset)
            continue
        balance_ts, amt = bal
        balance_ts_list.append(balance_ts)
        


        pr = prices.get(asset)
        if pr is None:
            missing_prices.append(asset)
            continue
        price_ts, px = pr

        # ---- 24h baseline price (at or before target_24h) ----
        row_24h = get_price_at_or_before(asset=asset, currency=currency, ts=target_24h)
        p24_ts, p24 = _normalize_price_row(row_24h)

        baseline_24h_valid = _baseline_ok(target_24h_dt, p24_ts)

        price_24h = None
        price_24h_ts = None
        price_change_24h = None
        price_change_pct_24h = None
        value_change_24h = None

        if baseline_24h_valid and p24 is not None and p24_ts is not None:
            price_24h = float(p24)
            price_24h_ts = p24_ts
            price_change_24h = float(px) - float(p24)
            price_change_pct_24h = _safe_pct(float(px), float(p24))
            value_change_24h = float(amt) * price_change_24h

            # mark-to-market: what current holdings were worth at 24h-ago price
            mtm_prev_total_24h += float(amt) * float(p24)
        else:
            missing_24h_prices.append(asset)



        # previous price (2nd latest) for this asset
        hist2 = get_price_history(asset, currency=currency, limit=2)

        prev_price = None
        prev_price_ts = None
        price_change = None
        price_change_pct = None
        value_change = None

        if len(hist2) >= 2:
            prev_price_ts, prev_price = hist2[1]  # [0] is latest, [1] is previous
            price_change = float(px) - float(prev_price)

            # these should ALWAYS be computed if we have prev_price
            value_change = float(amt) * price_change
            prev_total += float(amt) * float(prev_price)

            # percent is optional (only if prev_price not zero)
            if float(prev_price) != 0:
                price_change_pct = (price_change / float(prev_price)) * 100.0
            else:
                missing_prev_prices.append(asset)
        else:
            missing_prev_prices.append(asset)

        price_ts_list.append(price_ts)

        price_dt = datetime.fromisoformat(price_ts)
        age_min = (now_dt - price_dt).total_seconds() / 60.0
        if age_min > STALE_AFTER_MIN:
            stale_prices.append(asset)
        if asset in stale_prices:
            price_24h = None
            price_24h_ts = None
            price_change_24h = None
            price_change_pct_24h = None
            value_change_24h = None
            baseline_24h_valid = False
            if asset not in missing_24h_prices:
                missing_24h_prices.append(asset)

    



        value = float(amt) * float(px)
        positions[asset] = PortfolioPosition(
            asset=asset,
            amount=float(amt),
            balance_ts=balance_ts,
            price=float(px),
            price_ts=price_ts,
            value=value,
            prev_price=prev_price,
            prev_price_ts=prev_price_ts,
            price_change=price_change,
            price_change_pct=price_change_pct,
            value_change=value_change,

            price_24h=price_24h,
            price_24h_ts=price_24h_ts,
            price_change_24h=price_change_24h,
            price_change_pct_24h=price_change_pct_24h,
            value_change_24h=value_change_24h,
            baseline_24h_valid=baseline_24h_valid,
        )
        total += value

    balances_updated = human_age(max(balance_ts_list), now_dt) if balance_ts_list else "unknown"
    prices_updated = human_age(max(price_ts_list), now_dt) if price_ts_list else "unknown"


    if missing_prev_prices: 
        prev_total_value = None 
        total_change = None 
        total_change_pct = None 
    else: 
        prev_total_value = prev_total 
        total_change = total - prev_total 
        total_change_pct = (total_change / prev_total * 100.0) if prev_total != 0 else None

    if missing_24h_prices or stale_prices:
        mtm_total_value_24h = None
        mtm_total_change_24h = None
        mtm_total_change_pct_24h = None
    else:
        mtm_total_value_24h = mtm_prev_total_24h
        mtm_total_change_24h = total - mtm_prev_total_24h
        mtm_total_change_pct_24h = _safe_pct(total, mtm_prev_total_24h)


    change_label = "since previous price snapshot"
    change_24h_label = "24h change (mark-to-market on current holdings; tolerant baseline)"
    

    return PortfolioReport(
        account=account,
        currency=currency,
        generated_at=generated_at,
        total_value=total,
        positions=positions,
        missing_prices=missing_prices,
        missing_balances=missing_balances,
        stale_prices=stale_prices,
        prices_updated=prices_updated,
        balances_updated=balances_updated,
        prev_total_value=prev_total_value,
        total_change=total_change,
        total_change_pct=total_change_pct,
        change_label=change_label,

        target_24h=target_24h,
        mtm_total_value_24h=mtm_total_value_24h,
        mtm_total_change_24h=mtm_total_change_24h,
        mtm_total_change_pct_24h=mtm_total_change_pct_24h,
        missing_24h_prices=missing_24h_prices,
        change_24h_label="24h change (mark-to-market on current holdings; tolerant baseline)",

    )
