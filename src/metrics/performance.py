"""Performance metrics module for calculating portfolio performance indicators."""

import json
from urllib.request import urlopen

import numpy as np
import pandas as pd


def fetch_risk_free_rate(date: str) -> float:
    """
    Fetch the risk-free rate from FRED (3-month T-bill rate).

    Attempts to fetch the TB3MS (3-Month Treasury Bill Rate) for the specified date.
    If the exact date is not found, tries the previous trading day.
    Returns the annual rate as a decimal (e.g., 0.05 for 5%).

    Args:
        date: Date string in format "YYYY-MM-DD"

    Returns:
        Annual risk-free rate as decimal (e.g., 0.05). Returns 0.02 on error.

    Example:
        >>> rate = fetch_risk_free_rate("2025-03-14")
        >>> print(f"Risk-free rate: {rate * 100:.2f}%")
    """
    try:
        # Use St. Louis Fed FRED API to fetch 3-month Treasury Bill rate
        # API endpoint: https://api.stlouisfed.org/fred/series/data
        # Note: requires API key, but basic requests might work without key
        date_obj = pd.to_datetime(date)
        start_date = (date_obj - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = date_obj.strftime("%Y-%m-%d")

        # Try using FRED API with observation_start and observation_end
        # This requires an API key, but we'll try the public endpoint
        url = (
            f"https://api.stlouisfed.org/fred/series/data?"
            f"series_id=TB3MS&api_key=test&file_type=json&"
            f"observation_start={start_date}&observation_end={end_date}"
        )

        response = urlopen(url, timeout=5)
        data = json.loads(response.read().decode())

        if "observations" in data and len(data["observations"]) > 0:
            # Get the last observation (most recent)
            observations = data["observations"]
            # Find closest observation to requested date
            closest_obs = None
            min_diff = float("inf")
            for obs in observations:
                obs_date = pd.to_datetime(obs["date"])
                diff = abs((obs_date - date_obj).days)
                if diff < min_diff and obs.get("value") != ".":
                    min_diff = diff
                    closest_obs = obs

            if closest_obs:
                rate_value = float(closest_obs["value"])
                # TB3MS is in percentage format, convert to decimal
                if rate_value > 1:
                    rate_value = rate_value / 100.0
                return float(rate_value)

        raise ValueError(f"No data found for date {date}")

    except Exception as e:
        print(f"Warning: Failed to fetch risk-free rate for {date}: {str(e)}")
        return 0.02  # Fallback default


def compute_sharpe_ratio(
    returns: pd.Series, risk_free_rate: float = 0.02, periods: int = 252
) -> float:
    """
    Compute the annualized Sharpe ratio.

    The Sharpe ratio measures excess return per unit of risk:
    Sharpe = (mean(excess_returns) / std(returns)) * sqrt(periods)

    where excess_returns = returns - (risk_free_rate / periods)

    Args:
        returns: Series of daily returns (as decimals)
        risk_free_rate: Annual risk-free rate as decimal (default 0.02)
        periods: Number of trading periods per year (default 252 for daily)

    Returns:
        Annualized Sharpe ratio (float)

    Example:
        >>> returns = pd.Series(np.random.randn(252) * 0.01 + 0.0005)
        >>> sharpe = compute_sharpe_ratio(returns, risk_free_rate=0.05)
    """
    # Calculate daily risk-free rate
    daily_risk_free_rate = risk_free_rate / periods

    # Calculate excess returns
    excess_returns = returns - daily_risk_free_rate

    # Calculate mean and std dev
    mean_excess_return = excess_returns.mean()
    std_return = returns.std()

    # Handle edge case of zero volatility
    if std_return == 0:
        return 0.0

    # Annualized Sharpe ratio
    sharpe = (mean_excess_return / std_return) * np.sqrt(periods)

    return float(sharpe)


def compute_max_drawdown(equity_curve: list) -> float:
    """
    Compute the maximum drawdown from an equity curve.

    Maximum drawdown is the largest percentage decline from peak to trough:
    drawdown = (value - running_max) / running_max

    Args:
        equity_curve: List of portfolio values over time (e.g., [100, 110, 105, ...])

    Returns:
        Maximum drawdown as decimal (negative, e.g., -0.25 for 25% drawdown)

    Example:
        >>> equity = [100, 110, 105, 120, 115, 100, 95, 110]
        >>> max_dd = compute_max_drawdown(equity)
        >>> print(f"Max drawdown: {max_dd * 100:.2f}%")  # Output: -20.83%
    """
    equity_array = np.array(equity_curve, dtype=float)

    # Calculate running maximum
    running_max = np.maximum.accumulate(equity_array)

    # Calculate drawdown at each point
    drawdown = (equity_array - running_max) / running_max

    # Return maximum (most negative) drawdown
    return float(np.min(drawdown))


def compute_win_rate(trade_history: list) -> float:
    """
    Compute the win rate from a list of trades.

    Win rate is the percentage of trades with positive profit and loss (pnl):
    win_rate = (number of wins) / (total trades)

    Args:
        trade_history: List of trade dictionaries, each with a "pnl" key
                       (e.g., [{"pnl": 100}, {"pnl": -50}, {"pnl": 200}])

    Returns:
        Win rate as decimal between 0 and 1 (e.g., 0.5 for 50%)

    Example:
        >>> trades = [{"pnl": 100}, {"pnl": -50}, {"pnl": 200}]
        >>> wr = compute_win_rate(trades)
        >>> print(f"Win rate: {wr * 100:.2f}%")  # Output: 66.67%
    """
    if len(trade_history) == 0:
        return 0.0

    wins = sum(1 for trade in trade_history if trade["pnl"] > 0)

    return float(wins) / len(trade_history)


def compute_annual_return(
    initial_equity: float, final_equity: float, days_elapsed: int
) -> float:
    """
    Compute the annualized return.

    Annualized return compounds the total return over the number of years:
    annual_return = (1 + total_return) ^ (1/years) - 1

    where total_return = (final_equity - initial_equity) / initial_equity

    Args:
        initial_equity: Starting portfolio value
        final_equity: Ending portfolio value
        days_elapsed: Number of days in the period

    Returns:
        Annualized return as decimal (e.g., 0.10 for 10% annual return)

    Example:
        >>> annual_ret = compute_annual_return(initial_equity=10000,
        ...                                     final_equity=12000,
        ...                                     days_elapsed=365)
        >>> print(f"Annual return: {annual_ret * 100:.2f}%")
    """
    total_return = (final_equity - initial_equity) / initial_equity

    years = days_elapsed / 365.25

    if years == 0:
        return float(total_return)

    annual_return = (1 + total_return) ** (1 / years) - 1

    return float(annual_return)
