#!/usr/bin/env python3
"""EOD scanner entry point. Run after market close (~4:30 PM)."""
from scanner.scanner import run_scan, save_watchlist

if __name__ == "__main__":
    print("Running EOD scan...")
    df = run_scan()
    if df.empty:
        print("No stocks passed all filters today.")
    else:
        csv_path, txt_path = save_watchlist(df)
        print(f"\nFound {len(df)} stocks.\nCSV: {csv_path}\nTOS import: {txt_path}")
        print("\n" + df[["ticker", "close", "gap_pct", "rvol", "trend", "ema", "setups"]]
              .to_string(index=False))
