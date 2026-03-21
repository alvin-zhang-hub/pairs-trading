"""Test suite for performance metrics module."""

import numpy as np
import pandas as pd
import pytest
from src.metrics.performance import (
    compute_annual_return,
    compute_max_drawdown,
    compute_sharpe_ratio,
    compute_win_rate,
    fetch_risk_free_rate,
)


def test_compute_sharpe_ratio():
    """Test Sharpe ratio computation with 252 daily returns."""
    # Generate 252 daily returns with known mean and std dev
    np.random.seed(42)
    returns = pd.Series(np.random.randn(252) * 0.01 + 0.0005)  # mean ~0.0005, std ~0.01

    sharpe = compute_sharpe_ratio(returns, risk_free_rate=0.05)

    # Sharpe should be positive for positive returns
    assert isinstance(sharpe, float)
    assert sharpe > 0


def test_compute_max_drawdown():
    """Test max drawdown computation with known values."""
    # equity = [100, 110, 105, 120, 115, 100, 95, 110]
    # Peak is 120 at index 3, trough is 95 at index 6
    # Drawdown = (95 - 120) / 120 = -25 / 120 = -0.2083...
    equity = [100, 110, 105, 120, 115, 100, 95, 110]

    max_dd = compute_max_drawdown(equity)

    # Expected: approximately -0.2083 from peak 120 to trough 95
    assert isinstance(max_dd, float)
    assert max_dd < 0  # Drawdown should be negative
    assert abs(max_dd - (-25/120)) <= 0.01  # Within tolerance


def test_compute_win_rate():
    """Test win rate computation with 4 trades."""
    # 4 trades: PnL values [100, -50, 200, 0]
    # Wins: trades with pnl > 0 = 2 trades (100, 200)
    # Win rate = 2 / 4 = 0.5
    trade_history = [
        {"pnl": 100},
        {"pnl": -50},
        {"pnl": 200},
        {"pnl": 0},
    ]

    win_rate = compute_win_rate(trade_history)

    assert isinstance(win_rate, float)
    assert win_rate == 0.5  # 2 wins out of 4 trades


def test_fetch_risk_free_rate():
    """Test fetching risk-free rate from FRED API."""
    # Use a recent date that should have data
    rate = fetch_risk_free_rate("2025-03-14")

    # Rate should be a decimal between 0 and 1
    assert isinstance(rate, float)
    assert 0 < rate < 1
