import logging
import requests
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from config import SECTOR_GROWTH, SECTOR_DEFENSIVE, CBOE_BASE_URL, BREADTH_EMA_PERIOD, BREADTH_MIN_VALID_PCT


def fetch_qqq_data(lookback_days: int = 60) -> pd.DataFrame:
    """Fetch QQQ daily OHLCV and compute 20/50 EMA columns."""
    hist = yf.Ticker("QQQ").history(period=f"{lookback_days}d", auto_adjust=True)
    hist["ema_20"] = hist["Close"].ewm(span=20, adjust=False).mean()
    hist["ema_50"] = hist["Close"].ewm(span=50, adjust=False).mean()
    return hist


def fetch_vix() -> float:
    """Return the most recent VIX closing value."""
    hist = yf.Ticker("^VIX").history(period="5d", auto_adjust=True)
    return float(hist["Close"].iloc[-1])


def fetch_sector_returns(lookback_days: int = 5) -> dict:
    """
    Compute `lookback_days`-day return for each growth and defensive sector ETF.
    Returns {ticker: return_as_decimal}. Silently skips tickers that fail.
    """
    tickers = SECTOR_GROWTH + SECTOR_DEFENSIVE
    result = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(
                period=f"{lookback_days + 5}d", auto_adjust=True
            )
            if len(hist) >= lookback_days + 1:
                start = float(hist["Close"].iloc[-(lookback_days + 1)])
                end = float(hist["Close"].iloc[-1])
                result[ticker] = (end - start) / start
        except Exception:
            pass
    return result


def fetch_sp500_breadth(sp500_tickers: list, ema_period: int = None) -> Optional[float]:
    """
    Compute % of S&P 500 stocks with close > their 20-day EMA.
    Returns None if fewer than BREADTH_MIN_VALID_PCT of tickers return valid data.
    """
    if ema_period is None:
        ema_period = BREADTH_EMA_PERIOD

    above = 0
    total_valid = 0
    for ticker in sp500_tickers:
        try:
            hist = yf.Ticker(ticker).history(period="30d", auto_adjust=True)
            if len(hist) < ema_period + 1:
                continue
            ema = hist["Close"].ewm(span=ema_period, adjust=False).mean()
            if float(hist["Close"].iloc[-1]) > float(ema.iloc[-1]):
                above += 1
            total_valid += 1
        except Exception:
            pass

    min_valid = len(sp500_tickers) * BREADTH_MIN_VALID_PCT
    if total_valid < min_valid:
        logging.warning(
            "Breadth: only %d/%d tickers returned data — skipping factor",
            total_valid, len(sp500_tickers),
        )
        return None
    return above / total_valid


def fetch_put_call_ratio(lookback_days: int = 5) -> Optional[float]:
    """
    Download CBOE daily equity P/C CSV files for the last `lookback_days` trading days.
    Returns MA of equity-only P/C ratio, or None if CBOE is unavailable.

    CBOE URL format: https://www.cboe.com/us/options/market_statistics/daily/options_YYYYMMDD.csv
    The equity-only P/C ratio is in the row containing 'EQUITY'.
    """
    ratios = []
    check_date = date.today()
    attempts = 0
    while len(ratios) < lookback_days and attempts < 20:
        date_str = check_date.strftime("%Y%m%d")
        url = f"{CBOE_BASE_URL}options_{date_str}.csv"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                lines = resp.text.strip().split("\n")
                # Find header to locate EQUITY column, or fall back to last column
                header = lines[0].upper().split(",") if lines else []
                equity_col = header.index("EQUITY") if "EQUITY" in header else -1
                for line in lines[1:]:
                    parts = line.split(",")
                    if len(parts) > abs(equity_col):
                        try:
                            val = float(parts[equity_col].strip())
                            ratios.append(val)
                            break
                        except ValueError:
                            pass
        except Exception:
            pass
        check_date -= timedelta(days=1)
        attempts += 1

    if not ratios:
        logging.warning("Put/Call ratio: CBOE fetch failed — skipping factor")
        return None
    return sum(ratios) / len(ratios)
