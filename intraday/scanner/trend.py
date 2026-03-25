import pandas as pd
from typing import Literal

TrendLabel = Literal["Uptrend", "Downtrend", "Sideways"]


def find_swing_highs(high: pd.Series, lookback: int = 2) -> list:
    """
    Return integer positions of swing highs using a (2*lookback+1)-bar fractal.
    A swing high at position i: high[i] strictly greater than all candles within `lookback` on each side.
    """
    arr = high.values
    result = []
    for i in range(lookback, len(arr) - lookback):
        if all(arr[i] > arr[i - k] for k in range(1, lookback + 1)) and \
           all(arr[i] > arr[i + k] for k in range(1, lookback + 1)):
            result.append(i)
    return result


def find_swing_lows(low: pd.Series, lookback: int = 2) -> list:
    """Return integer positions of swing lows (inverse of find_swing_highs)."""
    arr = low.values
    result = []
    for i in range(lookback, len(arr) - lookback):
        if all(arr[i] < arr[i - k] for k in range(1, lookback + 1)) and \
           all(arr[i] < arr[i + k] for k in range(1, lookback + 1)):
            result.append(i)
    return result


def classify_price_structure(swing_highs_vals: list, swing_lows_vals: list) -> str:
    """
    Classify price structure from ordered swing point value lists.
    Requires at least 3 of each; returns 'Sideways' if fewer exist.

    Uptrend:   >= 2 of last 3 swing highs are HH AND >= 2 of last 3 swing lows are HL
    Downtrend: >= 2 of last 3 swing highs are LH AND >= 2 of last 3 swing lows are LL
    """
    if len(swing_highs_vals) < 3 or len(swing_lows_vals) < 3:
        return "Sideways"

    highs = swing_highs_vals[-3:]
    lows = swing_lows_vals[-3:]

    hh = sum(highs[i] > highs[i - 1] for i in range(1, 3))
    hl = sum(lows[i] > lows[i - 1] for i in range(1, 3))
    lh = sum(highs[i] < highs[i - 1] for i in range(1, 3))
    ll = sum(lows[i] < lows[i - 1] for i in range(1, 3))

    if hh >= 2 and hl >= 2:
        return "Uptrend"
    if lh >= 2 and ll >= 2:
        return "Downtrend"
    return "Sideways"


def classify_trend(
    hist: pd.DataFrame,
    ema_20: pd.Series,
    ema_50: pd.Series,
    window: int = 20,
) -> TrendLabel:
    """
    Classify trend using last `window` candles of daily OHLCV data.

    hist must have columns: High, Low, Close.
    ema_20 and ema_50 are pre-computed Series aligned to hist.index.
    Returns 'Sideways' if fewer than 3 swing points found in window.
    """
    recent = hist.tail(window)
    ema_20_last = float(ema_20.reindex(recent.index).iloc[-1])
    ema_50_last = float(ema_50.reindex(recent.index).iloc[-1])
    if pd.isna(ema_20_last) or pd.isna(ema_50_last):
        return "Sideways"
    close_last = float(recent["Close"].iloc[-1])

    price_above_both = close_last > ema_20_last and close_last > ema_50_last
    ema_20_above_50 = ema_20_last > ema_50_last
    price_below_both = close_last < ema_20_last and close_last < ema_50_last
    ema_20_below_50 = ema_20_last < ema_50_last

    sh_idxs = find_swing_highs(recent["High"])
    sl_idxs = find_swing_lows(recent["Low"])
    sh_vals = [float(recent["High"].iloc[i]) for i in sh_idxs]
    sl_vals = [float(recent["Low"].iloc[i]) for i in sl_idxs]

    structure = classify_price_structure(sh_vals, sl_vals)

    if price_above_both and ema_20_above_50 and structure == "Uptrend":
        return "Uptrend"
    if price_below_both and ema_20_below_50 and structure == "Downtrend":
        return "Downtrend"
    return "Sideways"


def get_eligible_setups(trend: TrendLabel) -> list:
    """Return setup names the stock is eligible for based on its trend."""
    mapping = {
        "Uptrend": ["orb_long", "ema_pullback_long", "vwap_reclaim_long"],
        "Downtrend": ["ema_pullback_short", "vwap_reclaim_short"],
        "Sideways": ["vwap_reclaim_long", "vwap_reclaim_short"],
    }
    return mapping.get(trend, [])
