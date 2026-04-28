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
    Download 3 months of daily closes for SPY, QQQ, IWM.
    Returns a dict with price, day/week/month pct changes, sparkline,
    and QQQ-vs-SPY / IWM-vs-SPY weekly deltas.

    On failure, raises so the caller can render an error banner.
    """
    raw = yf.download(
        TICKERS, period="3mo", auto_adjust=True, progress=False, threads=True
    )
    closes = raw["Close"]  # DataFrame: rows=dates, cols=SPY/QQQ/IWM

    missing = [t for t in TICKERS if t not in closes.columns]
    if missing:
        raise ValueError(f"yfinance did not return data for: {missing}")

    result = {}
    for ticker in TICKERS:
        s = closes[ticker].dropna()
        result[ticker] = {
            "price":      round(float(s.iloc[-1]), 2),
            "day_pct":    compute_pct_change(s, 1),
            "week_pct":   compute_pct_change(s, 5),
            "month_pct":  compute_pct_change(s, 21),
            "sparkline":  compute_sparkline(s),
        }

    result["qqq_vs_spy"] = result["QQQ"]["week_pct"] - result["SPY"]["week_pct"]
    result["iwm_vs_spy"] = result["IWM"]["week_pct"] - result["SPY"]["week_pct"]
    return result


def _load_sp500_tickers() -> list:
    """Reuse existing Wikipedia fetch; fall back to a short hardcoded list."""
    import io
    import requests
    try:
        resp = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        return [t.replace(".", "-") for t in tables[0]["Symbol"].tolist()]
    except Exception as exc:
        logging.warning("S&P 500 ticker list failed (%s) — using fallback list", exc)
        return [
            "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B",
            "UNH", "XOM", "JPM", "JNJ", "V", "PG", "MA", "HD", "CVX", "MRK",
            "ABBV", "LLY",
        ]


def _compute_today_breadth(tickers: list) -> list | None:
    """
    Batch-download 1 year of closes for all tickers. Compute:
      - pct_positive_today: % with close > prior close
      - pct_above_10sma:   % above 10-day SMA
      - pct_above_20sma:   % above 20-day SMA
      - pct_above_200sma:  % above 200-day SMA
    Returns a list of dicts (one per YTD date), or None on failure.
    """
    try:
        raw = yf.download(
            tickers, period="1y", auto_adjust=True, progress=False, threads=True
        )
        closes = raw["Close"].dropna(how="all")
        if closes.empty:
            return None

        valid = closes.notna()
        n_valid = valid.sum(axis=1).replace(0, pd.NA)

        sma10  = closes.rolling(10).mean()
        sma20  = closes.rolling(20).mean()
        sma200 = closes.rolling(200).mean()

        ytd_start = date(date.today().year, 1, 1).isoformat()
        closes.index = closes.index.strftime("%Y-%m-%d")
        sma10.index  = sma10.index.strftime("%Y-%m-%d")
        sma20.index  = sma20.index.strftime("%Y-%m-%d")
        sma200.index = sma200.index.strftime("%Y-%m-%d")
        valid.index  = valid.index.strftime("%Y-%m-%d")

        series = []
        idx_list = closes.index.tolist()
        for i, d_str in enumerate(idx_list):
            if d_str < ytd_start:
                continue
            if i == 0:
                continue
            row   = closes.loc[d_str]
            prev  = closes.iloc[i - 1]
            vrow  = valid.loc[d_str]
            n     = int(vrow.sum())
            if n == 0:
                continue
            series.append({
                "date":               d_str,
                "pct_positive_today": round(float(((row > prev) & vrow).sum() / n), 4),
                "pct_above_10sma":    round(float(((row > sma10.loc[d_str]) & vrow).sum() / n), 4),
                "pct_above_20sma":    round(float(((row > sma20.loc[d_str]) & vrow).sum() / n), 4),
                "pct_above_200sma":   round(float(((row > sma200.loc[d_str]) & vrow).sum() / n), 4),
            })
        return series
    except Exception as exc:
        logging.error("Breadth fetch failed: %s", exc)
        return None


def get_breadth_series(cache_path: pathlib.Path = CACHE_PATH) -> list:
    """
    Return YTD breadth series as a list of dicts.
    Reads from cache if date matches today; otherwise re-fetches and rewrites cache.
    Returns empty list on complete failure.
    """
    today = date.today().isoformat()

    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            if cached.get("date") == today:
                return cached["series"]
        except Exception:
            pass

    tickers = _load_sp500_tickers()
    series = _compute_today_breadth(tickers)
    if series is None:
        # Return whatever was in the old cache even if stale
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text()).get("series", [])
            except Exception:
                pass
        return []

    payload = {"date": today, "series": series}
    cache_path.write_text(json.dumps(payload, indent=2))
    return series
