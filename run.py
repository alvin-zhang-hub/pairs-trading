"""
Avellaneda & Lee Pairs Trading Strategy - Main Entry Point.

This orchestration script ties all modules together:
1. Fetch data (Task 2)
2. Generate signals (Task 5)
3. Run backtest (Task 6)
4. Compute metrics (Task 7)
5. Generate plots (Task 8)
6. Print summary (Task 8)

The strategy uses volume-weighted mean reversion to identify pairs trading
opportunities across SaaS and Semiconductor sectors.
"""

import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Suppress warnings from yfinance and pandas
warnings.filterwarnings("ignore")

# Import modules from src package
from src.data.fetcher import fetch_data
from src.signals.engine import generate_daily_signals
from src.backtest.simulator import Backtester
from src.metrics.performance import (
    fetch_risk_free_rate,
    compute_sharpe_ratio,
    compute_max_drawdown,
    compute_win_rate,
    compute_annual_return,
)
from src.plotting.visualizer import plot_equity_curve, print_signal_table


# ============================================================================
# CONFIGURATION SECTION (Editable)
# ============================================================================

SAAS_STOCKS = ["CRM", "NOW", "WDAY", "SNOW", "MDB", "DDOG", "ZS", "CRWD", "NET", "HUBS"]
SAAS_ETF = "IGV"

SEMI_STOCKS = ["NVDA", "AMD", "INTC", "AVGO", "QCOM", "MRVL", "AMAT", "LRCX", "KLAC", "MU"]
SEMI_ETF = "SMH"

INITIAL_CASH = 10000
TRANSACTION_COST = 0.001
LOOKBACK_PERIOD = "1y"
BACKTEST_START_DAYS = 180


def main():
    """Main orchestration function for the pairs trading strategy."""

    # Print header
    print("=" * 100)
    print("AVELLANEDA & LEE PAIRS TRADING STRATEGY")
    print("=" * 100)
    print()

    # ========================================================================
    # [1/6] FETCH DATA FROM YFINANCE
    # ========================================================================
    print("[1/6] FETCHING DATA")
    print("-" * 100)
    try:
        # Fetch SaaS stocks + ETF
        saas_tickers = SAAS_STOCKS + [SAAS_ETF]
        saas_data = fetch_data(saas_tickers, period=LOOKBACK_PERIOD)

        # Fetch Semiconductor stocks + ETF
        semi_tickers = SEMI_STOCKS + [SEMI_ETF]
        semi_data = fetch_data(semi_tickers, period=LOOKBACK_PERIOD)

        # Combine both datasets
        all_data = pd.concat([saas_data, semi_data])

        # Get statistics
        num_trading_days = len(all_data.index.get_level_values(0).unique())
        num_stocks = len(SAAS_STOCKS) + len(SEMI_STOCKS)
        num_etfs = 2

        print(f"  ✓ Fetched {num_trading_days} trading days")
        print(f"  ✓ Stocks: {num_stocks}, ETFs: {num_etfs}")
        print()

    except Exception as e:
        print(f"  ✗ Error fetching data: {str(e)}")
        return

    # ========================================================================
    # [2/6] GENERATE DAILY SIGNALS
    # ========================================================================
    print("[2/6] GENERATING DAILY SIGNALS")
    print("-" * 100)
    try:
        # Get the latest date (most recent trading day)
        latest_date = all_data.index.get_level_values(0).max()

        # Initialize list to collect signals
        all_signals = []

        # Process SaaS stocks vs IGV
        for stock_ticker in SAAS_STOCKS:
            try:
                # Get stock data
                stock_data = all_data.loc[all_data.index.get_level_values(1) == stock_ticker]
                stock_data = stock_data.reset_index(level=1, drop=True)

                # Get ETF data
                etf_data = all_data.loc[all_data.index.get_level_values(1) == SAAS_ETF]
                etf_data = etf_data.reset_index(level=1, drop=True)

                # Generate signals
                signal_dict = generate_daily_signals(
                    ticker=stock_ticker,
                    stock_data=stock_data,
                    etf_data=etf_data,
                    window=60,
                    max_half_life=30,
                )

                # Add sector and date information
                signal_dict["Sector"] = "SaaS"
                signal_dict["Date"] = latest_date

                all_signals.append(signal_dict)

            except Exception as e:
                # Continue with next stock on error
                continue

        # Process Semiconductor stocks vs SMH
        for stock_ticker in SEMI_STOCKS:
            try:
                # Get stock data
                stock_data = all_data.loc[all_data.index.get_level_values(1) == stock_ticker]
                stock_data = stock_data.reset_index(level=1, drop=True)

                # Get ETF data
                etf_data = all_data.loc[all_data.index.get_level_values(1) == SEMI_ETF]
                etf_data = etf_data.reset_index(level=1, drop=True)

                # Generate signals
                signal_dict = generate_daily_signals(
                    ticker=stock_ticker,
                    stock_data=stock_data,
                    etf_data=etf_data,
                    window=60,
                    max_half_life=30,
                )

                # Add sector and date information
                signal_dict["Sector"] = "Semiconductor"
                signal_dict["Date"] = latest_date

                all_signals.append(signal_dict)

            except Exception as e:
                # Continue with next stock on error
                continue

        # Convert to DataFrame
        signals_df = pd.DataFrame(all_signals)

        # Print signal table
        print_signal_table(signals_df)

        print(f"  ✓ Generated signals for {len(signals_df)} stocks")
        print()

    except Exception as e:
        print(f"  ✗ Error generating signals: {str(e)}")
        return

    # ========================================================================
    # [3/6] RUN BACKTEST
    # ========================================================================
    print("[3/6] RUNNING BACKTEST")
    print("-" * 100)
    try:
        # Calculate backtest period
        latest_date = all_data.index.get_level_values(0).max()
        backtest_start_date = latest_date - timedelta(days=BACKTEST_START_DAYS)

        # Filter data for backtest period
        mask = (
            (all_data.index.get_level_values(0) >= backtest_start_date)
            & (all_data.index.get_level_values(0) <= latest_date)
        )
        backtest_data = all_data[mask]

        # Reindex signals_df to have Date as column (not index)
        # Create a full signals DataFrame for backtest period
        backtest_signals_list = []

        for stock_ticker in SAAS_STOCKS:
            try:
                stock_data = backtest_data.loc[backtest_data.index.get_level_values(1) == stock_ticker]
                stock_data = stock_data.reset_index(level=1, drop=True)

                etf_data = backtest_data.loc[backtest_data.index.get_level_values(1) == SAAS_ETF]
                etf_data = etf_data.reset_index(level=1, drop=True)

                if len(stock_data) > 60:
                    signal_dict = generate_daily_signals(
                        ticker=stock_ticker,
                        stock_data=stock_data,
                        etf_data=etf_data,
                    )

                    signal_dict["Sector"] = "SaaS"
                    signal_dict["Date"] = latest_date
                    backtest_signals_list.append(signal_dict)
            except Exception:
                continue

        for stock_ticker in SEMI_STOCKS:
            try:
                stock_data = backtest_data.loc[backtest_data.index.get_level_values(1) == stock_ticker]
                stock_data = stock_data.reset_index(level=1, drop=True)

                etf_data = backtest_data.loc[backtest_data.index.get_level_values(1) == SEMI_ETF]
                etf_data = etf_data.reset_index(level=1, drop=True)

                if len(stock_data) > 60:
                    signal_dict = generate_daily_signals(
                        ticker=stock_ticker,
                        stock_data=stock_data,
                        etf_data=etf_data,
                    )

                    signal_dict["Sector"] = "Semiconductor"
                    signal_dict["Date"] = latest_date
                    backtest_signals_list.append(signal_dict)
            except Exception:
                continue

        backtest_signals_df = pd.DataFrame(backtest_signals_list)

        # Initialize backtester
        backtester = Backtester(initial_cash=INITIAL_CASH, transaction_cost=TRANSACTION_COST)

        # Run backtest
        trades_df, equity_df = backtester.run(backtest_signals_df, backtest_data)

        print(f"  Backtest period: {backtest_start_date.strftime('%Y-%m-%d')} to {latest_date.strftime('%Y-%m-%d')}")
        print(f"  ✓ Backtest completed")
        print(f"    - Total trades executed: {len(trades_df)}")
        print(f"    - Final equity: ${equity_df['Equity'].iloc[-1] if len(equity_df) > 0 else INITIAL_CASH:,.2f}")
        print()

    except Exception as e:
        print(f"  ✗ Error during backtest: {str(e)}")
        return

    # ========================================================================
    # [4/6] COMPUTE METRICS
    # ========================================================================
    print("[4/6] COMPUTING METRICS")
    print("-" * 100)
    try:
        # Count BUY and SHORT signals
        buy_signals = len(signals_df[signals_df["Signal"] == "BUY"])
        short_signals = len(signals_df[signals_df["Signal"] == "SHORT"])

        print(f"  Signal summary:")
        print(f"    - BUY signals: {buy_signals}")
        print(f"    - SHORT signals: {short_signals}")

        # Fetch risk-free rate
        try:
            risk_free_rate = fetch_risk_free_rate(latest_date.strftime("%Y-%m-%d"))
            print(f"    - Risk-free rate: {risk_free_rate * 100:.2f}%")
        except Exception:
            risk_free_rate = 0.02
            print(f"    - Risk-free rate: {risk_free_rate * 100:.2f}% (default)")

        # Compute performance metrics if we have trades
        if len(equity_df) > 0:
            initial_equity = INITIAL_CASH
            final_equity = equity_df["Equity"].iloc[-1]
            days_elapsed = (latest_date - backtest_start_date).days

            # Compute daily returns from equity curve
            equity_values = equity_df["Equity"].values
            if len(equity_values) > 1:
                daily_returns = np.diff(equity_values) / equity_values[:-1]
                sharpe_ratio = compute_sharpe_ratio(pd.Series(daily_returns), risk_free_rate=risk_free_rate)
            else:
                sharpe_ratio = 0.0

            max_drawdown = compute_max_drawdown(equity_values)
            annual_return = compute_annual_return(initial_equity, final_equity, days_elapsed)

            # Win rate
            if len(trades_df) > 0:
                win_rate = compute_win_rate(trades_df.to_dict("records"))
            else:
                win_rate = 0.0

            print(f"  Performance metrics:")
            print(f"    - Annual return: {annual_return * 100:.2f}%")
            print(f"    - Sharpe ratio: {sharpe_ratio:.2f}")
            print(f"    - Max drawdown: {max_drawdown * 100:.2f}%")
            print(f"    - Win rate: {win_rate * 100:.2f}%")
        print()

    except Exception as e:
        print(f"  ✗ Error computing metrics: {str(e)}")
        return

    # ========================================================================
    # [5/6] GENERATE PLOTS
    # ========================================================================
    print("[5/6] GENERATING PLOTS")
    print("-" * 100)
    try:
        # Get benchmark data
        igv_data = all_data.loc[all_data.index.get_level_values(1) == SAAS_ETF]
        igv_data = igv_data.reset_index()
        igv_data.columns = ["Date", "Ticker"] + list(igv_data.columns[2:])

        smh_data = all_data.loc[all_data.index.get_level_values(1) == SEMI_ETF]
        smh_data = smh_data.reset_index()
        smh_data.columns = ["Date", "Ticker"] + list(smh_data.columns[2:])

        # Filter benchmarks to backtest period
        igv_backtest = igv_data[
            (igv_data["Date"] >= backtest_start_date) & (igv_data["Date"] <= latest_date)
        ].copy()
        smh_backtest = smh_data[
            (smh_data["Date"] >= backtest_start_date) & (smh_data["Date"] <= latest_date)
        ].copy()

        # Plot equity curve
        plot_equity_curve(equity_df, igv_backtest, smh_backtest, output_path="equity_curve.png")
        print(f"  ✓ Plot saved to equity_curve.png")
        print()

    except Exception as e:
        print(f"  ✗ Error generating plots: {str(e)}")
        return

    # ========================================================================
    # [6/6] SUMMARY
    # ========================================================================
    print("[6/6] SUMMARY")
    print("-" * 100)
    print()
    print("NEXT STEPS: Deploy signals to live trading system")
    print("  1. Monitor daily s-scores for BUY/SHORT signals")
    print("  2. Execute trades with appropriate position sizing (volume-weighted)")
    print("  3. Close positions when s-score reverts to equilibrium")
    print("  4. Review daily performance metrics")
    print()
    print("=" * 100)
    print("Pairs trading strategy execution completed successfully!")
    print("=" * 100)


if __name__ == "__main__":
    main()
