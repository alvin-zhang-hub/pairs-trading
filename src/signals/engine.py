"""Signal generation engine for Avellaneda & Lee pairs trading strategy.

This module orchestrates the complete signal pipeline:
1. Computes volume-weighted returns for both stock and ETF
2. Performs rolling OLS regression to isolate idiosyncratic (mean-reverting) returns
3. Fits an Ornstein-Uhlenbeck process to the residuals
4. Validates mean reversion speed (half-life)
5. Computes s-score (deviation from equilibrium)
6. Applies trading rules based on s-score
7. Calculates volume ratios for position sizing

This is the daily orchestration layer that ties together Tasks 2, 3, and 4.
"""

import numpy as np
import pandas as pd
from src.data.fetcher import compute_volume_weighted_returns
from src.signals.regression import regress_returns
from src.signals.ou_process import (
    fit_ou_process,
    half_life,
    compute_s_score,
    should_reject_stock,
)


def apply_trading_rules(
    s_score: float,
    entry_threshold: float = 1.25,
    exit_threshold: float = 0.5
) -> str:
    """Apply trading rules based on the s-score.

    The s-score measures how far the current residual is from equilibrium
    in units of equilibrium volatility. Trading rules are:
    - Buy (oversold): s < -entry_threshold (expect reversion upward)
    - Short (overbought): s > entry_threshold (expect reversion downward)
    - Hold (neutral): -exit_threshold <= s <= entry_threshold (near equilibrium, no action)
    - Close long: s > -exit_threshold (positive drift, exit long position)
    - Close short: s < exit_threshold (negative drift, exit short position)

    Args:
        s_score: Current s-score (standardized deviation from equilibrium)
        entry_threshold: S-score threshold for entry signals (default 1.25)
        exit_threshold: S-score threshold for exit signals (default 0.5)

    Returns:
        Signal string: one of "BUY", "SHORT", "HOLD", "CLOSE_LONG", "CLOSE_SHORT"
        Returns "HOLD" if s_score is NaN.
    """
    # Handle missing data
    if np.isnan(s_score):
        return "HOLD"

    # Oversold: expect reversion upward
    if s_score < -entry_threshold:
        return "BUY"

    # Overbought: expect reversion downward
    if s_score > entry_threshold:
        return "SHORT"

    # Neutral zone: stay flat
    if -exit_threshold <= s_score <= exit_threshold:
        return "HOLD"

    # Above neutral but not yet overbought: close long if holding
    if s_score > -exit_threshold:
        return "CLOSE_LONG"

    # Below neutral but not yet oversold: close short if holding
    # (s_score < exit_threshold and not in [-exit_threshold, exit_threshold])
    return "CLOSE_SHORT"


def generate_daily_signals(
    ticker: str,
    stock_data: pd.DataFrame,
    etf_data: pd.DataFrame,
    window: int = 60,
    max_half_life: int = 30,
    entry_threshold: float = 1.25,
    exit_threshold: float = 0.5,
    use_volume_weighting: bool = True,
) -> dict:
    """Generate daily trading signals for a stock-ETF pair.

    This function implements the complete Avellaneda & Lee signal pipeline:

    1. **Compute volume-weighted returns**: Weight returns inversely by volume
       to amplify mean-reverting noise and discount genuine trends.

    2. **Align data**: Ensure stock and ETF data share common dates.

    3. **Rolling regression**: Use OLS to decompose stock returns into
       systematic (beta * etf_return) and idiosyncratic (residual).

    4. **Cumulative residuals**: The cumulative sum of residuals represents
       the current deviation from equilibrium (X).

    5. **Fit OU process**: Model X as AR(1) to estimate mean reversion speed (kappa)
       and equilibrium mean (m) and volatility (sigma_eq).

    6. **Validate mean reversion**: Reject stocks with slow mean reversion
       (half-life > max_half_life).

    7. **Compute s-score**: Standardize the current X relative to equilibrium:
       s = (X_current - m) / sigma_eq

    8. **Calculate volume ratio**: Current volume / 10-day average volume
       for position sizing.

    9. **Apply trading rules**: Map s-score to trading actions.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        stock_data: DataFrame with "Adj Close" and "Volume" columns
        etf_data: DataFrame with "Adj Close" and "Volume" columns
        window: Rolling window size for regression (default 60 days)
        max_half_life: Maximum acceptable half-life in trading days (default 30)
        entry_threshold: S-score threshold for entry signals (default 1.25)
        exit_threshold: S-score threshold for exit signals (default 0.5)
        use_volume_weighting: Whether to apply volume weighting to returns (default True)

    Returns:
        Dictionary with keys:
        - "Ticker": The input ticker
        - "S-Score": Current s-score (float), or NaN if rejected
        - "Signal": Trading signal string
        - "Half-Life": Half-life of mean reversion in days (float)
        - "Volume-Ratio": Current volume / 10-day average volume (float)

        If the stock is rejected (mean reversion too slow), Signal will be "REJECTED"
        and S-Score/Half-Life will be NaN.
    """
    try:
        # Step 1: Compute volume-weighted returns for both stock and ETF
        # These weight returns inversely by volume to amplify mean-reverting moves
        if use_volume_weighting:
            stock_vwr = compute_volume_weighted_returns(stock_data)
            etf_vwr = compute_volume_weighted_returns(etf_data)
        else:
            # Use raw returns without volume weighting
            stock_vwr = stock_data["Adj Close"].pct_change()
            etf_vwr = etf_data["Adj Close"].pct_change()

        # Step 2: Align to common dates (intersection of indices)
        common_dates = stock_vwr.index.intersection(etf_vwr.index)

        # Check if we have sufficient data after alignment
        if len(common_dates) < window:
            return {
                "Ticker": ticker,
                "S-Score": np.nan,
                "Signal": "REJECTED",
                "Half-Life": np.nan,
                "Volume-Ratio": np.nan,
            }

        # Align both series to common dates
        stock_vwr_aligned = stock_vwr[common_dates]
        etf_vwr_aligned = etf_vwr[common_dates]

        # Step 3: Perform rolling OLS regression
        # Model: stock_return = alpha + beta * etf_return + residual
        # Residuals represent idiosyncratic (mean-reverting) returns
        betas, residuals, r_squared = regress_returns(
            stock_vwr_aligned, etf_vwr_aligned, window=window
        )

        # Step 4: Compute cumulative residuals
        # X[t] = sum of residuals[0:t] represents current deviation from equilibrium
        X = residuals.fillna(0).cumsum()

        # Step 5: Fit OU process to cumulative residuals
        # This estimates mean reversion speed (kappa/rho) and equilibrium parameters
        rho, m, sigma_eq = fit_ou_process(X.values)

        # Step 6: Check if mean reversion is acceptable
        # Reject if kappa is NaN or if half-life exceeds max_half_life
        if np.isnan(rho) or should_reject_stock(rho, max_half_life):
            return {
                "Ticker": ticker,
                "S-Score": np.nan,
                "Signal": "REJECTED",
                "Half-Life": np.nan,
                "Volume-Ratio": np.nan,
            }

        # Step 7: Compute current s-score
        # s = (X_current - m) / sigma_eq measures deviation from equilibrium
        X_current = X.iloc[-1]
        s_score = compute_s_score(X_current, m, sigma_eq)

        # Step 8: Compute half-life for reporting
        hl = half_life(rho)

        # Step 9: Calculate volume ratio
        # Current volume / 10-day average volume
        current_volume = stock_data["Volume"].iloc[-1]
        avg_volume_10d = stock_data["Volume"].iloc[-10:].mean()

        # Avoid division by zero
        if avg_volume_10d > 0:
            volume_ratio = current_volume / avg_volume_10d
        else:
            volume_ratio = 1.0

        # Step 10: Apply trading rules with custom thresholds
        signal = apply_trading_rules(s_score, entry_threshold, exit_threshold)

        return {
            "Ticker": ticker,
            "S-Score": s_score,
            "Signal": signal,
            "Half-Life": hl,
            "Volume-Ratio": volume_ratio,
        }

    except Exception:
        # Gracefully handle any data issues (too short, misaligned, etc.)
        return {
            "Ticker": ticker,
            "S-Score": np.nan,
            "Signal": "REJECTED",
            "Half-Life": np.nan,
            "Volume-Ratio": np.nan,
        }
