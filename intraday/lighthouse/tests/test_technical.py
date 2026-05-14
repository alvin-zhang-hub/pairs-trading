import numpy as np
import pandas as pd
import pytest

from lighthouse.technical import is_stage2_breakout, stage2_diagnostics


def make_weekly(n_bars=40, trend_pct=0.01, last_vol_mult=2.0, base=20.0):
    """Build weekly OHLCV with a steady uptrend and a volume spike on the last bar.

    `trend_pct` = compounded weekly drift. 0.01 → ~70% gain over 50 weeks
    `last_vol_mult` = ratio of final-bar volume to baseline
    """
    closes = base * (1 + trend_pct) ** np.arange(n_bars)
    opens = closes * 0.995
    highs = closes * 1.02
    lows = closes * 0.98
    volumes = np.full(n_bars, 1_000_000, dtype=float)
    volumes[-1] = 1_000_000 * last_vol_mult
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes}
    )


def make_daily(n_bars=260, trend_pct=0.0015, dip_pct=0.0, base=20.0):
    """Build daily OHLCV. Optional `dip_pct` knocks final 5 days down to test
    'price near 52W high' check."""
    closes = base * (1 + trend_pct) ** np.arange(n_bars)
    if dip_pct > 0:
        closes[-5:] = closes[-5:] * (1 - dip_pct)
    opens = closes * 0.998
    highs = closes * 1.005
    lows = closes * 0.995
    volumes = np.full(n_bars, 500_000, dtype=float)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes}
    )


class TestIsStage2Breakout:
    def test_passes_when_all_five_conditions_met(self):
        weekly = make_weekly()
        daily = make_daily()
        assert is_stage2_breakout(daily, weekly) is True

    def test_fails_when_weekly_close_below_30w_ma(self):
        # Force a downward dip on the last weekly close so it sits below the
        # 30-week MA but keep prior bars climbing (so the MA itself is high).
        weekly = make_weekly()
        weekly.iloc[-1, weekly.columns.get_loc("Close")] = weekly["Close"].iloc[-2] * 0.5
        daily = make_daily()
        assert is_stage2_breakout(daily, weekly) is False

    def test_fails_when_30w_ma_not_rising(self):
        # Flat weekly closes → MA slope ~ 0
        weekly = make_weekly(trend_pct=0.0)
        # We still need final close above the (flat) MA; bump it up
        weekly.iloc[-1, weekly.columns.get_loc("Close")] = weekly["Close"].mean() * 1.05
        daily = make_daily()
        assert is_stage2_breakout(daily, weekly) is False

    def test_fails_when_50dma_below_200dma(self):
        # Build a daily series that was high then dropped, leaving 50 < 200
        n = 260
        # First 200 days at a high level, last 60 days dropping sharply
        early = np.full(200, 30.0)
        late = np.linspace(30.0, 10.0, 60)
        closes = np.concatenate([early, late])
        opens = closes * 0.998
        highs = closes * 1.005
        lows = closes * 0.995
        volumes = np.full(n, 500_000, dtype=float)
        daily = pd.DataFrame(
            {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes}
        )
        weekly = make_weekly()
        assert is_stage2_breakout(daily, weekly) is False

    def test_fails_when_price_too_far_below_52w_high(self):
        # 30% below 52-week high (threshold is 15%, so this fails)
        daily = make_daily(dip_pct=0.30)
        weekly = make_weekly()
        # Also push last weekly close down to match
        weekly.iloc[-1, weekly.columns.get_loc("Close")] = weekly["Close"].iloc[-1] * 0.70
        # The weekly MA slope condition may also fail — that's fine, we're
        # asserting the overall function rejects this scenario.
        assert is_stage2_breakout(daily, weekly) is False

    def test_fails_when_breakout_volume_not_elevated(self):
        weekly = make_weekly(last_vol_mult=1.0)  # last bar volume == baseline
        daily = make_daily()
        assert is_stage2_breakout(daily, weekly) is False

    def test_returns_false_for_insufficient_weekly_data(self):
        weekly = make_weekly(n_bars=20)  # < 30 weeks
        daily = make_daily()
        assert is_stage2_breakout(daily, weekly) is False

    def test_returns_false_for_insufficient_daily_data(self):
        weekly = make_weekly()
        daily = make_daily(n_bars=100)  # < 200 days
        assert is_stage2_breakout(daily, weekly) is False

    def test_returns_false_for_empty_inputs(self):
        empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        assert is_stage2_breakout(empty, empty) is False


class TestPctBelow3yrHigh:
    def test_returns_zero_when_at_high(self):
        # Steady uptrend → last bar is the high
        from lighthouse.technical import pct_below_3yr_high
        weekly = make_weekly(trend_pct=0.01)
        result = pct_below_3yr_high(weekly)
        assert result == pytest.approx(0.0, abs=1e-6)

    def test_returns_positive_when_off_high(self):
        # Uptrend then knockdown 20% on last bar
        from lighthouse.technical import pct_below_3yr_high
        weekly = make_weekly(trend_pct=0.01)
        last_idx = weekly.columns.get_loc("Close")
        weekly.iloc[-1, last_idx] = weekly["Close"].iloc[-2] * 0.80
        result = pct_below_3yr_high(weekly)
        assert result == pytest.approx(0.20, abs=0.02)

    def test_returns_zero_for_insufficient_data(self):
        from lighthouse.technical import pct_below_3yr_high
        weekly = make_weekly(n_bars=2)
        assert pct_below_3yr_high(weekly) == 0.0

    def test_handles_none(self):
        from lighthouse.technical import pct_below_3yr_high
        assert pct_below_3yr_high(None) == 0.0


class TestPctAbove30dma:
    def test_positive_in_uptrend(self):
        from lighthouse.technical import pct_above_30dma
        daily = make_daily(n_bars=100, trend_pct=0.003)
        result = pct_above_30dma(daily)
        # Strong uptrend, latest close above 30dma
        assert result > 0.02

    def test_negative_in_downtrend(self):
        from lighthouse.technical import pct_above_30dma
        daily = make_daily(n_bars=100, trend_pct=-0.003)
        result = pct_above_30dma(daily)
        assert result < -0.02

    def test_returns_zero_for_insufficient_data(self):
        from lighthouse.technical import pct_above_30dma
        daily = make_daily(n_bars=20)
        assert pct_above_30dma(daily) == 0.0

    def test_handles_none(self):
        from lighthouse.technical import pct_above_30dma
        assert pct_above_30dma(None) == 0.0


class TestStage2Diagnostics:
    """The diagnostics function returns the per-condition booleans for debugging.
    Useful when a stock 'just barely' fails and we want to know which condition."""

    def test_returns_all_five_condition_flags(self):
        weekly = make_weekly()
        daily = make_daily()
        diag = stage2_diagnostics(daily, weekly)
        assert set(diag.keys()) == {
            "weekly_close_above_30w_ma",
            "ma_slope_positive",
            "golden_cross",
            "near_52w_high",
            "breakout_volume",
        }
        assert all(isinstance(v, bool) for v in diag.values())

    def test_all_true_when_setup_is_clean(self):
        diag = stage2_diagnostics(make_daily(), make_weekly())
        assert all(diag.values())
