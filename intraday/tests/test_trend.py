import pytest
import pandas as pd
import numpy as np
from scanner.trend import (
    find_swing_highs, find_swing_lows,
    classify_price_structure, classify_trend, get_eligible_setups,
)


def make_hist(highs, lows, closes=None):
    """Build a DataFrame from explicit high/low sequences."""
    n = len(highs)
    if closes is None:
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "High": highs, "Low": lows, "Close": closes,
        "Open": closes, "Volume": [1_000_000] * n,
    }, index=idx)


class TestFindSwingHighs:
    def test_finds_clear_peak(self):
        # Index 2 is a peak: 1,2,5,2,1
        highs = pd.Series([1, 2, 5, 2, 1, 2, 1, 2, 1, 2])
        result = find_swing_highs(highs, lookback=2)
        assert 2 in result

    def test_no_swing_in_flat_series(self):
        highs = pd.Series([5.0] * 10)
        assert find_swing_highs(highs) == []

    def test_excludes_boundary_candles(self):
        # First and last candles cannot be swing highs (need 2 candles on each side)
        highs = pd.Series([10, 5, 5, 5, 5])
        result = find_swing_highs(highs, lookback=2)
        assert 0 not in result


class TestFindSwingLows:
    def test_finds_clear_trough(self):
        lows = pd.Series([5, 4, 1, 4, 5, 4, 5, 4, 5, 4])
        result = find_swing_lows(lows, lookback=2)
        assert 2 in result

    def test_no_swing_in_flat_series(self):
        lows = pd.Series([2.0] * 10)
        assert find_swing_lows(lows) == []


class TestClassifyPriceStructure:
    def test_uptrend_requires_hh_and_hl(self):
        # 3 swing highs each higher, 3 swing lows each higher
        sh = [10, 12, 14]
        sl = [8, 9, 10]
        assert classify_price_structure(sh, sl) == "Uptrend"

    def test_downtrend_requires_lh_and_ll(self):
        sh = [14, 12, 10]
        sl = [10, 9, 8]
        assert classify_price_structure(sh, sl) == "Downtrend"

    def test_mixed_is_sideways(self):
        sh = [10, 12, 11]  # mixed
        sl = [8, 9, 8]     # mixed
        assert classify_price_structure(sh, sl) == "Sideways"

    def test_fewer_than_3_swing_highs_returns_sideways(self):
        assert classify_price_structure([10, 12], [8, 9, 10]) == "Sideways"

    def test_fewer_than_3_swing_lows_returns_sideways(self):
        assert classify_price_structure([10, 12, 14], [8, 9]) == "Sideways"

    def test_empty_lists_return_sideways(self):
        assert classify_price_structure([], []) == "Sideways"


class TestClassifyTrend:
    def _make_uptrend_hist(self):
        """20 candles with rising closes, clear HH/HL structure."""
        closes = [float(50 + i * 0.5) for i in range(25)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        return make_hist(highs, lows, closes)

    def _make_downtrend_hist(self):
        closes = [float(70 - i * 0.5) for i in range(25)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        return make_hist(highs, lows, closes)

    def test_uptrend_when_price_above_emas_and_structure_up(self):
        hist = self._make_uptrend_hist()
        ema_20 = hist["Close"].ewm(span=20, adjust=False).mean()
        ema_50 = hist["Close"].ewm(span=50, adjust=False).mean()
        # Force ema_20 < ema_50 < close for the uptrend case
        ema_20_adj = ema_20 * 0.95
        ema_50_adj = ema_20 * 0.90
        result = classify_trend(hist, ema_20_adj, ema_50_adj)
        assert result == "Uptrend"

    def test_sideways_when_fewer_than_3_swing_points(self):
        # Flat price — no swing points will be found
        closes = [50.0] * 25
        highs = [50.5] * 25
        lows = [49.5] * 25
        hist = make_hist(highs, lows, closes)
        ema = pd.Series([45.0] * 25, index=hist.index)  # price above both EMAs
        result = classify_trend(hist, ema * 0.99, ema * 0.98)
        assert result == "Sideways"


class TestGetEligibleSetups:
    def test_uptrend_includes_long_setups(self):
        setups = get_eligible_setups("Uptrend")
        assert "orb_long" in setups
        assert "ema_pullback_long" in setups
        assert "vwap_reclaim_long" in setups

    def test_downtrend_includes_short_setups(self):
        setups = get_eligible_setups("Downtrend")
        assert "ema_pullback_short" in setups
        assert "vwap_reclaim_short" in setups
        assert "orb_long" not in setups

    def test_sideways_vwap_only(self):
        setups = get_eligible_setups("Sideways")
        assert setups == ["vwap_reclaim_long", "vwap_reclaim_short"]
