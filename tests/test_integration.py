"""Integration tests for the complete Avellaneda & Lee pairs trading pipeline.

These tests verify the end-to-end flow from data processing through signal generation.
They use synthetic data to avoid dependencies on live APIs.
"""

import numpy as np
import pandas as pd
import pytest
from src.signals.engine import generate_daily_signals


def test_pipeline_end_to_end():
    """Smoke test for the complete pipeline with live data.

    This test would verify the full pipeline works against real market data
    (yfinance connection required). For now, we skip it to avoid runtime dependencies
    on live API availability.

    Later, this can be enabled by removing the skip decorator to test against
    actual market data.
    """
    pytest.skip("Requires live yfinance connection")


def test_data_to_signals():
    """Integration test: synthetic data → signal generation pipeline.

    Creates 120 days of synthetic stock and ETF data with realistic characteristics:
    - Stock prices: random walk starting at ~100
    - ETF prices: random walk starting at ~50
    - Volumes: uniformly distributed 1M to 10M

    Verifies the complete pipeline:
    1. Data passes through generate_daily_signals without errors
    2. Output contains all required keys
    3. Signal is one of the valid trading signals
    4. S-Score, Half-Life, and Volume-Ratio are numeric values

    This test validates that the pipeline integrates correctly without requiring
    live market data.
    """
    np.random.seed(42)
    n = 120  # 120 days of synthetic data
    dates = pd.date_range("2025-01-01", periods=n)

    # Step 1: Create synthetic stock data
    # Random walk starting at ~100 with small daily changes
    stock_price = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    # Volumes uniformly distributed between 1M and 10M
    stock_volume = np.random.uniform(1e6, 10e6, n)
    stock_data = pd.DataFrame(
        {
            "Adj Close": stock_price,
            "Volume": stock_volume,
        },
        index=dates,
    )

    # Step 2: Create synthetic ETF data
    # Random walk starting at ~50 with slightly smaller daily changes
    etf_price = 50.0 + np.cumsum(np.random.randn(n) * 0.3)
    # Volumes uniformly distributed between 1M and 10M
    etf_volume = np.random.uniform(1e6, 10e6, n)
    etf_data = pd.DataFrame(
        {
            "Adj Close": etf_price,
            "Volume": etf_volume,
        },
        index=dates,
    )

    # Step 3: Call the signal generation pipeline
    result = generate_daily_signals("TEST", stock_data, etf_data)

    # Step 4: Verify output is a dictionary
    assert isinstance(result, dict), "generate_daily_signals should return a dict"

    # Step 5: Verify all required keys are present
    required_keys = {"Ticker", "S-Score", "Signal", "Half-Life", "Volume-Ratio"}
    assert required_keys.issubset(
        set(result.keys())
    ), f"Missing required keys. Expected {required_keys}, got {set(result.keys())}"

    # Step 6: Verify Ticker value
    assert result["Ticker"] == "TEST", f"Ticker should be 'TEST', got {result['Ticker']}"

    # Step 7: Verify Signal is one of the valid trading signals
    valid_signals = {"BUY", "SHORT", "CLOSE_LONG", "CLOSE_SHORT", "HOLD", "REJECTED"}
    assert result["Signal"] in valid_signals, (
        f"Signal '{result['Signal']}' not in valid signals {valid_signals}"
    )

    # Step 8: Verify numeric fields
    # For non-rejected stocks, S-Score and Half-Life should be numeric
    if result["Signal"] != "REJECTED":
        assert isinstance(result["S-Score"], (int, float)), (
            f"S-Score should be numeric, got {type(result['S-Score'])}"
        )
        assert not np.isnan(result["S-Score"]), (
            f"S-Score should not be NaN for non-rejected signals"
        )

        assert isinstance(result["Half-Life"], (int, float)), (
            f"Half-Life should be numeric, got {type(result['Half-Life'])}"
        )
        assert not np.isnan(result["Half-Life"]), (
            f"Half-Life should not be NaN for non-rejected signals"
        )

    # Volume-Ratio should always be numeric
    assert isinstance(result["Volume-Ratio"], (int, float)), (
        f"Volume-Ratio should be numeric, got {type(result['Volume-Ratio'])}"
    )
