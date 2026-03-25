import json
import logging
import pathlib
import pandas as pd
from datetime import date
from regime.fetcher import (
    fetch_qqq_data, fetch_vix, fetch_sector_returns,
    fetch_sp500_breadth, fetch_put_call_ratio,
)
from regime.scorer import compute_regime
from config import SP500_WIKI_URL

LAST_REGIME_PATH = pathlib.Path(__file__).parent / "last_regime.json"

SCORE_LABELS = {
    1: "+1", 0: " 0", -1: "-1",
}


def load_sp500_tickers() -> list:
    try:
        tables = pd.read_html(SP500_WIKI_URL)
        return [t.replace(".", "-") for t in tables[0]["Symbol"].tolist()]
    except Exception as e:
        logging.error("Failed to load S&P 500 tickers: %s", e)
        return []


def print_regime(result: dict) -> None:
    s = result["scores"]
    d = result["factor_details"]
    print(f"\n=== MARKET REGIME: {date.today()} ===\n")
    print(f"QQQ EMA Alignment:    {SCORE_LABELS[s['qqq_ema']]}  "
          f"(close={d['qqq_close']:.1f}, ema20={d['ema_20']:.1f}, ema50={d['ema_50']:.1f})")
    print(f"QQQ Price Structure:  {SCORE_LABELS[s['qqq_structure']]}")
    print(f"VIX:                  {SCORE_LABELS[s['vix']]}  ({d['vix']:.1f})")
    breadth_str = f"{d['breadth']*100:.0f}%" if d["breadth"] else "N/A (skipped)"
    print(f"Market Breadth:       {SCORE_LABELS[s['breadth']]}  ({breadth_str} above 20 EMA)")
    growth_avg = sum(d["sector_returns"].get(t, 0) for t in ["XLK", "XLY"]) / 2
    def_avg = sum(d["sector_returns"].get(t, 0) for t in ["XLU", "XLP", "XLV"]) / 3
    print(f"Sector Rotation:      {SCORE_LABELS[s['sector_rotation']]}  "
          f"(growth {growth_avg*100:+.2f}% vs defensive {def_avg*100:+.2f}% over 5d)")
    pc_str = f"{d['pc_ratio']:.2f}" if d["pc_ratio"] else "N/A (skipped)"
    print(f"Put/Call (5-day MA):  {SCORE_LABELS[s['put_call']]}  ({pc_str})")
    print(f"\nTOTAL SCORE:          {result['total_score']:+d}  →  {result['regime'].upper()}")
    print(f"RISK PER TRADE:       {result['risk_pct']*100:.2f}%  "
          f"(${result['dollar_risk']:.0f} on $20k)")
    long_str = ", ".join(result["long_setups"]) if result["long_setups"] else "OFF"
    short_str = ", ".join(result["short_setups"]) if result["short_setups"] else "OFF"
    print(f"LONG SETUPS:          {long_str}")
    print(f"SHORT SETUPS:         {short_str}\n")


def run_regime() -> dict:
    """Fetch all data, compute regime, print to terminal, cache to JSON."""
    print("Fetching market data...")
    qqq_hist = fetch_qqq_data()
    vix = fetch_vix()
    sector_returns = fetch_sector_returns()
    sp500_tickers = load_sp500_tickers()
    print(f"Computing breadth across {len(sp500_tickers)} S&P 500 stocks (may take ~2 min)...")
    breadth = fetch_sp500_breadth(sp500_tickers)
    pc_ratio = fetch_put_call_ratio()

    result = compute_regime(qqq_hist, vix, breadth, sector_returns, pc_ratio)
    print_regime(result)

    cache = {
        "date": date.today().isoformat(),
        "regime": result["regime"],
        "risk_pct": result["risk_pct"],
        "dollar_risk": result["dollar_risk"],
        "total_score": result["total_score"],
        "long_setups": result["long_setups"],
        "short_setups": result["short_setups"],
    }
    with open(LAST_REGIME_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    return result
