import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Compute ATR using Wilder's smoothing. Returns the most recent ATR value.

    Returns float('nan') if the series has fewer than `period` rows — callers
    must guard against nan. fetch_ticker_data ensures >= 22 rows before calling.
    """
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return float(atr.iloc[-1])


def fetch_ticker_data(ticker: str, lookback_days: int = 60) -> Optional[dict]:
    """
    Fetch OHLCV data for a single ticker and compute all derived scan metrics.

    Returns None if data is unavailable, insufficient, or raises an exception.
    Float is best-effort: None when yfinance cannot provide it.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{lookback_days}d", auto_adjust=True)
        if len(hist) < 22:
            return None

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]
        open_ = hist["Open"]

        today_close = float(close.iloc[-1])
        today_open = float(open_.iloc[-1])
        prev_close = float(close.iloc[-2])
        today_volume = float(volume.iloc[-1])
        avg_volume_20d = float(volume.iloc[-21:-1].mean())

        atr_14 = compute_atr(high, low, close)
        gap_pct = abs(today_open - prev_close) / prev_close
        rvol = today_volume / avg_volume_20d if avg_volume_20d > 0 else 0.0

        float_shares = None
        try:
            info = t.info
            float_shares = info.get("floatShares")
        except Exception:
            pass

        return {
            "ticker": ticker,
            "close": today_close,
            "open_": today_open,
            "prev_close": prev_close,
            "volume": today_volume,
            "avg_volume_20d": avg_volume_20d,
            "atr_14": atr_14,
            "gap_pct": gap_pct,
            "rvol": rvol,
            "float_shares": float_shares,
        }
    except Exception:
        return None
