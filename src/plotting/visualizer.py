"""Visualization utilities for pairs trading strategy.

This module provides plotting and reporting functions for:
1. Visualizing strategy equity curves against benchmarks
2. Printing formatted daily signal tables
"""

import pandas as pd
import matplotlib.pyplot as plt


def plot_equity_curve(
    strategy_equity: pd.DataFrame,
    benchmark_igv: pd.DataFrame,
    benchmark_smh: pd.DataFrame,
    output_path: str = "equity_curve.png",
) -> None:
    """Plot strategy equity curve against sector benchmarks.

    Creates a normalized comparison of the strategy equity curve with IGV (SaaS)
    and SMH (Semiconductors) benchmarks, all scaled to 1.0 at the start date.

    Args:
        strategy_equity: DataFrame with columns [Date, Equity]
        benchmark_igv: DataFrame with columns [Date, Adj Close] for IGV benchmark
        benchmark_smh: DataFrame with columns [Date, Adj Close] for SMH benchmark
        output_path: Path to save the plot (default "equity_curve.png")

    Returns:
        None. Prints confirmation message and saves plot to output_path.
    """
    # Create figure with specified size
    fig, ax = plt.subplots(figsize=(14, 7))

    # Normalize all three series to 1.0 at start date
    if len(strategy_equity) > 0:
        strategy_normalized = (
            strategy_equity["Equity"] / strategy_equity["Equity"].iloc[0]
        )
        ax.plot(
            strategy_equity["Date"],
            strategy_normalized,
            color="green",
            linewidth=2,
            label="Strategy",
        )

    if len(benchmark_igv) > 0:
        igv_normalized = benchmark_igv["Adj Close"] / benchmark_igv["Adj Close"].iloc[0]
        ax.plot(
            benchmark_igv["Date"],
            igv_normalized,
            color="blue",
            alpha=0.7,
            label="IGV (SaaS)",
        )

    if len(benchmark_smh) > 0:
        smh_normalized = (
            benchmark_smh["Adj Close"] / benchmark_smh["Adj Close"].iloc[0]
        )
        ax.plot(
            benchmark_smh["Date"],
            smh_normalized,
            color="red",
            alpha=0.7,
            label="SMH (Semiconductors)",
        )

    # Set labels and title
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Normalized Equity (1.0 = Initial)", fontsize=12)
    ax.set_title("Pairs Trading Strategy vs Sector Benchmarks", fontsize=14, fontweight="bold")

    # Add legend and grid
    ax.legend(loc="best", fontsize=11)
    ax.grid(alpha=0.3)

    # Save figure
    fig.savefig(output_path, dpi=100, bbox_inches="tight")
    print(f"Plot saved to {output_path}")

    # Close figure
    plt.close(fig)


def print_signal_table(signals_today: pd.DataFrame) -> None:
    """Print a formatted table of daily trading signals.

    Displays trading signals with proper alignment and formatting:
    - Ticker: left-aligned, 10 chars
    - Sector: left-aligned, 15 chars
    - S-Score: right-aligned, 10 chars, 3 decimals
    - Signal: left-aligned, 15 chars
    - Half-Life: right-aligned, 10 chars, 1 decimal + "d"
    - Volume-Ratio: right-aligned, 10 chars, 2 decimals + "x"

    Args:
        signals_today: DataFrame with columns [Ticker, Sector, S-Score, Signal,
                       Half-Life, Volume-Ratio]

    Returns:
        None. Prints formatted table to stdout.
    """
    # Print header
    print("=" * 100)
    print("DAILY SIGNALS")
    print("=" * 100)

    # Print column headers
    header = (
        f"{'Ticker':<10} {'Sector':<15} {'S-Score':<10} "
        f"{'Signal':<15} {'Half-Life':<15} {'Vol Ratio':<10}"
    )
    print(header)
    print("-" * 100)

    # Print each row
    for _, row in signals_today.iterrows():
        ticker = str(row["Ticker"])[:10] if pd.notna(row["Ticker"]) else "N/A"
        sector = str(row["Sector"])[:15] if pd.notna(row["Sector"]) else "N/A"

        # S-Score formatting (right-aligned, 3 decimals)
        if pd.notna(row["S-Score"]):
            s_score_str = f"{row['S-Score']:>10.3f}"
        else:
            s_score_str = f"{'N/A':>10}"

        # Signal formatting (left-aligned)
        signal = str(row["Signal"])[:15] if pd.notna(row["Signal"]) else "N/A"
        signal_str = f"{signal:<15}"

        # Half-Life formatting (right-aligned, 1 decimal + "d")
        if pd.notna(row["Half-Life"]):
            half_life_str = f"{row['Half-Life']:>10.1f}d"
        else:
            half_life_str = f"{'N/A':>10}"

        # Volume-Ratio formatting (right-aligned, 2 decimals + "x")
        if pd.notna(row["Volume-Ratio"]):
            vol_ratio_str = f"{row['Volume-Ratio']:>9.2f}x"
        else:
            vol_ratio_str = f"{'N/A':>10}"

        # Print formatted row
        row_str = (
            f"{ticker:<10} {sector:<15} {s_score_str} "
            f"{signal_str} {half_life_str} {vol_ratio_str}"
        )
        print(row_str)

    # Print footer
    print("=" * 100)
