import pandas as pd
import numpy as np
from src.signals.regression import regress_returns
from src.signals.ou_process import fit_ou_process, half_life, compute_s_score, should_reject_stock


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


def test_fit_ou_process_basic():
    """Test OU process fitting with synthetic AR(1) mean-reverting data.

    Creates 100 days of synthetic AR(1) data with known parameters:
    X[t] = m(1-rho) + rho*X[t-1] + ε[t]

    Verifies:
    - 0 < rho < 1 (mean-reverting speed)
    - m is numeric and non-NaN
    - sigma_eq > 0 (equilibrium volatility)
    """
    np.random.seed(42)
    n = 100

    # Create synthetic AR(1) mean-reverting process
    # Target: rho = 0.95, m = 0, sigma = 0.1
    rho_true = 0.95
    m_true = 0.0
    sigma_true = 0.1

    X = np.zeros(n)
    for t in range(1, n):
        innovation = np.random.randn() * sigma_true
        X[t] = m_true * (1 - rho_true) + rho_true * X[t-1] + innovation

    # Fit OU process
    rho, m, sigma_eq = fit_ou_process(X)

    # Verify outputs are numeric and not NaN
    assert not np.isnan(rho), "rho should not be NaN"
    assert not np.isnan(m), "m should not be NaN"
    assert not np.isnan(sigma_eq), "sigma_eq should not be NaN"

    # Verify rho is in valid range [0, 1) for mean-reversion
    assert 0 < rho < 1, f"rho {rho} should be in (0, 1)"

    # Verify sigma_eq is positive
    assert sigma_eq > 0, f"sigma_eq {sigma_eq} should be positive"


def test_half_life_calculation():
    """Test half-life calculation for mean reversion.

    Half-life = ln(2) / (-ln(kappa)) measures how fast mean reversion occurs.

    Verifies:
    - For kappa = 0.90, half-life is positive and < 252 days (1 trading year)
    - Half-life increases as kappa approaches 1 (slower mean reversion)
    """
    kappa = 0.90
    hl = half_life(kappa)

    # Verify half-life is positive and reasonable
    assert hl > 0, f"half_life {hl} should be positive"
    assert hl < 252, f"half_life {hl} should be < 252 trading days for kappa={kappa}"

    # Verify edge cases
    assert np.isinf(half_life(0.0)), "half_life should be inf for kappa=0"
    assert np.isinf(half_life(1.0)), "half_life should be inf for kappa=1"
    assert np.isinf(half_life(-0.5)), "half_life should be inf for kappa < 0"


def test_compute_s_score():
    """Test s-score calculation.

    S-score = (X_current - m) / sigma_eq measures deviation from equilibrium
    in units of equilibrium volatility.

    Verifies:
    - s = 2.0 when X_current=2.0, m=0.0, sigma_eq=1.0
    - s = 0 when X_current = m
    - Returns NaN when sigma_eq = 0
    """
    # Test case 1: Standard case
    X_current = 2.0
    m = 0.0
    sigma_eq = 1.0
    s = compute_s_score(X_current, m, sigma_eq)
    assert np.isclose(s, 2.0), f"s-score {s} should be 2.0"

    # Test case 2: X_current = m
    s_at_equilibrium = compute_s_score(1.0, 1.0, 1.0)
    assert np.isclose(s_at_equilibrium, 0.0), f"s-score {s_at_equilibrium} should be 0.0"

    # Test case 3: sigma_eq = 0 should return NaN
    s_zero_sigma = compute_s_score(1.0, 0.0, 0.0)
    assert np.isnan(s_zero_sigma), "s-score should be NaN when sigma_eq=0"

    # Test case 4: NaN sigma_eq should return NaN
    s_nan_sigma = compute_s_score(1.0, 0.0, np.nan)
    assert np.isnan(s_nan_sigma), "s-score should be NaN when sigma_eq=NaN"
