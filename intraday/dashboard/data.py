import json
import logging
import pathlib
from datetime import date

import pandas as pd
import yfinance as yf

CACHE_PATH = pathlib.Path(__file__).parent / "breadth_cache.json"
TICKERS = ["SPY", "QQQ", "IWM"]


def compute_pct_change(closes: pd.Series, periods: int) -> float:
    """Return (last / last-n) - 1. If series shorter than n+1, uses full length."""
    n = min(periods, len(closes) - 1)
    return float(closes.iloc[-1] / closes.iloc[-(n + 1)] - 1)


def compute_sparkline(closes: pd.Series, n: int = 5) -> list:
    """Return last n close prices as a plain list."""
    return closes.iloc[-n:].tolist()


def fetch_index_data() -> dict:
    """
    Download 1 month of daily closes for SPY, QQQ, IWM.
    Returns a dict with price, day/week/month pct changes, sparkline,
    and QQQ-vs-SPY / IWM-vs-SPY weekly deltas.

    On failure, raises so the caller can render an error banner.
    """
    raw = yf.download(
        TICKERS, period="3mo", auto_adjust=True, progress=False, threads=True
    )
    closes = raw["Close"]  # DataFrame: rows=dates, cols=SPY/QQQ/IWM

    result = {}
    for ticker in TICKERS:
        s = closes[ticker].dropna()
        result[ticker] = {
            "price":      round(float(s.iloc[-1]), 2),
            "day_pct":    compute_pct_change(s, 1),
            "week_pct":   compute_pct_change(s, 5),
            "month_pct":  compute_pct_change(s, 21),
            "sparkline":  compute_sparkline(s),
            "week_return": compute_pct_change(s, 5),
        }

    result["qqq_vs_spy"] = result["QQQ"]["week_return"] - result["SPY"]["week_return"]
    result["iwm_vs_spy"] = result["IWM"]["week_return"] - result["SPY"]["week_return"]
    return result
