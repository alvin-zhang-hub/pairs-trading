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
