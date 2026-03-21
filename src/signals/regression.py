"""OLS regression for decomposing stock returns into systematic and idiosyncratic components."""

import pandas as pd
import numpy as np
from statsmodels.api import OLS, add_constant


def regress_returns(stock_returns: pd.Series, etf_returns: pd.Series,
                    window: int = 60) -> tuple:
    """Perform rolling OLS regression to isolate idiosyncratic (mean-reverting) returns.

    Decomposes stock returns into:
    - Systematic risk: beta * etf_return
    - Idiosyncratic risk (residual): the mean-reverting alpha we trade

    Model: stock_return[t] = alpha + beta * etf_return[t] + residual[t]

    Args:
        stock_returns: Series of daily stock returns
        etf_returns: Series of daily ETF returns (same length and index as stock_returns)
        window: Lookback window in days for rolling OLS (default 60)

    Returns:
        Tuple of 3 Series (all with same length and index as input):
        - betas: Series of rolling beta coefficients
        - residuals: Series of rolling residuals (idiosyncratic returns)
        - r_squared: Series of rolling R-squared values

        First window-1 values are NaN (insufficient data for regression).
    """
    n = len(stock_returns)

    # Initialize output arrays with NaN
    betas = np.full(n, np.nan)
    residuals_array = np.full(n, np.nan)
    r_squared = np.full(n, np.nan)

    # Rolling window regression from position window-1 onwards
    for i in range(window - 1, n):
        # Extract window [i-window+1 : i+1]
        start_idx = i - window + 1
        end_idx = i + 1

        y = stock_returns.iloc[start_idx:end_idx].values
        X = etf_returns.iloc[start_idx:end_idx].values

        # Add constant for alpha term
        X_with_const = add_constant(X)

        # Fit OLS model
        model = OLS(y, X_with_const)
        results = model.fit()

        # Extract beta (coefficient[1], skip alpha at index 0)
        betas[i] = results.params[1]

        # Extract current residual (last value in window)
        residuals_array[i] = results.resid[-1]

        # Extract R-squared
        r_squared[i] = results.rsquared

    # Convert to Series with original index
    return (
        pd.Series(betas, index=stock_returns.index),
        pd.Series(residuals_array, index=stock_returns.index),
        pd.Series(r_squared, index=stock_returns.index)
    )
