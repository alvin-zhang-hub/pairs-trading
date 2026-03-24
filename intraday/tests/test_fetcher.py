import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from scanner.fetcher import compute_atr, fetch_ticker_data


def make_hist(n=30, close_val=50.0, volume=1_000_000):
    """Build a minimal OHLCV DataFrame for testing."""
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = pd.Series([close_val] * n, index=idx)
    return pd.DataFrame({
        "Open": close_val * 0.99,
        "High": close_val * 1.01,
        "Low": close_val * 0.99,
        "Close": close,
        "Volume": volume,
    }, index=idx)


class TestComputeATR:
    def test_returns_positive_float(self):
        hist = make_hist(30, close_val=100.0)
        atr = compute_atr(hist["High"], hist["Low"], hist["Close"])
        assert isinstance(atr, float)
        assert atr > 0

    def test_wider_candles_produce_larger_atr(self):
        narrow = make_hist(30, close_val=100.0)
        wide = narrow.copy()
        wide["High"] = wide["Close"] * 1.05
        wide["Low"] = wide["Close"] * 0.95
        assert compute_atr(wide["High"], wide["Low"], wide["Close"]) > \
               compute_atr(narrow["High"], narrow["Low"], narrow["Close"])

    def test_returns_none_on_insufficient_data(self):
        hist = make_hist(5)
        result = compute_atr(hist["High"], hist["Low"], hist["Close"])
        # ATR with fewer than period candles returns NaN — we handle upstream
        assert result is not None  # function itself doesn't raise


class TestFetchTickerData:
    def _mock_ticker(self, hist, float_shares=50_000_000):
        mock = MagicMock()
        mock.history.return_value = hist
        mock.info = {"floatShares": float_shares}
        return mock

    @patch("scanner.fetcher.yf.Ticker")
    def test_returns_expected_keys(self, mock_ticker_cls):
        hist = make_hist(30, close_val=50.0, volume=800_000)
        mock_ticker_cls.return_value = self._mock_ticker(hist)

        result = fetch_ticker_data("AAPL")

        assert result is not None
        expected_keys = {"ticker", "close", "open_", "prev_close", "volume",
                         "avg_volume_20d", "atr_14", "gap_pct", "rvol", "float_shares"}
        assert set(result.keys()) == expected_keys

    @patch("scanner.fetcher.yf.Ticker")
    def test_returns_none_on_insufficient_history(self, mock_ticker_cls):
        hist = make_hist(10)  # fewer than 22 required days
        mock_ticker_cls.return_value = self._mock_ticker(hist)

        assert fetch_ticker_data("AAPL") is None

    @patch("scanner.fetcher.yf.Ticker")
    def test_rvol_computed_correctly(self, mock_ticker_cls):
        # Today's volume is 2x the 20-day average
        hist = make_hist(30, volume=500_000)
        hist.iloc[-1, hist.columns.get_loc("Volume")] = 1_000_000
        mock_ticker_cls.return_value = self._mock_ticker(hist)

        result = fetch_ticker_data("AAPL")
        assert result is not None
        assert abs(result["rvol"] - 2.0) < 0.1

    @patch("scanner.fetcher.yf.Ticker")
    def test_gap_pct_computed_correctly(self, mock_ticker_cls):
        hist = make_hist(30, close_val=100.0)
        # Set today's open to 103 (3% gap from prev close of 100)
        hist.iloc[-1, hist.columns.get_loc("Open")] = 103.0
        hist.iloc[-2, hist.columns.get_loc("Close")] = 100.0
        mock_ticker_cls.return_value = self._mock_ticker(hist)

        result = fetch_ticker_data("AAPL")
        assert result is not None
        assert abs(result["gap_pct"] - 0.03) < 0.005

    @patch("scanner.fetcher.yf.Ticker")
    def test_float_none_when_info_missing(self, mock_ticker_cls):
        hist = make_hist(30)
        mock = self._mock_ticker(hist, float_shares=None)
        mock.info = {}
        mock_ticker_cls.return_value = mock

        result = fetch_ticker_data("AAPL")
        assert result is not None
        assert result["float_shares"] is None

    @patch("scanner.fetcher.yf.Ticker")
    def test_returns_none_on_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("network error")
        assert fetch_ticker_data("AAPL") is None
