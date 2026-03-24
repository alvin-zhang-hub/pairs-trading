import pytest
import pandas as pd
from scanner.filters import apply_filters


def make_df(**overrides):
    """Build a minimal passing row. Override any field to test a filter."""
    base = {
        "ticker": "AAPL",
        "close": 50.0,
        "avg_volume_20d": 1_000_000.0,
        "float_shares": 100_000_000.0,
        "atr_14": 1.0,
        "gap_pct": 0.03,
        "rvol": 2.0,
    }
    base.update(overrides)
    return pd.DataFrame([base])


class TestPriceFilter:
    def test_passes_within_range(self):
        assert len(apply_filters(make_df(close=100.0, atr_14=2.0))) == 1

    def test_excludes_below_min(self):
        assert len(apply_filters(make_df(close=9.0))) == 0

    def test_excludes_above_max(self):
        assert len(apply_filters(make_df(close=501.0))) == 0


class TestVolumeFilter:
    def test_passes_above_threshold(self):
        assert len(apply_filters(make_df(avg_volume_20d=600_000))) == 1

    def test_excludes_below_threshold(self):
        assert len(apply_filters(make_df(avg_volume_20d=400_000))) == 0


class TestFloatFilter:
    def test_passes_within_range(self):
        assert len(apply_filters(make_df(float_shares=50_000_000))) == 1

    def test_excludes_below_min(self):
        assert len(apply_filters(make_df(float_shares=5_000_000))) == 0

    def test_excludes_above_max(self):
        assert len(apply_filters(make_df(float_shares=600_000_000))) == 0

    def test_passes_when_float_is_none(self):
        # Missing float should not exclude the stock
        assert len(apply_filters(make_df(float_shares=None))) == 1


class TestATRFilter:
    def test_passes_when_both_conditions_met(self):
        # close=50, atr=1.0 → atr_pct=2% ≥ 1.5%
        assert len(apply_filters(make_df(close=50.0, atr_14=1.0))) == 1

    def test_excludes_when_dollar_atr_too_low(self):
        assert len(apply_filters(make_df(atr_14=0.70))) == 0

    def test_excludes_when_pct_atr_too_low(self):
        # close=200, atr=1.0 → atr_pct=0.5% < 1.5%
        assert len(apply_filters(make_df(close=200.0, atr_14=1.0))) == 0


class TestGapFilter:
    def test_passes_at_threshold(self):
        assert len(apply_filters(make_df(gap_pct=0.02))) == 1

    def test_excludes_below_threshold(self):
        assert len(apply_filters(make_df(gap_pct=0.01))) == 0


class TestRVOLFilter:
    def test_passes_above_threshold(self):
        assert len(apply_filters(make_df(rvol=2.0))) == 1

    def test_excludes_below_threshold(self):
        assert len(apply_filters(make_df(rvol=1.0))) == 0


class TestEMAColumn:
    def test_uses_9_ema_when_gap_above_threshold(self):
        # gap_pct=0.04 > 0.03 threshold
        df = apply_filters(make_df(gap_pct=0.04, close=50.0, atr_14=1.0))
        assert df.iloc[0]["ema"] == 9

    def test_uses_9_ema_when_atr_pct_above_threshold(self):
        # close=30, atr=1.0 → atr_pct=3.3% > 2.5%
        df = apply_filters(make_df(close=30.0, atr_14=1.0, gap_pct=0.02))
        assert df.iloc[0]["ema"] == 9

    def test_uses_21_ema_otherwise(self):
        # gap_pct=0.02, atr_pct=2% — both below thresholds
        df = apply_filters(make_df(close=50.0, atr_14=1.0, gap_pct=0.02))
        assert df.iloc[0]["ema"] == 21
