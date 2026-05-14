"""Technical signals for the Lighthouse scanner.

This module implements the Stage 2 binary flag (Stan Weinstein). The full
multi-factor score (0-10) is intentionally deferred to a later phase — we want
end-to-end plumbing working before piling on scoring complexity.

All five conditions must be true to fire:
  1. Weekly close > 30-week simple MA
  2. 30-week MA slope positive over the last 4 weekly bars
  3. Daily 50DMA > 200DMA (golden cross territory)
  4. Latest price within 15% of 52-week high
  5. Most recent weekly bar volume > 1.5 x 13-week avg volume
"""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

MA_WEEKS = 30
MA_SLOPE_LOOKBACK = 4
MA_SLOPE_MIN_PCT = 0.005   # require >0.5% rise across the lookback window
DAILY_SHORT_MA = 50
DAILY_LONG_MA = 200
NEAR_HIGH_THRESHOLD = 0.85   # price >= 85% of 52w high
VOLUME_LOOKBACK_WEEKS = 13
BREAKOUT_VOLUME_MULT = 1.5

TRADING_DAYS_PER_YEAR = 252


def _has_enough_data(daily: pd.DataFrame, weekly: pd.DataFrame) -> bool:
    if daily is None or weekly is None:
        return False
    if len(weekly) < MA_WEEKS + MA_SLOPE_LOOKBACK:
        return False
    if len(daily) < DAILY_LONG_MA:
        return False
    return True


def _weekly_close_above_30w_ma(weekly: pd.DataFrame) -> bool:
    ma = weekly["Close"].rolling(MA_WEEKS).mean().iloc[-1]
    return bool(weekly["Close"].iloc[-1] > ma)


def _ma_slope_positive(weekly: pd.DataFrame) -> bool:
    ma_series = weekly["Close"].rolling(MA_WEEKS).mean()
    recent = ma_series.iloc[-MA_SLOPE_LOOKBACK:]
    if recent.isna().any() or recent.iloc[0] <= 0:
        return False
    rise_pct = (recent.iloc[-1] / recent.iloc[0]) - 1.0
    return bool(rise_pct > MA_SLOPE_MIN_PCT)


def _golden_cross(daily: pd.DataFrame) -> bool:
    ma_short = daily["Close"].rolling(DAILY_SHORT_MA).mean().iloc[-1]
    ma_long = daily["Close"].rolling(DAILY_LONG_MA).mean().iloc[-1]
    return bool(ma_short > ma_long)


def _near_52w_high(daily: pd.DataFrame) -> bool:
    window = daily["Close"].iloc[-TRADING_DAYS_PER_YEAR:]
    high_52w = window.max()
    if high_52w == 0:
        return False
    return bool(daily["Close"].iloc[-1] >= NEAR_HIGH_THRESHOLD * high_52w)


def _breakout_volume(weekly: pd.DataFrame) -> bool:
    last_vol = weekly["Volume"].iloc[-1]
    # Average over the prior 13 weeks (exclude the current bar)
    prior = weekly["Volume"].iloc[-(VOLUME_LOOKBACK_WEEKS + 1):-1]
    if len(prior) == 0:
        return False
    avg = prior.mean()
    if avg <= 0:
        return False
    return bool(last_vol > BREAKOUT_VOLUME_MULT * avg)


def stage2_diagnostics(daily: pd.DataFrame, weekly: pd.DataFrame) -> Dict[str, bool]:
    """Return per-condition booleans. Useful for explaining 'why not a hit'.

    If inputs lack enough data, all flags are False.
    """
    if not _has_enough_data(daily, weekly):
        return {
            "weekly_close_above_30w_ma": False,
            "ma_slope_positive": False,
            "golden_cross": False,
            "near_52w_high": False,
            "breakout_volume": False,
        }
    return {
        "weekly_close_above_30w_ma": _weekly_close_above_30w_ma(weekly),
        "ma_slope_positive": _ma_slope_positive(weekly),
        "golden_cross": _golden_cross(daily),
        "near_52w_high": _near_52w_high(daily),
        "breakout_volume": _breakout_volume(weekly),
    }


def is_stage2_breakout(daily: pd.DataFrame, weekly: pd.DataFrame) -> bool:
    return all(stage2_diagnostics(daily, weekly).values())


# -----------------------------------------------------------------------------
# Descriptive metrics — not part of scoring; surfaced in the dashboard row to
# give a quick read on positioning without expanding the components panel.
# -----------------------------------------------------------------------------

def pct_below_3yr_high(weekly: pd.DataFrame) -> float:
    """Return (high - last) / high as a positive fraction. 0.0 means at the high.

    Uses the entire weekly close series we have (typically 3 years from
    `get_weekly_history`). Falls back to 0.0 on missing/insufficient data.
    """
    if weekly is None or len(weekly) < 2:
        return 0.0
    closes = weekly["Close"]
    high = float(closes.max())
    if high <= 0:
        return 0.0
    last = float(closes.iloc[-1])
    return max(0.0, (high - last) / high)


def pct_above_30dma(daily: pd.DataFrame) -> float:
    """Return (last - 30dma) / 30dma. Positive = above MA, negative = below.

    0.0 on missing/insufficient data.
    """
    if daily is None or len(daily) < 30:
        return 0.0
    ma30 = float(daily["Close"].rolling(30).mean().iloc[-1])
    if ma30 <= 0 or pd.isna(ma30):
        return 0.0
    last = float(daily["Close"].iloc[-1])
    return (last - ma30) / ma30
