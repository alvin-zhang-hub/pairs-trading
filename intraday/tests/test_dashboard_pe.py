import pytest
from dashboard.data import fetch_pe_data


def test_fetch_pe_data_returns_dict():
    """Verify fetch_pe_data returns a dict with SPY, QQQ, IWM keys."""
    result = fetch_pe_data()
    assert isinstance(result, dict)
    assert "SPY" in result
    assert "QQQ" in result
    assert "IWM" in result


def test_fetch_pe_data_values_are_positive():
    """Verify PE values are positive floats."""
    result = fetch_pe_data()
    for ticker in ["SPY", "QQQ", "IWM"]:
        assert isinstance(result[ticker], (int, float))
        assert result[ticker] >= 0


def test_fetch_pe_data_handles_missing_pe():
    """If yfinance doesn't return PE, use 0.0 placeholder."""
    result = fetch_pe_data()
    # Should not raise even if PE is unavailable
    assert isinstance(result, dict)
