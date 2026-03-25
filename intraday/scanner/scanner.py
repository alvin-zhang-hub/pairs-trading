import logging
import os
import yfinance as yf
import pandas as pd
from datetime import date
from typing import Optional
from scanner.fetcher import fetch_ticker_data
from scanner.filters import apply_filters
from scanner.trend import classify_trend, get_eligible_setups
from config import SP500_WIKI_URL


def get_universe() -> list:
    """Fetch S&P 500 tickers from Wikipedia. Returns empty list on failure."""
    import io, requests
    try:
        resp = requests.get(SP500_WIKI_URL, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        tickers = tables[0]["Symbol"].tolist()
        return [t.replace(".", "-") for t in tickers]
    except Exception as e:
        logging.error("Failed to fetch S&P 500 universe: %s", e)
        return []


def run_scan(tickers: Optional[list] = None) -> pd.DataFrame:
    """
    Run the full EOD scan pipeline.
    Returns a DataFrame sorted by RVOL descending, or empty DataFrame if no stocks pass.
    """
    if tickers is None:
        tickers = get_universe()

    rows = []
    for ticker in tickers:
        data = fetch_ticker_data(ticker)
        if data:
            rows.append(data)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = apply_filters(df)
    if df.empty:
        return df

    trends, setups_list = [], []
    for _, row in df.iterrows():
        try:
            hist = yf.Ticker(row["ticker"]).history(period="60d", auto_adjust=True)
            ema_20 = hist["Close"].ewm(span=20, adjust=False).mean()
            ema_50 = hist["Close"].ewm(span=50, adjust=False).mean()
            trend = classify_trend(hist, ema_20, ema_50)
        except Exception as e:
            logging.warning("Trend classification failed for %s: %s", row["ticker"], e)
            trend = "Sideways"
        trends.append(trend)
        setups_list.append(", ".join(get_eligible_setups(trend)))

    df["trend"] = trends
    df["setups"] = setups_list
    return df.sort_values("rvol", ascending=False).reset_index(drop=True)


def save_watchlist(df: pd.DataFrame, output_dir: str = ".") -> tuple:
    """
    Write ranked watchlist to CSV and plain-text file.
    Returns (csv_path, txt_path).
    """
    today = date.today().strftime("%Y-%m-%d")
    csv_path = os.path.join(output_dir, f"watchlist_{today}.csv")
    txt_path = os.path.join(output_dir, "watchlist.txt")

    out = df[["ticker", "close", "gap_pct", "rvol", "atr_14", "atr_pct",
              "float_shares", "trend", "ema", "setups"]].copy()
    out["gap_pct"] = (out["gap_pct"] * 100).round(2)
    out["atr_pct"] = (out["atr_pct"] * 100).round(2)
    out["rvol"] = out["rvol"].round(2)
    out.columns = ["Ticker", "Price", "Gap%", "RVOL", "ATR", "ATR%",
                   "Float", "Trend", "EMA", "Setups"]
    out.to_csv(csv_path, index=False)

    with open(txt_path, "w") as f:
        f.write("\n".join(df["ticker"].tolist()))

    return csv_path, txt_path
