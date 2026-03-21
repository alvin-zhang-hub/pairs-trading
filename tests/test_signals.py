import pandas as pd
import numpy as np
from src.signals.regression import regress_returns


def test_regress_returns_basic():
    """Test OLS regression with synthetic data.

    Creates 100 days of synthetic data where:
    stock_returns = 1.2 * etf_returns + noise

    Verifies:
    - Beta is approximately 1.2 (within 0.5)
    - All outputs are Series
    - Output lengths match input
    """
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2025-01-01", periods=n)

    # Create synthetic returns
    etf_returns = np.random.randn(n) * 0.02  # ETF returns ~2% std dev
    noise = np.random.randn(n) * 0.01  # Noise ~1% std dev
    stock_returns = 1.2 * etf_returns + noise

    etf_series = pd.Series(etf_returns, index=dates)
    stock_series = pd.Series(stock_returns, index=dates)

    # Regress with 60-day window
    betas, residuals, r_squared = regress_returns(stock_series, etf_series, window=60)

    # Verify output types
    assert isinstance(betas, pd.Series), "betas should be a Series"
    assert isinstance(residuals, pd.Series), "residuals should be a Series"
    assert isinstance(r_squared, pd.Series), "r_squared should be a Series"

    # Verify lengths match input
    assert len(betas) == n, f"betas length {len(betas)} != input length {n}"
    assert len(residuals) == n, f"residuals length {len(residuals)} != input length {n}"
    assert len(r_squared) == n, f"r_squared length {len(r_squared)} != input length {n}"

    # Verify first window-1 values are NaN
    assert np.all(np.isnan(betas.iloc[:59])), "First 59 beta values should be NaN"
    assert np.all(np.isnan(residuals.iloc[:59])), "First 59 residual values should be NaN"
    assert np.all(np.isnan(r_squared.iloc[:59])), "First 59 r_squared values should be NaN"

    # Verify last value is NOT NaN (we have enough data)
    assert not np.isnan(betas.iloc[-1]), "Last beta value should not be NaN"
    assert not np.isnan(residuals.iloc[-1]), "Last residual value should not be NaN"
    assert not np.isnan(r_squared.iloc[-1]), "Last r_squared value should not be NaN"

    # Verify beta is approximately 1.2
    # Average beta across the valid window (after window-1)
    avg_beta = betas.iloc[59:].mean()
    assert 0.7 <= avg_beta <= 1.7, f"Average beta {avg_beta} not within [0.7, 1.7]"


def test_regress_returns_insufficient_data():
    """Test OLS regression with insufficient data.

    Creates 30-day data with 60-day window.

    Verifies:
    - First 59 values are NaN (cannot fit window)
    - Last value is NOT NaN (only fits at last position)
    """
    np.random.seed(42)
    n = 30
    dates = pd.date_range("2025-01-01", periods=n)

    # Create synthetic returns
    etf_returns = np.random.randn(n) * 0.02
    stock_returns = 1.1 * etf_returns + np.random.randn(n) * 0.01

    etf_series = pd.Series(etf_returns, index=dates)
    stock_series = pd.Series(stock_returns, index=dates)

    # Regress with 60-day window (larger than data)
    betas, residuals, r_squared = regress_returns(stock_series, etf_series, window=60)

    # Verify lengths match input
    assert len(betas) == n
    assert len(residuals) == n
    assert len(r_squared) == n

    # With n=30 and window=60, first 59 values should be NaN
    # Only last value at index 29 can have a full window (...)
    # Actually, with n=30 and window=60, we can never fit a 60-day window
    # So all values should be NaN
    assert np.all(np.isnan(betas)), "All values should be NaN when data < window"
    assert np.all(np.isnan(residuals)), "All values should be NaN when data < window"
    assert np.all(np.isnan(r_squared)), "All values should be NaN when data < window"
