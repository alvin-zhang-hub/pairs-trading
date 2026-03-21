"""Backtesting simulation engine for strategy evaluation."""

import pandas as pd
import numpy as np
from typing import Tuple
from src.backtest.portfolio import Portfolio


class Backtester:
    """Simulation engine for backtesting trading strategies.

    Processes trading signals and price data to simulate portfolio
    performance, track trades, and compute equity curves.
    """

    def __init__(self, initial_cash: float = 10000, transaction_cost: float = 0.001):
        """Initialize Backtester.

        Args:
            initial_cash: Starting capital (default $10,000)
            transaction_cost: Transaction cost as fraction (default 0.1%)
        """
        self.portfolio = Portfolio(initial_cash, transaction_cost)
        self.daily_equity: list = []
        self.daily_dates: list = []

    def run(
        self,
        signals_df: pd.DataFrame,
        prices_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run backtest simulation.

        Args:
            signals_df: DataFrame with columns [Date, Ticker, Signal, S-Score]
                Signal column contains "BUY" or "CLOSE_LONG"
            prices_df: DataFrame with MultiIndex (Date, Ticker) and "Adj Close" column

        Returns:
            Tuple of (trades_df, equity_df)
            - trades_df: DataFrame of all executed trades from trade_history
            - equity_df: DataFrame with daily equity values and dates

        Algorithm:
        1. Group signals by date
        2. For each date:
            a. Process all signals for that date
            b. Execute BUY/CLOSE_LONG orders based on signals
            c. Get current prices for all positions
            d. Mark portfolio to market
            e. Record daily equity
        3. Return trade history and equity curve
        """
        # Group signals by date for processing
        signals_by_date = signals_df.groupby("Date")

        # Track all dates we process for later price lookups
        signal_dates = sorted(signals_df["Date"].unique())

        try:
            for signal_date in signal_dates:
                # Get all signals for this date
                daily_signals = signals_by_date.get_group(signal_date)

                # Process each signal
                for _, signal_row in daily_signals.iterrows():
                    ticker = signal_row["Ticker"]
                    signal = signal_row["Signal"]

                    # Get price for this signal
                    try:
                        price = prices_df.loc[(signal_date, ticker), "Adj Close"]
                    except KeyError:
                        # Price not available for this date/ticker, skip signal
                        continue

                    # Execute BUY signal
                    if signal == "BUY":
                        # Check if position already open
                        position_exists = any(pos.ticker == ticker for pos in self.portfolio.positions)
                        if not position_exists:
                            try:
                                self.portfolio.open_position(
                                    ticker=ticker,
                                    quantity=100,  # Standard position size
                                    price=price,
                                    entry_date=signal_date
                                )
                            except ValueError:
                                # Insufficient cash, skip this position
                                continue

                    # Execute CLOSE_LONG signal
                    elif signal == "CLOSE_LONG":
                        try:
                            self.portfolio.close_position(
                                ticker=ticker,
                                price=price,
                                exit_date=signal_date
                            )
                        except ValueError:
                            # Position not found, skip
                            continue

                # After processing signals for this date, mark to market
                # Get all current prices for positions
                current_prices = {}
                for position in self.portfolio.positions:
                    try:
                        current_prices[position.ticker] = prices_df.loc[
                            (signal_date, position.ticker), "Adj Close"
                        ]
                    except KeyError:
                        # Use entry price if current price not available
                        current_prices[position.ticker] = position.entry_price

                # Compute daily equity
                daily_equity = self.portfolio.equity_with_prices(current_prices)
                self.daily_equity.append(daily_equity)
                self.daily_dates.append(signal_date)

        except Exception as e:
            # Log error and continue with partial results
            print(f"Error during backtesting: {e}")

        # Convert trade history to DataFrame
        if self.portfolio.trade_history:
            trades_df = pd.DataFrame(self.portfolio.trade_history)
        else:
            trades_df = pd.DataFrame()

        # Convert equity curve to DataFrame
        equity_df = pd.DataFrame({
            "Date": self.daily_dates,
            "Equity": self.daily_equity
        })

        return trades_df, equity_df
