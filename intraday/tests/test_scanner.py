import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from scanner.scanner import run_scan, save_watchlist


def make_passing_row(ticker="AAPL"):
    return {
        "ticker": ticker, "close": 50.0, "open_": 51.5,
        "prev_close": 48.5, "volume": 2_000_000,
        "avg_volume_20d": 1_000_000, "atr_14": 1.2,
        "gap_pct": 0.031, "rvol": 2.0, "float_shares": 80_000_000,
    }


def make_hist(n=25, close_start=50.0, rising=True):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    closes = [close_start + (i * 0.5 if rising else -i * 0.5) for i in range(n)]
    return pd.DataFrame({
        "High": [c + 0.5 for c in closes],
        "Low": [c - 0.5 for c in closes],
        "Close": closes, "Open": closes, "Volume": [1_000_000] * n,
    }, index=idx)


class TestRunScan:
    @patch("scanner.scanner.yf.Ticker")
    @patch("scanner.scanner.fetch_ticker_data")
    @patch("scanner.scanner.get_universe")
    def test_returns_dataframe_with_expected_columns(
        self, mock_universe, mock_fetch, mock_ticker
    ):
        mock_universe.return_value = ["AAPL"]
        mock_fetch.return_value = make_passing_row("AAPL")

        hist = make_hist(25, rising=True)
        mock_ticker.return_value.history.return_value = hist

        result = run_scan(["AAPL"])
        assert isinstance(result, pd.DataFrame)
        assert "trend" in result.columns
        assert "setups" in result.columns
        assert "ema" in result.columns

    @patch("scanner.scanner.yf.Ticker")
    @patch("scanner.scanner.fetch_ticker_data")
    def test_sorts_by_rvol_descending(self, mock_fetch, mock_ticker):
        rows = [make_passing_row("AAPL"), make_passing_row("MSFT")]
        rows[0]["rvol"] = 3.0
        rows[1]["rvol"] = 5.0
        mock_fetch.side_effect = rows

        hist = make_hist(25)
        mock_ticker.return_value.history.return_value = hist

        result = run_scan(["AAPL", "MSFT"])
        assert result.iloc[0]["ticker"] == "MSFT"

    @patch("scanner.scanner.fetch_ticker_data")
    def test_returns_empty_df_when_no_tickers_pass(self, mock_fetch):
        mock_fetch.return_value = None
        result = run_scan(["AAPL"])
        assert result.empty


class TestSaveWatchlist:
    def test_creates_csv_and_txt(self, tmp_path):
        df = pd.DataFrame([{
            "ticker": "AAPL", "close": 50.0, "gap_pct": 0.03,
            "rvol": 2.0, "atr_14": 1.0, "atr_pct": 0.02,
            "float_shares": 80_000_000, "trend": "Uptrend",
            "ema": 9, "setups": "orb_long",
        }])
        csv_path, txt_path = save_watchlist(df, output_dir=str(tmp_path))
        assert csv_path.endswith(".csv")
        assert txt_path.endswith(".txt")
        with open(txt_path) as f:
            assert "AAPL" in f.read()
