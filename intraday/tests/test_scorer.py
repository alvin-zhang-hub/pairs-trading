import pytest
import pandas as pd
from unittest.mock import patch
from regime.scorer import (
    score_qqq_ema, score_qqq_structure, score_vix,
    score_breadth, score_sector_rotation, score_put_call,
    get_regime_tier, compute_regime,
)


def make_qqq_hist(n=20, close=400.0, ema_20=390.0, ema_50=380.0):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    c = pd.Series([close] * n, index=idx)
    hist = pd.DataFrame({"High": c * 1.01, "Low": c * 0.99,
                         "Close": c, "Open": c, "Volume": 50_000_000}, index=idx)
    hist["ema_20"] = ema_20
    hist["ema_50"] = ema_50
    return hist


class TestScoreQQQEma:
    def test_bullish_when_above_both_and_20_above_50(self):
        assert score_qqq_ema(410, ema_20=400, ema_50=390) == 1

    def test_bearish_when_below_20_ema(self):
        assert score_qqq_ema(380, ema_20=390, ema_50=380) == -1

    def test_bearish_when_20_below_50(self):
        assert score_qqq_ema(410, ema_20=380, ema_50=390) == -1

    def test_neutral_when_between_emas(self):
        assert score_qqq_ema(395, ema_20=400, ema_50=390) == 0

    def test_boundary_returns_neutral(self):
        # price exactly on ema_20 — boundary → neutral
        assert score_qqq_ema(400, ema_20=400, ema_50=390) == 0


class TestScoreVIX:
    def test_bullish_below_18(self):
        assert score_vix(15.0) == 1

    def test_bearish_above_25(self):
        assert score_vix(28.0) == -1

    def test_neutral_between_18_and_25(self):
        assert score_vix(21.0) == 0

    def test_boundary_18_is_neutral(self):
        assert score_vix(18.0) == 0

    def test_boundary_25_is_neutral(self):
        assert score_vix(25.0) == 0


class TestScoreBreadth:
    def test_bullish_above_60pct(self):
        assert score_breadth(0.65) == 1

    def test_bearish_below_40pct(self):
        assert score_breadth(0.35) == -1

    def test_neutral_between(self):
        assert score_breadth(0.50) == 0

    def test_none_returns_zero(self):
        assert score_breadth(None) == 0


class TestScoreSectorRotation:
    def test_bullish_when_growth_leads(self):
        returns = {"XLK": 0.02, "XLY": 0.015, "XLU": 0.005, "XLP": 0.003, "XLV": 0.004}
        assert score_sector_rotation(returns) == 1

    def test_bearish_when_defensives_lead(self):
        returns = {"XLK": 0.002, "XLY": 0.001, "XLU": 0.015, "XLP": 0.012, "XLV": 0.010}
        assert score_sector_rotation(returns) == -1

    def test_neutral_when_difference_below_threshold(self):
        returns = {"XLK": 0.01, "XLY": 0.01, "XLU": 0.01, "XLP": 0.01, "XLV": 0.01}
        assert score_sector_rotation(returns) == 0

    def test_returns_zero_on_empty_dict(self):
        assert score_sector_rotation({}) == 0


class TestScorePutCall:
    def test_bullish_below_0_85(self):
        assert score_put_call(0.75) == 1

    def test_bearish_above_1_1(self):
        assert score_put_call(1.2) == -1

    def test_neutral_in_range(self):
        assert score_put_call(0.95) == 0

    def test_none_returns_zero(self):
        assert score_put_call(None) == 0


class TestGetRegimeTier:
    def test_strong_bull_at_plus_4(self):
        regime, risk = get_regime_tier(4)
        assert regime == "Strong Bull"
        assert risk == pytest.approx(0.015)

    def test_bull_at_plus_2(self):
        regime, _ = get_regime_tier(2)
        assert regime == "Bull"

    def test_choppy_at_zero(self):
        regime, _ = get_regime_tier(0)
        assert regime == "Choppy/Neutral"

    def test_choppy_at_minus_1(self):
        regime, _ = get_regime_tier(-1)
        assert regime == "Choppy/Neutral"

    def test_bear_at_minus_2(self):
        regime, _ = get_regime_tier(-2)
        assert regime == "Bear"

    def test_strong_bear_at_minus_4(self):
        regime, risk = get_regime_tier(-4)
        assert regime == "Strong Bear"
        assert risk == pytest.approx(0.005)


class TestComputeRegime:
    def test_returns_all_expected_keys(self):
        hist = make_qqq_hist(20, close=410, ema_20=400, ema_50=390)
        result = compute_regime(
            qqq_hist=hist, vix=15.0, breadth=0.65,
            sector_returns={"XLK": 0.02, "XLY": 0.015, "XLU": 0.003, "XLP": 0.002, "XLV": 0.001},
            pc_ratio=0.75,
        )
        for key in ("scores", "total_score", "regime", "risk_pct",
                    "dollar_risk", "long_setups", "short_setups"):
            assert key in result

    def test_strong_bull_all_factors_bullish(self):
        hist = make_qqq_hist(20, close=410, ema_20=400, ema_50=390)
        result = compute_regime(
            qqq_hist=hist, vix=14.0, breadth=0.70,
            sector_returns={"XLK": 0.02, "XLY": 0.015, "XLU": 0.001, "XLP": 0.001, "XLV": 0.001},
            pc_ratio=0.70,
        )
        assert result["regime"] in ("Strong Bull", "Bull")
        assert result["long_setups"] == ["orb", "ema_pullback", "vwap_reclaim"]

    def test_strong_bear_blocks_long_setups(self):
        hist = make_qqq_hist(20, close=360, ema_20=380, ema_50=390)
        result = compute_regime(
            qqq_hist=hist, vix=32.0, breadth=0.20,
            sector_returns={"XLK": -0.02, "XLY": -0.015, "XLU": 0.01, "XLP": 0.01, "XLV": 0.01},
            pc_ratio=1.3,
        )
        assert result["regime"] in ("Strong Bear", "Bear")
        assert result["long_setups"] == [] or result["long_setups"] == ["vwap_reclaim"]
