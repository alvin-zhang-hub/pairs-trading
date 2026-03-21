"""Ornstein-Uhlenbeck (OU) process estimation for mean-reversion dynamics.

The core of the Avellaneda & Lee strategy models the residual as a mean-reverting OU process:
    dX = κ(m - X)dt + σ dW

Where:
- κ (kappa): Speed of mean reversion (how fast it pulls back to equilibrium)
- m: Equilibrium mean level
- σ: Equilibrium volatility (diffusion coefficient)

We estimate these parameters by fitting an AR(1) model to cumulative residuals:
    X[t] = m(1-rho) + rho*X[t-1] + ε[t]

The AR(1) coefficients map to OU parameters:
- rho (AR coefficient) ≈ κ (mean reversion speed)
- m (equilibrium) = intercept / (1 - rho)
- σ_eq = std(residuals) (equilibrium volatility)

The s-score measures how far we are from equilibrium in units of volatility,
enabling principled entry/exit decisions based on statistical significance.
"""

import numpy as np
from statsmodels.tsa.ar_model import AutoReg


def fit_ou_process(residual_series: np.ndarray) -> tuple:
    """Fit an Ornstein-Uhlenbeck process to cumulative residuals.

    Estimates mean reversion parameters by fitting an AR(1) model:
        X[t] = const + rho*X[t-1] + ε[t]

    Args:
        residual_series: Array of residuals (daily, uncumulated)

    Returns:
        Tuple of (rho, m, sigma_eq):
        - rho: AR(1) coefficient, estimates mean reversion speed κ
                In range (0, 1) for mean-reverting process
        - m: Equilibrium mean (intercept / (1 - rho))
        - sigma_eq: Equilibrium volatility (std of residuals)

        Returns (np.nan, np.nan, np.nan) if fitting fails or data is insufficient.
    """
    try:
        # Remove NaN values from the series
        residuals_clean = residual_series[~np.isnan(residual_series)]

        # Need at least 2 observations for AR(1)
        if len(residuals_clean) < 2:
            return (np.nan, np.nan, np.nan)

        # Fit AR(1) model using statsmodels
        # AutoReg with lags=1 fits: X[t] = const + rho*X[t-1] + noise
        model = AutoReg(residuals_clean, lags=1)
        results = model.fit()

        # Extract parameters
        # params[0] = constant (intercept)
        # params[1] = rho (AR coefficient)
        intercept = results.params[0]
        rho = results.params[1]

        # Calculate equilibrium mean
        # From X[t] = const + rho*X[t-1] + noise, in steady state:
        # m = const + rho*m  =>  m = const / (1 - rho)
        if rho < 1:
            m = intercept / (1 - rho)
        else:
            # Process is not mean-reverting (rho >= 1)
            m = 0

        # Equilibrium volatility is the standard deviation of residuals
        sigma_eq = np.std(residuals_clean)

        return (rho, m, sigma_eq)

    except Exception:
        # Return NaN tuple on any fitting error
        return (np.nan, np.nan, np.nan)


def half_life(kappa: float) -> float:
    """Calculate the half-life of mean reversion.

    Half-life measures how many trading days it takes for the process
    to revert halfway back to its equilibrium after a shock.

    Formula: HL = ln(2) / (-ln(kappa))

    Args:
        kappa: Mean reversion speed (typically the AR(1) coefficient rho)
               Valid range (0, 1) for mean-reverting process

    Returns:
        Half-life in trading days.
        Returns np.inf if kappa is invalid (kappa <= 0 or kappa >= 1).
    """
    # Check for invalid mean reversion parameter
    if kappa <= 0 or kappa >= 1:
        return np.inf

    # Calculate half-life
    # HL = ln(2) / (-ln(kappa))
    half_life_days = np.log(2) / (-np.log(kappa))

    return half_life_days


def compute_s_score(X_current: float, m: float, sigma_eq: float) -> float:
    """Compute the s-score: normalized deviation from equilibrium.

    The s-score measures how far the current residual is from equilibrium
    in units of equilibrium volatility. This is the key trading signal:
    - s = 0: At equilibrium (no position)
    - s > 0: Above equilibrium (expect reversion downward)
    - s < 0: Below equilibrium (expect reversion upward)

    Statistical interpretation:
    - |s| > 2: Approximately 2 standard deviations from mean (95% confidence)
    - |s| > 3: Approximately 3 standard deviations from mean (99% confidence)

    Formula: s = (X_current - m) / sigma_eq

    Args:
        X_current: Current residual value
        m: Equilibrium mean
        sigma_eq: Equilibrium volatility

    Returns:
        S-score (dimensionless).
        Returns np.nan if sigma_eq is 0 or NaN (undefined s-score).
    """
    # Cannot compute s-score with zero or NaN volatility
    if sigma_eq == 0 or np.isnan(sigma_eq):
        return np.nan

    # Compute normalized deviation from equilibrium
    s_score = (X_current - m) / sigma_eq

    return s_score


def should_reject_stock(kappa: float, max_half_life: int = 30) -> bool:
    """Determine if a stock should be rejected based on mean reversion speed.

    Stocks with slow mean reversion (large half-life) produce unreliable trading signals.
    This filter ensures we only trade stocks with sufficiently fast mean reversion.

    Args:
        kappa: Mean reversion speed (typically the AR(1) coefficient rho)
        max_half_life: Maximum acceptable half-life in trading days (default 30)

    Returns:
        True if stock should be rejected (mean reversion too slow)
        False if stock should be accepted (mean reversion is fast enough)
    """
    hl = half_life(kappa)

    # Reject if half-life exceeds threshold
    if hl > max_half_life:
        return True

    return False
