"""Portfolio tracking and position management for backtesting."""

import pandas as pd
from typing import List, Dict, Optional


class Position:
    """Represents a single open position in the portfolio.

    Attributes:
        ticker: Stock symbol
        quantity: Number of shares
        entry_price: Price per share at entry
        entry_date: Date position was opened
        cost_basis: Total cost including transaction fees
    """

    def __init__(
        self,
        ticker: str,
        quantity: int,
        price: float,
        entry_date: pd.Timestamp,
        transaction_cost: float = 0.001
    ):
        """Initialize a Position.

        Args:
            ticker: Stock symbol
            quantity: Number of shares
            price: Entry price per share
            entry_date: Date position was opened
            transaction_cost: Transaction cost as fraction (default 0.1%)

        The cost_basis includes the transaction cost:
        cost_basis = quantity * price * (1 + transaction_cost)
        """
        self.ticker = ticker
        self.quantity = quantity
        self.entry_price = price
        self.entry_date = entry_date
        # Cost basis includes transaction cost fee
        self.cost_basis = quantity * price * (1 + transaction_cost)

    def to_dict(self) -> Dict:
        """Convert Position to dictionary representation.

        Returns:
            Dictionary with position details
        """
        return {
            "ticker": self.ticker,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_date": self.entry_date,
            "cost_basis": self.cost_basis
        }


class Portfolio:
    """Manages portfolio state, positions, and trade execution.

    Tracks open positions, cash balance, and trade history.
    Executes buy/sell orders with transaction cost calculations.
    """

    def __init__(self, initial_cash: float = 10000, transaction_cost: float = 0.001):
        """Initialize Portfolio.

        Args:
            initial_cash: Starting cash (default $10,000)
            transaction_cost: Transaction cost as fraction (default 0.1%)
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: List[Position] = []
        self.transaction_cost = transaction_cost
        self.trade_history: List[Dict] = []

    def open_position(
        self,
        ticker: str,
        quantity: int,
        price: float,
        entry_date: pd.Timestamp
    ) -> None:
        """Open a new position.

        Args:
            ticker: Stock symbol
            quantity: Number of shares
            price: Entry price per share
            entry_date: Date position is opened

        Raises:
            ValueError: If insufficient cash to open position

        The cost includes transaction fees:
        cost = quantity * price * (1 + transaction_cost)
        """
        cost = quantity * price * (1 + self.transaction_cost)

        if cost > self.cash:
            raise ValueError(
                f"Insufficient cash to open position. "
                f"Required: {cost:.2f}, Available: {self.cash:.2f}"
            )

        # Create position and add to portfolio
        position = Position(ticker, quantity, price, entry_date, self.transaction_cost)
        self.positions.append(position)

        # Deduct cost from cash
        self.cash -= cost

    def close_position(
        self,
        ticker: str,
        price: float,
        exit_date: pd.Timestamp
    ) -> float:
        """Close an open position.

        Args:
            ticker: Stock symbol to close
            price: Exit price per share
            exit_date: Date position is closed

        Returns:
            Realized P&L from closing position

        Raises:
            ValueError: If position not found for ticker

        P&L calculation:
        exit_value = quantity * price * (1 - transaction_cost)
        pnl = exit_value - cost_basis
        """
        # Find position
        position = None
        for pos in self.positions:
            if pos.ticker == ticker:
                position = pos
                break

        if position is None:
            raise ValueError(f"No open position found for {ticker}")

        # Calculate exit value (minus transaction cost)
        exit_value = position.quantity * price * (1 - self.transaction_cost)

        # Calculate realized P&L
        pnl = exit_value - position.cost_basis

        # Remove position from portfolio
        self.positions.remove(position)

        # Add exit proceeds to cash
        self.cash += exit_value

        # Record trade
        trade = {
            "ticker": ticker,
            "entry_date": position.entry_date,
            "exit_date": exit_date,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "exit_price": price,
            "cost_basis": position.cost_basis,
            "exit_value": exit_value,
            "pnl": pnl
        }
        self.trade_history.append(trade)

        return pnl

    def total_equity(self) -> float:
        """Get total portfolio equity (cash only).

        Returns:
            Current cash balance
        """
        return self.cash

    def equity_with_prices(self, current_prices: Dict[str, float]) -> float:
        """Mark portfolio to market with current prices.

        Args:
            current_prices: Dictionary mapping ticker to current price

        Returns:
            Total equity = cash + market value of open positions
        """
        equity = self.cash

        # Add market value of each position
        for position in self.positions:
            market_value = position.quantity * current_prices[position.ticker]
            equity += market_value

        return equity

    def calculate_kelly_fraction(self, fractional: float = 0.5) -> float:
        """Calculate Kelly Criterion position sizing fraction.

        Kelly Criterion: f* = (bp - q) / b
        Where:
          b = ratio of average win to average loss
          p = probability of winning (win rate)
          q = probability of losing (1 - p)

        Args:
            fractional: Fraction of Kelly to use (default 0.5 = half-Kelly)
                       Use < 1.0 for safety (0.25 conservative, 0.5 moderate, 1.0 aggressive)

        Returns:
            Kelly fraction to use for position sizing (0.0 to 1.0)
            Returns 0.5 (50% fixed sizing) if insufficient trade history
        """
        if len(self.trade_history) < 10:
            # Insufficient data - use conservative sizing
            return 0.5  # Default to 50 shares per position

        # Calculate win rate and P&L statistics
        import numpy as np

        pnls = [trade["pnl"] for trade in self.trade_history]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]

        if len(wins) == 0 or len(losses) == 0:
            # All wins or all losses - not enough data
            return 0.5

        win_rate = len(wins) / len(self.trade_history)
        avg_win = np.mean(wins)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 0.5

        # Kelly formula: f* = (bp - q) / b
        b = avg_win / avg_loss  # Odds ratio
        p = win_rate  # Probability of win
        q = 1 - win_rate  # Probability of loss

        kelly_full = (b * p - q) / b if b > 0 else 0

        # Clamp to reasonable bounds and apply fractional Kelly
        kelly_full = max(0, min(kelly_full, 1.0))  # 0 to 100%
        kelly_fractional = kelly_full * fractional

        return kelly_fractional

    def calculate_position_size(
        self,
        price: float,
        kelly_fraction: float = 0.5,
        max_position_pct: float = 0.25
    ) -> int:
        """Calculate position size using Kelly Criterion.

        Args:
            price: Current stock price
            kelly_fraction: Kelly sizing fraction (0.0 to 1.0)
            max_position_pct: Maximum position as % of portfolio (default 25%)

        Returns:
            Number of shares to buy
        """
        # Maximum allocation per position based on portfolio %
        max_allocation = self.initial_cash * max_position_pct

        # Kelly-sized allocation: conservative sizing to manage risk
        # Uses small multiplier (0.05 = 5%) per position to maintain capital for multiple trades
        kelly_allocation = self.initial_cash * kelly_fraction * 0.05

        # Use the smaller of Kelly or max position
        allocation = min(kelly_allocation, max_allocation)

        # Calculate shares (round down for safety)
        shares = int(allocation / price)

        return max(1, shares)  # At least 1 share
