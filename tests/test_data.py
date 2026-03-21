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
    """Test volume-weighted return computation with larger synthetic dataset."""
    import numpy as np
    # Use 100 data points for realistic testing (matches 60+ day lookback window)
    dates = pd.date_range("2025-01-01", periods=100)
    # Generate synthetic prices with small random walk
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    # Generate synthetic volumes around 1M with some variation
    volumes = 1e6 + np.random.randn(100) * 2e5
    df = pd.DataFrame({"Adj Close": prices, "Volume": volumes}, index=dates)

    vwr = compute_volume_weighted_returns(df)

    # Output type and structure assertions
    assert isinstance(vwr, pd.Series)
    # With 100 points and shift() creating 1 NaN, dropna() removes it -> 99 rows
    assert len(vwr) == 99

    # Value assertions
    assert vwr.dtype in [np.float64, np.float32, float]
    assert np.all(np.isfinite(vwr)), "Output contains NaN or Inf values"
    assert vwr.abs().sum() > 0, "Volume-weighted returns should be non-zero"
