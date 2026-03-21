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
