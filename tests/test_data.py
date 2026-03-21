import pandas as pd
from src.data.fetcher import fetch_data, compute_volume_weighted_returns


def test_fetch_data_returns_dataframe():
    """Test that fetch_data returns a DataFrame with expected columns."""
    data = fetch_data(["AAPL"], "1y")
    assert isinstance(data, pd.DataFrame)
    assert "Adj Close" in data.columns
    assert len(data) > 0


def test_fetch_data_multiple_tickers():
    """Test fetching multiple tickers returns multi-index DataFrame."""
    data = fetch_data(["AAPL", "MSFT"], "1y")
    assert isinstance(data, pd.DataFrame)
    assert data.index.nlevels == 2


def test_compute_volume_weighted_returns():
    """Test volume-weighted return computation."""
    dates = pd.date_range("2025-01-01", periods=5)
    prices = [100, 101, 102, 101, 100]
    volumes = [1e6, 2e6, 5e5, 1e6, 3e6]
    df = pd.DataFrame({"Adj Close": prices, "Volume": volumes}, index=dates)
    vwr = compute_volume_weighted_returns(df)
    assert isinstance(vwr, pd.Series)
    assert len(vwr) == len(df) - 1
