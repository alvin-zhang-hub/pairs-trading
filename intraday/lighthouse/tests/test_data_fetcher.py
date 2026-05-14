import time

import numpy as np
import pandas as pd
import pytest

from lighthouse.data_fetcher import (
    TTLCache,
    _parse_batched_download,
    concurrent_fetch,
    with_retry,
)


class TestWithRetry:
    def test_returns_value_on_first_success(self):
        calls = []

        def op():
            calls.append(1)
            return "ok"

        assert with_retry(op, max_attempts=3, base_delay=0) == "ok"
        assert len(calls) == 1

    def test_retries_on_exception_and_eventually_succeeds(self):
        calls = []

        def op():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("boom")
            return "ok"

        assert with_retry(op, max_attempts=5, base_delay=0) == "ok"
        assert len(calls) == 3

    def test_raises_when_attempts_exhausted(self):
        calls = []

        def op():
            calls.append(1)
            raise ConnectionError("persistent")

        with pytest.raises(ConnectionError):
            with_retry(op, max_attempts=3, base_delay=0)
        assert len(calls) == 3

    def test_does_not_retry_on_value_error_by_default(self):
        # ValueError is not in the retry set — should propagate immediately
        calls = []

        def op():
            calls.append(1)
            raise ValueError("bad input")

        with pytest.raises(ValueError):
            with_retry(op, max_attempts=5, base_delay=0)
        assert len(calls) == 1


class TestTTLCache:
    def test_returns_cached_value(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("k", 42)
        assert cache.get("k") == 42

    def test_returns_none_for_missing_key(self):
        cache = TTLCache(ttl_seconds=60)
        assert cache.get("missing") is None

    def test_expires_after_ttl(self):
        cache = TTLCache(ttl_seconds=0.05)
        cache.set("k", "val")
        time.sleep(0.1)
        assert cache.get("k") is None

    def test_get_or_compute_caches_callable_result(self):
        calls = []

        def compute():
            calls.append(1)
            return "computed"

        cache = TTLCache(ttl_seconds=60)
        assert cache.get_or_compute("k", compute) == "computed"
        assert cache.get_or_compute("k", compute) == "computed"
        assert len(calls) == 1

    def test_different_keys_compute_independently(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") == 1
        assert cache.get("b") == 2


class TestConcurrentFetch:
    def test_returns_results_in_input_order(self):
        result = concurrent_fetch(lambda x: x * 2, [1, 2, 3, 4, 5], max_workers=3)
        assert result == [2, 4, 6, 8, 10]

    def test_handles_per_item_exception_with_none(self):
        def maybe_fail(x):
            if x == 3:
                raise ValueError("boom")
            return x * 2

        result = concurrent_fetch(maybe_fail, [1, 2, 3, 4, 5], max_workers=3)
        assert result == [2, 4, None, 8, 10]

    def test_empty_list_returns_empty(self):
        assert concurrent_fetch(lambda x: x * 2, [], max_workers=3) == []

    def test_single_item(self):
        assert concurrent_fetch(lambda x: x * 2, [42], max_workers=3) == [84]

    def test_concurrent_is_faster_than_sequential(self):
        def slow(x):
            time.sleep(0.05)
            return x

        start = time.time()
        concurrent_fetch(slow, list(range(10)), max_workers=10)
        elapsed = time.time() - start
        # 10 × 0.05 = 0.5s sequential. With 10 workers should be ~0.05-0.1s
        assert elapsed < 0.25, f"expected concurrent execution, got {elapsed:.2f}s"

    def test_progress_callback_invoked_for_each_item(self):
        calls = []

        def on_progress(done, total):
            calls.append((done, total))

        concurrent_fetch(lambda x: x, [1, 2, 3], max_workers=2, on_progress=on_progress)
        assert len(calls) == 3
        # Last call should report all done
        assert calls[-1] == (3, 3)
        # All calls should report total=3
        assert all(c[1] == 3 for c in calls)


# Helpers for synthesizing yf.download output shapes
def _make_multi_ticker_df(tickers, n_bars=10, all_nan=()):
    """Build a MultiIndex DataFrame matching yf.download(group_by='ticker') output.

    `all_nan`: iterable of ticker symbols whose data should be entirely NaN
    (simulating yfinance's behavior for tickers that failed to fetch).
    """
    cols = pd.MultiIndex.from_product([tickers, ["Open", "High", "Low", "Close", "Volume"]])
    idx = pd.date_range(end="2026-05-13", periods=n_bars, freq="D")
    data = np.random.rand(n_bars, len(tickers) * 5) * 100
    df = pd.DataFrame(data, index=idx, columns=cols)
    for t in all_nan:
        if t in tickers:
            df[t] = np.nan
    return df


def _make_single_ticker_df(n_bars=10):
    """Build a flat DataFrame matching yf.download with one ticker."""
    cols = ["Open", "High", "Low", "Close", "Volume"]
    idx = pd.date_range(end="2026-05-13", periods=n_bars, freq="D")
    data = np.random.rand(n_bars, 5) * 100
    return pd.DataFrame(data, index=idx, columns=cols)


class TestParseBatchedDownload:
    def test_empty_input_returns_empty_dict(self):
        assert _parse_batched_download(None, ["AAPL"]) == {}
        assert _parse_batched_download(pd.DataFrame(), ["AAPL"]) == {}

    def test_extracts_each_ticker_from_multiindex(self):
        df = _make_multi_ticker_df(["AAPL", "NVDA", "MSFT"])
        out = _parse_batched_download(df, ["AAPL", "NVDA", "MSFT"])
        assert set(out.keys()) == {"AAPL", "NVDA", "MSFT"}
        for t in out:
            assert list(out[t].columns) == ["Open", "High", "Low", "Close", "Volume"]
            assert len(out[t]) == 10

    def test_omits_tickers_with_all_nan_data(self):
        df = _make_multi_ticker_df(["AAPL", "DEAD", "NVDA"], all_nan=["DEAD"])
        out = _parse_batched_download(df, ["AAPL", "DEAD", "NVDA"])
        assert "DEAD" not in out
        assert "AAPL" in out
        assert "NVDA" in out

    def test_handles_single_ticker_flat_output(self):
        df = _make_single_ticker_df()
        out = _parse_batched_download(df, ["AAPL"])
        assert list(out.keys()) == ["AAPL"]
        assert len(out["AAPL"]) == 10

    def test_handles_single_ticker_empty_output(self):
        out = _parse_batched_download(pd.DataFrame(columns=["Close"]), ["AAPL"])
        assert out == {}

    def test_omits_tickers_not_in_dataframe(self):
        df = _make_multi_ticker_df(["AAPL", "NVDA"])
        # Asked for 3, only 2 came back
        out = _parse_batched_download(df, ["AAPL", "NVDA", "GHOST"])
        assert "GHOST" not in out
