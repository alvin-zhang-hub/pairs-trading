"""Data fetcher module for fetching market data and computing volume-weighted returns."""

import numpy as np
import pandas as pd
import yfinance as yf


def fetch_data(tickers: list, period: str = "1y") -> pd.DataFrame:
    """
    Fetch historical stock data for multiple tickers.

    Reshapes the data to have a MultiIndex (Date, Ticker) to support
    operations across multiple assets. Column names are normalized to
    include "Adj Close" for consistency.

    Args:
        tickers: List of ticker symbols (e.g., ["AAPL", "MSFT"])
        period: Period for which to fetch data (default "1y")

    Returns:
        DataFrame with MultiIndex (Date, Ticker) and columns like
        'Adj Close', 'Volume', etc.
    """
    # Download data for all tickers
    data = yf.download(tickers, period=period, progress=False)

    # yfinance returns MultiIndex columns: (Field, Ticker)
    # Rename 'Close' to 'Adj Close' for consistency
    if isinstance(data.columns, pd.MultiIndex):
        # Multi-ticker case: columns are (Field, Ticker)
        data = data.rename(columns={"Close": "Adj Close"}, level=0)
    else:
        # Single ticker case: columns are just Field names
        data = data.rename(columns={"Close": "Adj Close"})

    # Reshape from wide (columns = (field, ticker)) to long (index = (date, ticker))
    # Stack moves the ticker from columns to index
    data = data.stack()
    data.index.names = ["Date", "Ticker"]

    return data


def compute_volume_weighted_returns(df: pd.DataFrame, lookback: int = 10) -> pd.Series:
    """
    Compute volume-weighted log returns.

    Volume weighting is crucial for the strategy:
    - High-volume moves are likely genuine (not mean-reverting), so we discount them
    - Low-volume moves are likely noise (mean-reverting), so we amplify them

    The weighting process:
    1. Compute daily log returns
    2. Compute rolling average volume over lookback period
    3. Calculate volume ratio = current_volume / avg_volume
      (ratio > 1 indicates high volume, < 1 indicates low volume)
    4. Weight = 1.0 / volume_ratio (inverse relationship)
    5. Clip weights to [0.5, 2.0] to avoid extreme outliers
    6. Return weighted log return = log_return * weight

    Args:
        df: DataFrame with 'Adj Close' and 'Volume' columns
        lookback: Period for rolling average volume calculation (default 10 days)

    Returns:
        Series of volume-weighted log returns. First 'lookback' values are NaN
        and dropped, so output length = input length - lookback (or less for small samples)
    """
    # Compute daily log returns
    log_returns = np.log(df["Adj Close"] / df["Adj Close"].shift(1))

    # Compute rolling average volume with min_periods=1 to handle small samples
    rolling_avg_volume = df["Volume"].rolling(window=lookback, min_periods=1).mean()

    # Compute volume ratio (current_volume / avg_volume)
    volume_ratio = df["Volume"] / rolling_avg_volume

    # Compute weights as inverse of volume ratio
    # High volume (ratio > 1) -> weight < 1 (discount genuine moves)
    # Low volume (ratio < 1) -> weight > 1 (amplify noisy moves)
    weights = 1.0 / volume_ratio

    # Clip weights to [0.5, 2.0] to avoid extreme values
    weights = weights.clip(lower=0.5, upper=2.0)

    # Compute volume-weighted returns
    vwr = log_returns * weights

    # Drop NaN values from the beginning (due to first return calculation)
    vwr = vwr.dropna()

    return vwr
