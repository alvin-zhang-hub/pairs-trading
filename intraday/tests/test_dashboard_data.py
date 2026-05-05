import pandas as pd
import pytest
from dashboard.data import compute_pct_change, compute_sparkline


def test_compute_pct_change_one_period():
    closes = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    result = compute_pct_change(closes, 1)
    assert result == pytest.approx(105.0 / 104.0 - 1)


def test_compute_pct_change_five_periods():
    closes = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    result = compute_pct_change(closes, 5)
    assert result == pytest.approx(105.0 / 100.0 - 1)


def test_compute_pct_change_handles_short_series():
    closes = pd.Series([100.0, 102.0])
    result = compute_pct_change(closes, 21)
    # Falls back to longest available window
    assert result == pytest.approx(102.0 / 100.0 - 1)


def test_compute_sparkline_returns_last_5():
    closes = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    result = compute_sparkline(closes)
    assert result == [3.0, 4.0, 5.0, 6.0, 7.0]


def test_compute_sparkline_fewer_than_5():
    closes = pd.Series([10.0, 20.0, 30.0])
    result = compute_sparkline(closes)
    assert result == [10.0, 20.0, 30.0]


def test_compute_sparkline_exactly_5():
    closes = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = compute_sparkline(closes)
    assert result == [1.0, 2.0, 3.0, 4.0, 5.0]
