import pytest
import json
import os
from sizing.calculator import calculate_size, load_regime


class TestCalculateSizeLong:
    def test_basic_long_shares_and_targets(self):
        result = calculate_size(entry=50.0, stop=49.0, setup="orb", risk_pct=0.015)
        assert result["is_long"] is True
        assert result["shares"] == 300          # floor(20000*0.015 / 1.0)
        assert result["dollar_risk"] == pytest.approx(300.0)
        assert result["target_1"] == pytest.approx(51.0)
        assert result["target_2"] == pytest.approx(52.0)

    def test_shares_floored_not_rounded(self):
        # 20000 * 0.015 = 300, 300 / 1.1 = 272.7 → floor = 272
        result = calculate_size(entry=50.0, stop=48.9, setup="orb", risk_pct=0.015)
        assert result["shares"] == 272

    def test_no_blocks_on_valid_trade(self):
        result = calculate_size(entry=50.0, stop=49.0, setup="orb", risk_pct=0.015, atr=2.0)
        assert result["blocks"] == []


class TestCalculateSizeShort:
    def test_basic_short_shares_and_targets(self):
        result = calculate_size(entry=50.0, stop=51.0, setup="vwap_reclaim", risk_pct=0.015)
        assert result["is_long"] is False
        assert result["shares"] == 300
        assert result["target_1"] == pytest.approx(49.0)
        assert result["target_2"] == pytest.approx(48.0)

    def test_stop_distance_is_positive_for_short(self):
        result = calculate_size(entry=50.0, stop=51.5, setup="vwap_reclaim", risk_pct=0.015)
        assert result["stop_distance"] == pytest.approx(1.5)


class TestGuards:
    def test_blocks_when_stop_equals_entry(self):
        result = calculate_size(entry=50.0, stop=50.0, setup="orb", risk_pct=0.015)
        assert len(result["blocks"]) > 0

    def test_warns_when_stop_wider_than_atr(self):
        result = calculate_size(entry=50.0, stop=48.5, setup="orb", risk_pct=0.015, atr=1.0)
        assert any("ATR" in w for w in result["warnings"])

    def test_warns_when_target_beyond_2x_atr(self):
        # stop_distance=3.0 → target_2 is 6.0 from entry, but atr=2.0 → max target reach=4.0
        result = calculate_size(entry=50.0, stop=47.0, setup="orb", risk_pct=0.015, atr=2.0)
        assert any("ATR" in w for w in result["warnings"])

    def test_warns_when_position_exceeds_25pct_account(self):
        # entry=100, shares=300 → position=$30,000 > 25% of $20k ($5,000)
        result = calculate_size(entry=100.0, stop=99.0, setup="orb", risk_pct=0.015)
        assert any("25%" in w for w in result["warnings"])

    def test_blocks_when_open_risk_would_exceed_cap(self):
        result = calculate_size(
            entry=50.0, stop=49.0, setup="orb", risk_pct=0.015, open_risk=400.0
        )
        # dollar_risk=300, open_risk=400 → total=700 > 600 cap
        assert any("600" in b for b in result["blocks"])

    def test_no_block_when_open_risk_omitted(self):
        # open_risk defaults to 0 — should not trigger cap
        result = calculate_size(entry=50.0, stop=49.0, setup="orb", risk_pct=0.015)
        assert not any("600" in b for b in result["blocks"])

    def test_warns_on_orb_entry_more_than_half_pct_above_orb_high(self):
        # entry=50.30, orb_high=50.0 → 0.6% above → warning
        result = calculate_size(
            entry=50.30, stop=49.50, setup="orb", risk_pct=0.015, orb_high=50.0
        )
        assert any("ORB" in w for w in result["warnings"])

    def test_no_orb_warning_when_within_threshold(self):
        result = calculate_size(
            entry=50.20, stop=49.50, setup="orb", risk_pct=0.015, orb_high=50.0
        )
        assert not any("ORB" in w for w in result["warnings"])


class TestLoadRegime:
    def test_returns_none_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sizing.calculator.LAST_REGIME_PATH",
                            str(tmp_path / "nonexistent.json"))
        assert load_regime() is None

    def test_loads_valid_json(self, tmp_path, monkeypatch):
        path = tmp_path / "last_regime.json"
        data = {"regime": "Bull", "risk_pct": 0.0125, "dollar_risk": 250.0,
                "long_setups": ["orb"], "short_setups": ["vwap_reclaim"]}
        path.write_text(json.dumps(data))
        monkeypatch.setattr("sizing.calculator.LAST_REGIME_PATH", str(path))
        result = load_regime()
        assert result["regime"] == "Bull"
