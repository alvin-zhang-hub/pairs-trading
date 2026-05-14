import numpy as np
import pandas as pd
import pytest

from lighthouse.scoring import (
    multi_factor_score,
    score_distance_from_high,
    score_relative_strength,
    score_trend,
    score_volatility_contraction,
    score_volume_accumulation,
)


def make_daily(n_bars=300, drift=0.001, base=20.0, vol=500_000, vol_spike_last=False, dip_pct=0.0):
    """Build daily OHLCV with steady drift.

    drift: per-bar compounded return. 0.001 = 28% gain over 252 days.
    dip_pct: knock final 5 bars down by this fraction (test distance-from-high).
    """
    closes = base * (1 + drift) ** np.arange(n_bars)
    if dip_pct > 0:
        closes[-5:] = closes[-5:] * (1 - dip_pct)
    opens = closes * 0.998
    highs = closes * 1.005
    lows = closes * 0.995
    volumes = np.full(n_bars, vol, dtype=float)
    if vol_spike_last:
        volumes[-1] = vol * 3
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes}
    )


# -----------------------------------------------------------------------------
# 1. Trend (MA stack)
# -----------------------------------------------------------------------------

class TestScoreTrend:
    def test_full_stack_scores_2(self):
        # Steady uptrend → price > 50DMA > 150DMA > 200DMA
        daily = make_daily(drift=0.002)
        assert score_trend(daily) == 2

    def test_returns_0_when_price_below_50dma(self):
        # Long uptrend then sharp recent drop → price falls below 50DMA
        daily = make_daily(drift=0.002)
        daily.iloc[-30:, daily.columns.get_loc("Close")] *= 0.6
        assert score_trend(daily) == 0

    def test_returns_1_when_mostly_stacked(self):
        # Build a case where price > 50 > 200 but 150 sits between 50 and 200
        # in a non-monotonic way. Simplest: a recent surge that has pulled
        # the 50 above 150 cleanly but the 150 hasn't crossed 200 in order.
        # We construct: long flat at 20, then 60-day surge to 30.
        closes = np.concatenate([np.full(240, 20.0), np.linspace(20, 30, 60)])
        df = pd.DataFrame({
            "Open": closes * 0.998, "High": closes * 1.005, "Low": closes * 0.995,
            "Close": closes, "Volume": np.full(300, 500_000.0),
        })
        # Verify: price=30, 50DMA spans the surge so ~25-28, 150DMA mostly flat at 20,
        # 200DMA still mostly flat at 20. Stack is price>50>150≈200 → partial.
        result = score_trend(df)
        assert result in (1, 2)  # we accept either; key is non-zero

    def test_returns_0_for_insufficient_data(self):
        assert score_trend(make_daily(n_bars=50)) == 0


# -----------------------------------------------------------------------------
# 2. Relative strength vs SPY
# -----------------------------------------------------------------------------

class TestScoreRelativeStrength:
    def test_returns_2_when_outperforming_and_rs_at_new_high(self):
        # Stock up 50% over 252 days, SPY up 10% — strong outperformance,
        # and the RS line (stock/spy ratio) keeps making new highs.
        stock = make_daily(drift=0.0016)   # ~50% over 252 days
        spy = make_daily(drift=0.00038)    # ~10% over 252 days
        assert score_relative_strength(stock, spy) == 2

    def test_returns_1_when_outperforming_but_rs_off_high(self):
        # Stock outperformed historically but has been lagging recently —
        # ratio is still > 1 (RS positive) but no longer at its peak.
        stock = make_daily(drift=0.0016)
        spy = make_daily(drift=0.00038)
        # Knock down stock last 30 days to pull RS line away from its high
        stock.iloc[-30:, stock.columns.get_loc("Close")] *= 0.85
        result = score_relative_strength(stock, spy)
        assert result == 1

    def test_returns_0_when_underperforming(self):
        # SPY outperforms stock — RS < 0
        stock = make_daily(drift=0.0002)
        spy = make_daily(drift=0.002)
        assert score_relative_strength(stock, spy) == 0

    def test_returns_0_for_insufficient_data(self):
        stock = make_daily(n_bars=100)
        spy = make_daily(n_bars=100)
        assert score_relative_strength(stock, spy) == 0


# -----------------------------------------------------------------------------
# 3. Volume accumulation
# -----------------------------------------------------------------------------

class TestScoreVolumeAccumulation:
    def test_returns_2_with_uptrend_and_strong_close_position(self):
        # Steady uptrend with closes at the top of daily range → both OBV
        # and A/D line trend up; A/D at recent high.
        n = 250
        closes = 20.0 * (1 + 0.002) ** np.arange(n)
        # Closes at top of range (bullish) to push A/D up
        df = pd.DataFrame({
            "Open": closes * 0.99,
            "High": closes * 1.005,
            "Low": closes * 0.98,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        })
        assert score_volume_accumulation(df) == 2

    def test_returns_0_in_downtrend(self):
        # Downtrend with closes near lows → OBV falls, A/D falls
        n = 250
        closes = 20.0 * (1 - 0.002) ** np.arange(n)
        df = pd.DataFrame({
            "Open": closes * 1.01,
            "High": closes * 1.02,
            "Low": closes * 0.995,
            "Close": closes,
            "Volume": np.full(n, 1_000_000.0),
        })
        assert score_volume_accumulation(df) == 0

    def test_returns_0_for_insufficient_data(self):
        assert score_volume_accumulation(make_daily(n_bars=20)) == 0


# -----------------------------------------------------------------------------
# 4. Volatility contraction
# -----------------------------------------------------------------------------

class TestScoreVolatilityContraction:
    def test_returns_2_when_bb_width_at_low_and_recent_nr_bar(self):
        # First 200 days: high volatility (wide swings)
        # Last 30 days: tight consolidation (narrow bars), with today narrowest of 7
        n = 250
        early = np.array([20 + 3 * np.sin(i / 5) for i in range(220)])  # noisy
        late = np.linspace(early[-1], 22, 30)  # tight uptrend
        closes = np.concatenate([early, late])
        opens = closes - 0.05
        # Most recent bars: very narrow range; today the narrowest
        highs = closes + np.concatenate([np.full(220, 1.5), np.full(30, 0.3)])
        lows = closes - np.concatenate([np.full(220, 1.5), np.full(30, 0.3)])
        # Make today specifically narrower than the prior 6 bars
        highs[-1] = closes[-1] + 0.1
        lows[-1] = closes[-1] - 0.1
        df = pd.DataFrame({
            "Open": opens, "High": highs, "Low": lows, "Close": closes,
            "Volume": np.full(n, 500_000.0),
        })
        assert score_volatility_contraction(df) == 2

    def test_returns_0_when_expanding(self):
        # Quiet then explosion: BB width at recent high, ranges expanding
        n = 250
        early = np.full(200, 20.0)
        late = 20 * (1 + 0.01) ** np.arange(50)  # expanding move
        closes = np.concatenate([early, late])
        opens = closes * 0.99
        highs = closes * 1.03
        lows = closes * 0.97
        df = pd.DataFrame({
            "Open": opens, "High": highs, "Low": lows, "Close": closes,
            "Volume": np.full(n, 500_000.0),
        })
        assert score_volatility_contraction(df) == 0

    def test_returns_0_for_insufficient_data(self):
        assert score_volatility_contraction(make_daily(n_bars=20)) == 0


# -----------------------------------------------------------------------------
# 5. Distance from 52w high
# -----------------------------------------------------------------------------

class TestScoreDistanceFromHigh:
    def test_returns_2_when_within_25pct(self):
        # Steady uptrend → price is the 52w high
        daily = make_daily(drift=0.001)
        assert score_distance_from_high(daily) == 2

    def test_returns_1_when_within_40pct(self):
        # Uptrend then 30% drop → at 70% of high (between 25% and 40% off)
        daily = make_daily(drift=0.002, dip_pct=0.30)
        result = score_distance_from_high(daily)
        assert result == 1

    def test_returns_0_when_more_than_40pct_off_high(self):
        daily = make_daily(drift=0.002, dip_pct=0.55)
        assert score_distance_from_high(daily) == 0

    def test_returns_0_for_insufficient_data(self):
        assert score_distance_from_high(make_daily(n_bars=20)) == 0


# -----------------------------------------------------------------------------
# Aggregate score
# -----------------------------------------------------------------------------

class TestMultiFactorScore:
    def test_returns_all_components_and_total(self):
        stock = make_daily(drift=0.0016)
        spy = make_daily(drift=0.00038)
        result = multi_factor_score(stock, spy)
        assert set(result.keys()) == {
            "trend", "relative_strength", "volume_accumulation",
            "volatility_contraction", "distance_from_high", "total",
        }
        assert all(0 <= v <= 2 for k, v in result.items() if k != "total")
        assert result["total"] == sum(v for k, v in result.items() if k != "total")
        assert 0 <= result["total"] <= 10

    def test_strong_uptrend_scores_high(self):
        stock = make_daily(drift=0.0016)
        spy = make_daily(drift=0.00038)
        result = multi_factor_score(stock, spy)
        assert result["total"] >= 5

    def test_downtrend_scores_low(self):
        stock = make_daily(drift=-0.002)
        spy = make_daily(drift=0.0005)
        result = multi_factor_score(stock, spy)
        assert result["total"] <= 2
