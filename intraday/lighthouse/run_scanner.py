"""Lighthouse scanner — daily small-cap inflection-point scan.

Architecture (Option B: batched downloads):
  1. Fetch universe (5,656 US-listed common stocks)
  2. Batch download 400d daily OHLCV in chunks of 100 — one HTTP request per chunk
  3. Compute price + ADV from batched data; pre-filter to ~2,500 candidates
  4. Fetch `.info` per survivor (low concurrency, rate-limit sensitive)
  5. Apply mcap + industry gate → ~1,500 final survivors
  6. Batch download weekly OHLCV for survivors + SPY for relative strength
  7. Score technicals (Stage 2 + multi-factor) → ~100-200 candidates
  8. Fetch quarterly fundamentals per technical hit (small set, parallel)
  9. Apply fundamental gate → final hits
  10. Enrich + write CSV/JSON cache

The previous per-ticker `Ticker.history()` flow tripped Yahoo's crumb-based
rate limiter at full-universe scale. This flow uses `yf.download(group_by="ticker")`
which is a different endpoint Yahoo serves in bulk without per-call crumbs.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import warnings
from typing import Dict, List, Optional

import pandas as pd

# yfinance still uses Timestamp.utcnow() internally; silence its deprecation spam
warnings.filterwarnings("ignore", message=".*Timestamp.utcnow.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="yfinance")

from lighthouse import (
    data_fetcher, filters, fundamentals, narrative, ranker, scoring,
    technical, universe, writer,
)

SPY_TICKER = "SPY"
MIN_MULTI_FACTOR_SCORE = 6
MIN_FUNDAMENTAL_SCORE = 5
THEMES_DIR = os.path.join(os.path.dirname(__file__), "themes")

# Concurrency tuned for what Yahoo tolerates:
#   - Batched price downloads (yf.download): a different endpoint, handles bulk fine
#   - `.info` and quarterly endpoints: per-ticker scrapes, rate-limited aggressively
#
# At INFO_WORKERS=3 we hit "Invalid Crumb" errors after a few minutes and lost
# ~75% of .info responses. For a once-daily scan, serial calls are fine — the
# extra runtime (~7 minutes more) is a small price for >95% completeness.
INFO_WORKERS = 1
FUNDAMENTAL_WORKERS = 1
BATCH_CHUNK_SIZE = 100  # tickers per yf.download call

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
LOG = logging.getLogger("lighthouse")


def _make_progress_logger(label: str, every: int = 1):
    def cb(done: int, total: int) -> None:
        if done % every == 0 or done == total:
            LOG.info("%s %d/%d", label, done, total)
    return cb


# -----------------------------------------------------------------------------
# Pre-filter helpers (operate on already-fetched price data)
# -----------------------------------------------------------------------------

def compute_price_and_adv(daily: Optional[pd.DataFrame]) -> Optional[dict]:
    """Extract last price + 20-day avg dollar volume from a daily OHLCV frame.

    Returns None if there's insufficient data. Matches the old `get_quote_bundle`
    contract for these two fields.
    """
    if daily is None or len(daily) < 21:
        return None
    price = float(daily["Close"].iloc[-1])
    recent = daily.iloc[-21:-1]
    adv = float((recent["Close"] * recent["Volume"]).mean())
    return {"price": price, "adv_20d_dollar": adv}


def prefilter_by_price_adv(
    tickers: List[str],
    daily_data: Dict[str, pd.DataFrame],
) -> List[dict]:
    """Apply the cheap part of the gate (price + ADV thresholds) using already-
    fetched data. Returns one row per ticker that passes; the expensive `.info`
    fetch happens only on these survivors.
    """
    rows = []
    for t in tickers:
        quote = compute_price_and_adv(daily_data.get(t))
        if quote is None:
            continue
        if quote["price"] < filters.MIN_PRICE:
            continue
        if quote["adv_20d_dollar"] < filters.MIN_ADV_DOLLAR:
            continue
        rows.append({"ticker": t, **quote})
    return rows


# -----------------------------------------------------------------------------
# Technical evaluation — pure scoring on already-fetched data
# -----------------------------------------------------------------------------

def evaluate_technicals_from_data(
    tickers: List[str],
    daily_data: Dict[str, pd.DataFrame],
    weekly_data: Dict[str, pd.DataFrame],
    spy_daily: Optional[pd.DataFrame],
) -> pd.DataFrame:
    rows = []
    for t in tickers:
        daily = daily_data.get(t)
        weekly = weekly_data.get(t)
        if daily is None or weekly is None:
            continue
        diag = technical.stage2_diagnostics(daily, weekly)
        stage2 = all(diag.values())
        score = scoring.multi_factor_score(daily, spy_daily) if spy_daily is not None else {
            "trend": 0, "relative_strength": 0, "volume_accumulation": 0,
            "volatility_contraction": 0, "distance_from_high": 0, "total": 0,
        }
        if not (stage2 or score["total"] >= MIN_MULTI_FACTOR_SCORE):
            continue
        row = {"ticker": t, "stage2_flag": stage2}
        row.update(diag)
        row.update({f"score_{k}": v for k, v in score.items()})
        row["pct_below_3yr_high"] = technical.pct_below_3yr_high(weekly)
        row["pct_above_30dma"] = technical.pct_above_30dma(daily)
        rows.append(row)
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Fundamentals — still per-ticker (yfinance has no batched endpoint for these)
# -----------------------------------------------------------------------------

def _evaluate_one_fundamental(t: str) -> dict:
    bundle = data_fetcher.get_quarterly_fundamentals(t)
    if bundle is None:
        score = {"revenue_growth": 0, "margin_expansion": 0, "profitability_path": 0,
                 "pe_compression": 0, "earnings_beat": 0, "total": 0}
    else:
        score = fundamentals.growth_inflection_score(
            bundle["quarterly_financials"], bundle["quarterly_cashflow"], bundle["info"],
        )
    row = {"ticker": t}
    row.update({f"fund_{k}": v for k, v in score.items()})
    return row


def evaluate_fundamentals(tickers: List[str]) -> pd.DataFrame:
    results = data_fetcher.concurrent_fetch(
        _evaluate_one_fundamental,
        tickers,
        max_workers=FUNDAMENTAL_WORKERS,
        on_progress=_make_progress_logger("fundamentals", every=25),
    )
    rows = [r for r in results if r is not None]
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------------

def run(limit: int | None = None, close_of_day: bool = False, output_dir: str = DEFAULT_OUTPUT_DIR) -> pd.DataFrame:
    start = time.time()

    # ----- Step 1: universe -----
    LOG.info("step 1/8 — fetching universe")
    tickers = universe.fetch_universe(cache_dir=output_dir)
    LOG.info("universe size: %d", len(tickers))
    if limit:
        tickers = tickers[:limit]
        LOG.info("limited to first %d tickers", limit)

    # ----- Step 2: batch download daily OHLCV for everyone -----
    LOG.info("step 2/8 — batch downloading daily OHLCV (chunks of %d)", BATCH_CHUNK_SIZE)
    daily_data = data_fetcher.batch_download_daily(
        tickers, period="400d", chunk_size=BATCH_CHUNK_SIZE,
        on_progress=_make_progress_logger("daily batch"),
    )
    LOG.info("daily data: %d/%d tickers fetched", len(daily_data), len(tickers))

    # ----- Step 3: cheap pre-filter (price + ADV) -----
    LOG.info("step 3/8 — pre-filtering by price + ADV")
    prefilter_rows = prefilter_by_price_adv(tickers, daily_data)
    LOG.info("pre-filter survivors: %d", len(prefilter_rows))

    # ----- Step 4: fetch .info only for pre-filter survivors -----
    LOG.info("step 4/8 — fetching .info for %d survivors (workers=%d)",
             len(prefilter_rows), INFO_WORKERS)
    info_tickers = [r["ticker"] for r in prefilter_rows]
    info_results = data_fetcher.concurrent_fetch(
        data_fetcher.get_ticker_info,
        info_tickers,
        max_workers=INFO_WORKERS,
        on_progress=_make_progress_logger("info", every=100),
    )
    info_by_ticker = {r["ticker"]: r for r in info_results if r is not None}
    LOG.info(".info: %d/%d successful", len(info_by_ticker), len(prefilter_rows))

    # ----- Step 5: apply full liquidity gate (mcap + industry on top of pre-filter) -----
    LOG.info("step 5/8 — applying mcap + industry gate")
    bundles = []
    for row in prefilter_rows:
        info = info_by_ticker.get(row["ticker"])
        if info is None:
            continue
        bundles.append({**row, **{k: v for k, v in info.items() if k != "ticker"}})
    bundles_df = pd.DataFrame(bundles)
    gated = filters.apply_liquidity_gate(bundles_df)
    LOG.info("survived liquidity gate: %d", len(gated))
    if len(gated) == 0:
        LOG.warning("nothing survived the gate — writing empty results")
        writer.write_scan_results(pd.DataFrame(), output_dir=output_dir, close_of_day=close_of_day)
        return pd.DataFrame()

    # ----- Step 6: batch download weekly + SPY daily for technical scoring -----
    LOG.info("step 6/8 — batch downloading weekly OHLCV for %d survivors", len(gated))
    survivor_tickers = list(gated["ticker"])
    weekly_data = data_fetcher.batch_download_weekly(
        survivor_tickers, weeks=156, chunk_size=BATCH_CHUNK_SIZE,
        on_progress=_make_progress_logger("weekly batch"),
    )
    LOG.info("weekly data: %d/%d tickers fetched", len(weekly_data), len(survivor_tickers))
    LOG.info("fetching SPY for relative strength")
    spy_dict = data_fetcher.batch_download_daily([SPY_TICKER], period="400d")
    spy_daily = spy_dict.get(SPY_TICKER)
    if spy_daily is None:
        LOG.error("SPY fetch failed — relative strength scores will be 0")

    # ----- Step 7: technical evaluation (pure compute, no fetches) -----
    LOG.info("step 7/8 — technical evaluation (Stage 2 + multi-factor)")
    tech = evaluate_technicals_from_data(survivor_tickers, daily_data, weekly_data, spy_daily)
    LOG.info(
        "technical hits: %d (stage2=%d, score>=%d=%d)",
        len(tech),
        int(tech["stage2_flag"].sum()) if len(tech) else 0,
        MIN_MULTI_FACTOR_SCORE,
        int((tech["score_total"] >= MIN_MULTI_FACTOR_SCORE).sum()) if len(tech) else 0,
    )

    # ----- Step 8: fundamentals + final assembly -----
    LOG.info("step 8/8 — fundamentals for %d technical hits", len(tech))
    fund = evaluate_fundamentals(list(tech["ticker"])) if len(tech) else pd.DataFrame()

    if len(tech) > 0 and len(fund) > 0:
        hits = tech.merge(fund, on="ticker", how="left")
        keep = (hits["fund_total"] >= MIN_FUNDAMENTAL_SCORE) | hits["stage2_flag"]
        hits = hits[keep].reset_index(drop=True)
        LOG.info("after fundamental gate (>=%d): %d hits", MIN_FUNDAMENTAL_SCORE, len(hits))

        hits = hits.merge(
            gated[["ticker", "price", "mcap", "adv_20d_dollar",
                   "industry", "sector", "business_summary"]],
            on="ticker", how="left",
        )
        hits["combined_score"] = hits["score_total"] + hits["fund_total"]
        hits = hits.sort_values(
            ["stage2_flag", "combined_score"], ascending=[False, False]
        ).reset_index(drop=True)
        hits = narrative.enrich_dataframe(hits, themes_dir=THEMES_DIR)
        prior_cache = os.path.join(output_dir, writer.CACHE_JSON)
        hits = ranker.mark_new_today(hits, prior_cache_path=prior_cache)
    else:
        hits = pd.DataFrame()

    writer.write_scan_results(hits, output_dir=output_dir, close_of_day=close_of_day)
    LOG.info("done in %.1fs — %d hits written to %s", time.time() - start, len(hits), output_dir)
    return hits


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lighthouse small-cap scanner")
    parser.add_argument("--limit", type=int, default=None, help="cap the universe (for smoke testing)")
    parser.add_argument("--close-of-day", action="store_true", help="also write a dated archive copy")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # yf.download is chatty — keep its own logger at WARNING regardless
    logging.getLogger("yfinance").setLevel(logging.WARNING)

    run(limit=args.limit, close_of_day=args.close_of_day, output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
