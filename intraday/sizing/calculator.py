import math
import json
import os
from typing import Optional
from config import ACCOUNT_SIZE, MAX_OPEN_RISK, MAX_POSITION_PCT

LAST_REGIME_PATH = "regime/last_regime.json"


def load_regime() -> Optional[dict]:
    """Load the last cached regime from last_regime.json. Returns None if missing."""
    if not os.path.exists(LAST_REGIME_PATH):
        return None
    with open(LAST_REGIME_PATH) as f:
        return json.load(f)


def calculate_size(
    entry: float,
    stop: float,
    setup: str,
    risk_pct: float,
    atr: Optional[float] = None,
    open_risk: float = 0.0,
    orb_high: Optional[float] = None,
) -> dict:
    """
    Calculate position size and output targets for a long or short trade.

    is_long determined by stop < entry (long) or stop > entry (short).
    open_risk: dollar amount already at risk in existing open positions (default 0).
    orb_high: for ORB setup only — warns if entry is >0.5% above this level.
    """
    is_long = stop < entry
    stop_distance = abs(entry - stop)

    if stop_distance == 0:
        return {"blocks": ["Stop price equals entry price — invalid trade"],
                "warnings": [], "shares": 0}

    budget = ACCOUNT_SIZE * risk_pct
    shares = math.floor(budget / stop_distance)
    dollar_risk = shares * stop_distance
    position_value = shares * entry

    if is_long:
        target_1 = entry + stop_distance
        target_2 = entry + 2 * stop_distance
    else:
        target_1 = entry - stop_distance
        target_2 = entry - 2 * stop_distance

    warnings, blocks = [], []

    if atr and stop_distance > atr:
        warnings.append(
            f"Stop distance ${stop_distance:.2f} > 1x ATR ${atr:.2f} — consider skipping"
        )

    if atr and abs(target_2 - entry) > 2 * atr:
        warnings.append(
            f"Target 2 is >{2}x ATR from entry — may not be reachable"
        )

    if position_value > ACCOUNT_SIZE * MAX_POSITION_PCT:
        warnings.append(
            f"Position value ${position_value:,.0f} > 25% of account — review"
        )

    if open_risk + dollar_risk > MAX_OPEN_RISK:
        blocks.append(
            f"Total open risk ${open_risk + dollar_risk:.0f} would exceed ${MAX_OPEN_RISK:.0f} cap"
        )

    if setup == "orb" and orb_high is not None and is_long:
        pct_above = (entry - orb_high) / orb_high
        if pct_above > 0.005:
            warnings.append(
                f"Entry is {pct_above*100:.2f}% above ORB high ${orb_high:.2f} — likely chasing"
            )

    return {
        "is_long": is_long,
        "shares": shares,
        "dollar_risk": round(dollar_risk, 2),
        "stop_distance": round(stop_distance, 4),
        "position_value": round(position_value, 2),
        "target_1": round(target_1, 4),
        "target_2": round(target_2, 4),
        "atr_multiples_stop": round(stop_distance / atr, 2) if atr else None,
        "atr_multiples_target": round(abs(target_2 - entry) / atr, 2) if atr else None,
        "warnings": warnings,
        "blocks": blocks,
    }
