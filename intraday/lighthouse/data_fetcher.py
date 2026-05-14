"""yfinance wrapper with retry + in-memory caching.

This is the single chokepoint for all external market data. Every other module
should import from here, never directly from yfinance — so we can swap data
sources or layer in additional caching later without rippling changes.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import pandas as pd
import yfinance as yf

LOG = logging.getLogger("lighthouse.data_fetcher")

# Exceptions worth retrying. We don't retry ValueError/TypeError — those usually
# mean we're calling yfinance wrong, and retrying won't help.
RETRY_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def with_retry(
    op: Callable[[], Any],
    max_attempts: int = 3,
    base_delay: float = 0.5,
    retry_on: Tuple[Type[BaseException], ...] = RETRY_EXCEPTIONS,
) -> Any:
    """Run `op` with exponential backoff. Re-raises on persistent failure."""
    last_exc: Optional[BaseException] = None
    for attempt in range(max_attempts):
        try:
            return op()
        except retry_on as exc:
            last_exc = exc
            if attempt < max_attempts - 1 and base_delay > 0:
                time.sleep(base_delay * (2 ** attempt))
    assert last_exc is not None  # only reached if we exhausted retries
    raise last_exc


def concurrent_fetch(
    fn: Callable[[Any], Any],
    items: List[Any],
    max_workers: int = 5,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> List[Any]:
    """Run `fn` on each item across a thread pool. Returns results in input order.

    Per-item exceptions are caught and the slot is set to None. This matches the
    existing behavior of the sequential code path (where `get_quote_bundle` etc.
    already return None on failure) so callers can keep their filter-out-None logic.

    yfinance is I/O bound and threading works well. We default to 5 workers — Yahoo
    accepts roughly 5-10 concurrent requests before rate-limiting; the per-call
    retry handles transient throttles already.
    """
    n = len(items)
    if n == 0:
        return []
    results: List[Any] = [None] * n
    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {pool.submit(fn, item): i for i, item in enumerate(items)}
        for fut in as_completed(future_to_idx):
            i = future_to_idx[fut]
            try:
                results[i] = fut.result()
            except Exception:
                results[i] = None
            completed += 1
            if on_progress is not None:
                on_progress(completed, n)
    return results


class TTLCache:
    """Simple in-memory TTL cache. Process-local, not thread-safe."""

    def __init__(self, ttl_seconds: float = 3600):
        self._ttl = ttl_seconds
        self._store: dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self._ttl, value)

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        self.set(key, value)
        return value


# Shared caches. info has a short TTL (price/mcap change intraday); price history
# is cached longer because daily bars only update once a day.
_info_cache = TTLCache(ttl_seconds=600)         # 10 min
_history_cache = TTLCache(ttl_seconds=3600 * 6)  # 6 hr


def get_quote_bundle(ticker: str) -> Optional[dict]:
    """Return {mcap, price, adv_20d_dollar} for the filter stage, or None on failure.

    Uses a 60-day daily history to compute 20-day average dollar volume, and
    yfinance .info for market cap. Both are cached.
    """
    def fetch() -> Optional[dict]:
        t = yf.Ticker(ticker)
        info = t.info or {}

        hist = t.history(period="60d", auto_adjust=True)
        if hist is None or len(hist) < 21:
            return None

        price = float(hist["Close"].iloc[-1])
        # 20-day average dollar volume, using the prior 20 sessions (exclude today
        # to match how a pre-market or end-of-day scanner would see it).
        recent = hist.iloc[-21:-1]
        avg_dollar_volume = float((recent["Close"] * recent["Volume"]).mean())

        return {
            "ticker": ticker,
            "mcap": info.get("marketCap"),
            "price": price,
            "adv_20d_dollar": avg_dollar_volume,
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "business_summary": info.get("longBusinessSummary"),
        }

    try:
        return _info_cache.get_or_compute(
            f"quote:{ticker}",
            lambda: with_retry(fetch, max_attempts=3),
        )
    except Exception:
        return None


def get_daily_history(ticker: str, lookback_days: int = 400) -> Optional[pd.DataFrame]:
    """Return daily OHLCV for the technical stage, or None on failure."""
    def fetch() -> Optional[pd.DataFrame]:
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{lookback_days}d", auto_adjust=True)
        if hist is None or len(hist) < 50:
            return None
        return hist

    try:
        return _history_cache.get_or_compute(
            f"daily:{ticker}:{lookback_days}",
            lambda: with_retry(fetch, max_attempts=3),
        )
    except Exception:
        return None


def get_weekly_history(ticker: str, lookback_weeks: int = 156) -> Optional[pd.DataFrame]:
    """Return weekly OHLCV (3 years default) for Stage 2 checks, or None on failure."""
    def fetch() -> Optional[pd.DataFrame]:
        t = yf.Ticker(ticker)
        # yfinance: use a period long enough to cover the lookback in weeks
        days = lookback_weeks * 7 + 30
        hist = t.history(period=f"{days}d", interval="1wk", auto_adjust=True)
        if hist is None or len(hist) < 30:
            return None
        return hist

    try:
        return _history_cache.get_or_compute(
            f"weekly:{ticker}:{lookback_weeks}",
            lambda: with_retry(fetch, max_attempts=3),
        )
    except Exception:
        return None


_fundamentals_cache = TTLCache(ttl_seconds=3600 * 12)  # 12 hr — quarterly data is stable


def get_quarterly_fundamentals(ticker: str) -> Optional[dict]:
    """Return {quarterly_financials, quarterly_cashflow, info} for the fundamental
    scoring stage. Cached for 12 hours. Returns None only if every component is
    unavailable — partial data is allowed (the scorer handles missing pieces).
    """
    def fetch() -> Optional[dict]:
        t = yf.Ticker(ticker)
        qf = t.quarterly_financials
        qcf = t.quarterly_cashflow
        info = t.info or {}
        if (qf is None or len(qf) == 0) and (qcf is None or len(qcf) == 0) and not info:
            return None
        return {"quarterly_financials": qf, "quarterly_cashflow": qcf, "info": info}

    try:
        return _fundamentals_cache.get_or_compute(
            f"fundamentals:{ticker}",
            lambda: with_retry(fetch, max_attempts=3),
        )
    except Exception:
        return None


# =============================================================================
# Batched fetch via yf.download — many tickers in one HTTP round-trip
# =============================================================================
#
# Why batched: per-ticker `Ticker.history()` calls trigger Yahoo's crumb-based
# rate limiting at scale (we hit it on a full universe run). The `yf.download`
# endpoint uses a different backend that handles bulk requests gracefully —
# 100-500 tickers per call is normal.
# =============================================================================


def _parse_batched_download(df, tickers: List[str]) -> Dict[str, pd.DataFrame]:
    """Convert yf.download output into {ticker: DataFrame}.

    yf.download returns one of two shapes depending on len(tickers):
      - 1 ticker:  flat columns [Open, High, Low, Close, Volume]
      - N tickers: MultiIndex columns (ticker, field)

    Tickers whose data is entirely NaN (yfinance's failure marker) are omitted.
    """
    out: Dict[str, pd.DataFrame] = {}
    if df is None or len(df) == 0:
        return out

    if not isinstance(df.columns, pd.MultiIndex):
        # Single-ticker shape
        cleaned = df.dropna(how="all")
        if len(cleaned) > 0 and len(tickers) >= 1:
            out[tickers[0]] = cleaned
        return out

    # MultiIndex shape
    top_level = set(df.columns.get_level_values(0))
    for t in tickers:
        if t not in top_level:
            continue
        sub = df[t].dropna(how="all")
        if len(sub) > 0:
            out[t] = sub
    return out


def batch_download_daily(
    tickers: List[str],
    period: str = "400d",
    chunk_size: int = 100,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, pd.DataFrame]:
    """Fetch daily OHLCV for many tickers via yf.download in chunks.

    Returns {ticker: DataFrame}. Tickers that fail are omitted (no exception).
    """
    return _batch_download(tickers, period=period, interval="1d",
                           chunk_size=chunk_size, on_progress=on_progress)


def batch_download_weekly(
    tickers: List[str],
    weeks: int = 156,
    chunk_size: int = 100,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, pd.DataFrame]:
    """Fetch weekly OHLCV for many tickers via yf.download in chunks."""
    days = weeks * 7 + 30
    return _batch_download(tickers, period=f"{days}d", interval="1wk",
                           chunk_size=chunk_size, on_progress=on_progress)


def _batch_download(
    tickers: List[str],
    period: str,
    interval: str,
    chunk_size: int,
    on_progress: Optional[Callable[[int, int], None]],
) -> Dict[str, pd.DataFrame]:
    if not tickers:
        return {}
    result: Dict[str, pd.DataFrame] = {}
    n = len(tickers)
    for i in range(0, n, chunk_size):
        chunk = tickers[i:i + chunk_size]
        try:
            df = yf.download(
                tickers=chunk, period=period, interval=interval,
                group_by="ticker", auto_adjust=True, progress=False,
                threads=True,
            )
            result.update(_parse_batched_download(df, chunk))
        except Exception as exc:
            LOG.warning("batch download failed for chunk starting %s: %s", chunk[0], exc)
        if on_progress is not None:
            on_progress(min(i + chunk_size, n), n)
    return result


# =============================================================================
# Ticker info — the rate-limit-sensitive endpoint. Use sparingly + after a cheap
# pre-filter, never against the full universe.
# =============================================================================


def get_ticker_info(ticker: str) -> Optional[dict]:
    """Just the `.info` dict (mcap, industry, sector, business summary).

    Cached for 10 min via the shared _info_cache. Used in the new flow AFTER
    a price/ADV pre-filter has trimmed the universe — we want as few of these
    calls as possible because they're what trip Yahoo's rate limiter.
    """
    def fetch():
        t = yf.Ticker(ticker)
        info = t.info
        if not info:
            return None
        return {
            "ticker": ticker,
            "mcap": info.get("marketCap"),
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "business_summary": info.get("longBusinessSummary"),
        }

    try:
        return _info_cache.get_or_compute(
            f"info_only:{ticker}",
            lambda: with_retry(fetch, max_attempts=3),
        )
    except Exception:
        return None


def clear_caches() -> None:
    """Reset all caches. Mainly useful for testing."""
    _info_cache._store.clear()
    _history_cache._store.clear()
    _fundamentals_cache._store.clear()
