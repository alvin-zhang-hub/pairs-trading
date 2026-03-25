import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from regime.fetcher import (
    fetch_qqq_data, fetch_vix, fetch_sector_returns,
    fetch_sp500_breadth, fetch_put_call_ratio,
)


def make_hist(n=30, close=400.0):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    c = pd.Series([close] * n, index=idx)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99,
                         "Close": c, "Volume": 50_000_000}, index=idx)


class TestFetchQQQData:
    @patch("regime.fetcher.yf.Ticker")
    def test_returns_dataframe_with_emas(self, mock_cls):
        mock_cls.return_value.history.return_value = make_hist(60)
        result = fetch_qqq_data()
        assert "ema_20" in result.columns
        assert "ema_50" in result.columns
        assert len(result) > 0


class TestFetchVIX:
    @patch("regime.fetcher.yf.Ticker")
    def test_returns_float(self, mock_cls):
        mock_cls.return_value.history.return_value = make_hist(5, close=20.0)
        result = fetch_vix()
        assert isinstance(result, float)
        assert result == pytest.approx(20.0, abs=0.01)


class TestFetchSectorReturns:
    @patch("regime.fetcher.yf.Ticker")
    def test_returns_dict_with_sector_tickers(self, mock_cls):
        mock_cls.return_value.history.return_value = make_hist(15, close=100.0)
        result = fetch_sector_returns()
        assert isinstance(result, dict)
        assert "XLK" in result
        assert "XLU" in result

    @patch("regime.fetcher.yf.Ticker")
    def test_positive_return_when_price_rises(self, mock_cls):
        hist = make_hist(15, close=100.0)
        hist.iloc[-1, hist.columns.get_loc("Close")] = 105.0
        mock_cls.return_value.history.return_value = hist
        result = fetch_sector_returns(lookback_days=5)
        for v in result.values():
            assert v > 0


class TestFetchSP500Breadth:
    @patch("regime.fetcher.yf.Ticker")
    def test_returns_float_when_sufficient_data(self, mock_cls):
        # All prices above their 20 EMA (rising series)
        hist = make_hist(30, close=100.0)
        mock_cls.return_value.history.return_value = hist
        tickers = ["AAPL"] * 10  # 10 identical tickers
        result = fetch_sp500_breadth(tickers)
        assert result is not None
        assert 0.0 <= result <= 1.0

    @patch("regime.fetcher.yf.Ticker")
    def test_returns_none_when_too_many_failures(self, mock_cls):
        mock_cls.return_value.history.side_effect = Exception("network error")
        tickers = ["AAPL"] * 10
        result = fetch_sp500_breadth(tickers)
        assert result is None


class TestFetchPutCallRatio:
    @patch("regime.fetcher.requests.get")
    def test_returns_float_on_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "DATE,CALLS,PUTS,EQUITY\n2026-01-01,100,80,0.80\n"
        result = fetch_put_call_ratio(lookback_days=1)
        assert result is not None
        assert isinstance(result, float)

    @patch("regime.fetcher.requests.get")
    def test_returns_none_on_failure(self, mock_get):
        mock_get.return_value.status_code = 404
        result = fetch_put_call_ratio(lookback_days=5)
        assert result is None
