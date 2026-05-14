"""Multi-factor technical score (0-10) for the Lighthouse scanner.

Five components, each scored 0-2:
  1. Trend          — MA stack (price > 50DMA > 150DMA > 200DMA)
  2. Relative strength — Mansfield-style stock/SPY ratio, with "RS line at new high"
  3. Volume accumulation — OBV slope + A/D Line at 6-month high
  4. Volatility contraction — Bollinger Band width at 6mo low + NR7 today
  5. Distance from 52W high — closer = higher score

The score is designed to complement the Stage 2 binary flag in technical.py.
Stage 2 catches "already breaking out" — high RS, high vol, MAs stacked.
This score also rewards "coiled spring" setups via the volatility contraction
component, so an early-stage accumulation candidate can surface even before
the Stage 2 trigger fires.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

# Lookback constants
TRADING_DAYS_PER_YEAR = 252
HALF_YEAR_DAYS = 130
QUARTER_YEAR_DAYS = 63
WEEKLY_LOOKBACK = 52

# Thresholds
RS_NEAR_HIGH_PCT = 0.95          # RS line within 5% of 52W high
AD_NEAR_HIGH_PCT = 0.95          # A/D line within 5% of 6mo high
AD_MEANINGFUL_RATIO = 0.05       # A/D 6mo range must exceed 5% of 6mo total volume
BB_WIDTH_MAX_RATIO = 1.10        # BB width within 10% of 6mo low counts as contracted
NEAR_HIGH_FULL = 0.75            # price >= 75% of 52W high → 2 pts
NEAR_HIGH_PARTIAL = 0.60         # price >= 60% of 52W high → 1 pt
NR_WINDOW = 7                    # NR7


# -----------------------------------------------------------------------------
# Helper indicators
# -----------------------------------------------------------------------------

def _compute_obv(daily: pd.DataFrame) -> pd.Series:
    direction = np.sign(daily["Close"].diff().fillna(0))
    return (direction * daily["Volume"]).cumsum()


def _compute_ad_line(daily: pd.DataFrame) -> pd.Series:
    h, l, c, v = daily["High"], daily["Low"], daily["Close"], daily["Volume"]
    rng = (h - l).replace(0, np.nan)
    mfm = ((c - l) - (h - c)) / rng
    mfm = mfm.fillna(0)
    return (mfm * v).cumsum()


def _bb_width(daily: pd.DataFrame, window: int = 20) -> pd.Series:
    """Bollinger Band width normalized by the middle band.
    width = (upper - lower) / middle = 4 * std / ma
    """
    ma = daily["Close"].rolling(window).mean()
    std = daily["Close"].rolling(window).std(ddof=0)
    return (4 * std) / ma


# -----------------------------------------------------------------------------
# 1. Trend
# -----------------------------------------------------------------------------

def score_trend(daily: pd.DataFrame) -> int:
    if daily is None or len(daily) < 200:
        return 0
    price = float(daily["Close"].iloc[-1])
    ma50 = float(daily["Close"].rolling(50).mean().iloc[-1])
    ma150 = float(daily["Close"].rolling(150).mean().iloc[-1])
    ma200 = float(daily["Close"].rolling(200).mean().iloc[-1])

    if any(np.isnan(x) for x in (ma50, ma150, ma200)):
        return 0

    if price > ma50 > ma150 > ma200:
        return 2
    if price > ma50 and ma50 > ma200:
        return 1
    return 0


# -----------------------------------------------------------------------------
# 2. Relative strength vs SPY
# -----------------------------------------------------------------------------

def score_relative_strength(stock_daily: pd.DataFrame, spy_daily: pd.DataFrame) -> int:
    if stock_daily is None or spy_daily is None:
        return 0
    if len(stock_daily) < TRADING_DAYS_PER_YEAR or len(spy_daily) < TRADING_DAYS_PER_YEAR:
        return 0

    stock = stock_daily["Close"].iloc[-TRADING_DAYS_PER_YEAR:].to_numpy(dtype=float)
    spy = spy_daily["Close"].iloc[-TRADING_DAYS_PER_YEAR:].to_numpy(dtype=float)
    if (spy <= 0).any():
        return 0
    rs_line = stock / spy

    current = rs_line[-1]
    a_year_ago = rs_line[0]
    if current <= a_year_ago:
        return 0

    rs_52w_high = rs_line.max()
    if rs_52w_high <= 0:
        return 0
    if current >= RS_NEAR_HIGH_PCT * rs_52w_high:
        return 2
    return 1


# -----------------------------------------------------------------------------
# 3. Volume accumulation
# -----------------------------------------------------------------------------

def score_volume_accumulation(daily: pd.DataFrame) -> int:
    if daily is None or len(daily) < HALF_YEAR_DAYS:
        return 0
    score = 0

    obv = _compute_obv(daily)
    # OBV slope: today vs ~52 trading days ago
    if obv.iloc[-1] > obv.iloc[-WEEKLY_LOOKBACK]:
        score += 1

    ad = _compute_ad_line(daily)
    ad_window = ad.iloc[-HALF_YEAR_DAYS:]
    vol_window = daily["Volume"].iloc[-HALF_YEAR_DAYS:]
    # Guard against floating-point noise: when high/low are symmetric around
    # close, MFM is theoretically 0 but accumulates ~1e-12 errors. Require the
    # A/D line's 6mo range to be a meaningful fraction of total traded volume
    # before crediting "near high".
    ad_range = ad_window.max() - ad_window.min()
    total_vol = vol_window.sum()
    is_meaningful = total_vol > 0 and ad_range >= AD_MEANINGFUL_RATIO * total_vol
    if is_meaningful and ad_window.max() > 0 and ad.iloc[-1] >= AD_NEAR_HIGH_PCT * ad_window.max():
        score += 1

    return score


# -----------------------------------------------------------------------------
# 4. Volatility contraction
# -----------------------------------------------------------------------------

def score_volatility_contraction(daily: pd.DataFrame) -> int:
    if daily is None or len(daily) < HALF_YEAR_DAYS:
        return 0
    score = 0

    width = _bb_width(daily).dropna()
    if len(width) >= HALF_YEAR_DAYS:
        recent_min = width.iloc[-HALF_YEAR_DAYS:].min()
        current = width.iloc[-1]
        if recent_min > 0 and current <= BB_WIDTH_MAX_RATIO * recent_min:
            score += 1

    # Normalized range (range/close) — comparing absolute ranges across days
    # spuriously triggers NR7 during geometric declines because shrinking prices
    # mechanically shrink absolute ranges.
    close = daily["Close"].replace(0, np.nan)
    norm_ranges = (daily["High"] - daily["Low"]) / close
    norm_ranges = norm_ranges.dropna()
    if len(norm_ranges) >= NR_WINDOW:
        last_window = norm_ranges.iloc[-NR_WINDOW:]
        if last_window.iloc[-1] == last_window.min() and last_window.min() > 0:
            score += 1

    return score


# -----------------------------------------------------------------------------
# 5. Distance from 52W high
# -----------------------------------------------------------------------------

def score_distance_from_high(daily: pd.DataFrame) -> int:
    if daily is None or len(daily) < TRADING_DAYS_PER_YEAR:
        return 0
    high_52w = float(daily["Close"].iloc[-TRADING_DAYS_PER_YEAR:].max())
    if high_52w <= 0:
        return 0
    pct = float(daily["Close"].iloc[-1]) / high_52w
    if pct >= NEAR_HIGH_FULL:
        return 2
    if pct >= NEAR_HIGH_PARTIAL:
        return 1
    return 0


# -----------------------------------------------------------------------------
# Aggregate
# -----------------------------------------------------------------------------

def multi_factor_score(stock_daily: pd.DataFrame, spy_daily: pd.DataFrame) -> Dict[str, int]:
    components = {
        "trend": score_trend(stock_daily),
        "relative_strength": score_relative_strength(stock_daily, spy_daily),
        "volume_accumulation": score_volume_accumulation(stock_daily),
        "volatility_contraction": score_volatility_contraction(stock_daily),
        "distance_from_high": score_distance_from_high(stock_daily),
    }
    components["total"] = sum(components.values())
    return components
