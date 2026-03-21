import pytest
import pandas as pd
import numpy as np
from src.backtest.portfolio import Position, Portfolio
from src.backtest.simulator import Backtester


class TestPosition:
    """Test Position data class."""

    def test_position_initialization(self):
        """Test Position initialization with cost basis calculation."""
        pos = Position("AAPL", 100, 50.0, pd.Timestamp("2025-01-01"), transaction_cost=0.001)

        assert pos.ticker == "AAPL"
        assert pos.quantity == 100
        assert pos.entry_price == 50.0
        assert pos.entry_date == pd.Timestamp("2025-01-01")
        # cost_basis = 100 * 50 * (1 + 0.001) = 5005
        assert pos.cost_basis == pytest.approx(5005.0)

    def test_position_to_dict(self):
        """Test Position.to_dict() method."""
        pos = Position("MSFT", 50, 100.0, pd.Timestamp("2025-01-02"), transaction_cost=0.001)
        pos_dict = pos.to_dict()

        assert isinstance(pos_dict, dict)
        assert pos_dict["ticker"] == "MSFT"
        assert pos_dict["quantity"] == 50
        assert pos_dict["entry_price"] == 100.0


class TestPortfolio:
    """Test Portfolio tracking and trade execution."""

    def test_portfolio_initialization(self):
        """Test Portfolio initialization with correct initial state."""
        portfolio = Portfolio(initial_cash=10000, transaction_cost=0.001)

        assert portfolio.cash == 10000
        assert portfolio.initial_cash == 10000
        assert portfolio.positions == []
        assert portfolio.transaction_cost == 0.001
        assert portfolio.trade_history == []
        assert portfolio.total_equity() == 10000

    def test_portfolio_open_position(self):
        """Test opening a position with cash deduction."""
        portfolio = Portfolio(initial_cash=10000, transaction_cost=0.001)

        # Open position: 100 shares at $50
        portfolio.open_position("AAPL", 100, 50.0, pd.Timestamp("2025-01-01"))

        # Verify position was added
        assert len(portfolio.positions) == 1
        assert portfolio.positions[0].ticker == "AAPL"
        assert portfolio.positions[0].quantity == 100

        # Verify cash was deducted: cost = 100 * 50 * 1.001 = 5005
        expected_cash = 10000 - 5005
        assert portfolio.cash == pytest.approx(expected_cash)

    def test_portfolio_open_position_insufficient_cash(self):
        """Test that ValueError is raised when cash is insufficient."""
        portfolio = Portfolio(initial_cash=1000, transaction_cost=0.001)

        # Try to open position that costs more than available cash
        with pytest.raises(ValueError):
            portfolio.open_position("AAPL", 100, 50.0, pd.Timestamp("2025-01-01"))

    def test_portfolio_close_position(self):
        """Test closing a position and calculating realized P&L."""
        portfolio = Portfolio(initial_cash=10000, transaction_cost=0.001)

        # Open position: 100 shares at $50
        portfolio.open_position("AAPL", 100, 50.0, pd.Timestamp("2025-01-01"))
        initial_cash_after_open = portfolio.cash

        # Close position: 100 shares at $55 (profit scenario)
        pnl = portfolio.close_position("AAPL", 55.0, pd.Timestamp("2025-01-05"))

        # Verify P&L calculation
        # exit_value = 100 * 55 * (1 - 0.001) = 5495
        # cost_basis = 100 * 50 * (1 + 0.001) = 5005
        # pnl = 5495 - 5005 = 490
        assert pnl == pytest.approx(489.5, abs=1)

        # Verify position was removed
        assert len(portfolio.positions) == 0

        # Verify cash was updated: initial_cash_after_open + exit_value
        expected_cash = initial_cash_after_open + 5495
        assert portfolio.cash == pytest.approx(expected_cash, abs=1)

        # Verify trade was recorded
        assert len(portfolio.trade_history) == 1

    def test_portfolio_close_position_loss(self):
        """Test closing a position at a loss."""
        portfolio = Portfolio(initial_cash=10000, transaction_cost=0.001)

        # Open position: 100 shares at $50
        portfolio.open_position("AAPL", 100, 50.0, pd.Timestamp("2025-01-01"))

        # Close position: 100 shares at $45 (loss scenario)
        pnl = portfolio.close_position("AAPL", 45.0, pd.Timestamp("2025-01-05"))

        # exit_value = 100 * 45 * (1 - 0.001) = 4495
        # cost_basis = 100 * 50 * (1 + 0.001) = 5005
        # pnl = 4495 - 5005 = -510
        assert pnl == pytest.approx(-509.5, abs=1)
        assert len(portfolio.positions) == 0

    def test_portfolio_close_nonexistent_position(self):
        """Test that ValueError is raised when closing non-existent position."""
        portfolio = Portfolio(initial_cash=10000, transaction_cost=0.001)

        with pytest.raises(ValueError):
            portfolio.close_position("NONEXISTENT", 50.0, pd.Timestamp("2025-01-01"))

    def test_portfolio_total_equity(self):
        """Test total_equity() returns cash balance."""
        portfolio = Portfolio(initial_cash=10000, transaction_cost=0.001)
        assert portfolio.total_equity() == 10000

        portfolio.open_position("AAPL", 100, 50.0, pd.Timestamp("2025-01-01"))
        expected_equity = 10000 - (100 * 50 * 1.001)
        assert portfolio.total_equity() == pytest.approx(expected_equity)

    def test_portfolio_equity_with_prices(self):
        """Test equity_with_prices() marks portfolio to market."""
        portfolio = Portfolio(initial_cash=20000, transaction_cost=0.001)

        portfolio.open_position("AAPL", 100, 50.0, pd.Timestamp("2025-01-01"))
        portfolio.open_position("MSFT", 50, 100.0, pd.Timestamp("2025-01-01"))

        current_prices = {"AAPL": 55.0, "MSFT": 105.0}
        equity = portfolio.equity_with_prices(current_prices)

        # equity = cash + (100 * 55) + (50 * 105)
        cash_after_positions = 20000 - (100 * 50 * 1.001) - (50 * 100 * 1.001)
        expected_equity = cash_after_positions + (100 * 55) + (50 * 105)
        assert equity == pytest.approx(expected_equity)


class TestBacktester:
    """Test Backtester simulation engine."""

    def test_backtester_initialization(self):
        """Test Backtester initialization."""
        backtester = Backtester(initial_cash=10000, transaction_cost=0.001)

        assert backtester.portfolio is not None
        assert backtester.portfolio.cash == 10000
        assert backtester.daily_equity == []
        assert backtester.daily_dates == []

    def test_backtester_run_simple(self):
        """Test Backtester.run() with simple BUY and CLOSE signals."""
        # Create synthetic data
        dates = pd.date_range("2025-01-01", periods=5)

        # Signals: BUY on day 1, CLOSE_LONG on day 4
        signals_data = {
            "Date": [dates[0], dates[3]],
            "Ticker": ["AAPL", "AAPL"],
            "Signal": ["BUY", "CLOSE_LONG"],
            "S-Score": [2.5, -2.5]
        }
        signals_df = pd.DataFrame(signals_data)

        # Prices: MultiIndex with (Date, Ticker)
        price_data = []
        for date in dates:
            price_data.append({"Date": date, "Ticker": "AAPL", "Adj Close": 50.0 if date == dates[0] else 55.0})
        prices_df = pd.DataFrame(price_data).set_index(["Date", "Ticker"])

        backtester = Backtester(initial_cash=10000, transaction_cost=0.001)
        trades_df, equity_df = backtester.run(signals_df, prices_df)

        # Verify outputs
        assert isinstance(trades_df, pd.DataFrame)
        assert isinstance(equity_df, pd.DataFrame)
        assert len(backtester.daily_equity) > 0
        assert len(backtester.daily_dates) > 0
