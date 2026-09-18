"""Dual-account side-by-side trial: two independent bills plus the totals delta."""

from app.engines.helpers import money
from app.engines.tier_progressive import calc_bill


def compare_pair(left: dict, right: dict, tiers: list[dict], peak_factor: float) -> dict:
    """left/right: {"kwh": float, "peak": bool}. delta = right total - left total."""
    pf = float(peak_factor)
    left_bill = calc_bill(left["kwh"], tiers, pf if left.get("peak") else 1.0)
    right_bill = calc_bill(right["kwh"], tiers, pf if right.get("peak") else 1.0)
    return {
        "left": left_bill,
        "right": right_bill,
        "delta": money(right_bill["total"] - left_bill["total"]),
    }
