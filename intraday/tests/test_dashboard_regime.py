from dashboard.regime import classify_regime, format_bullet


# --- format_bullet ---

def test_format_bullet_outperforming():
    assert format_bullet("Tech", 0.008) == "Tech outperforming market (+0.8%)"


def test_format_bullet_underperforming():
    assert format_bullet("Small caps", -0.008) == "Small caps underperforming market (-0.8%)"


def test_format_bullet_neutral_positive():
    assert format_bullet("Tech", 0.003) == "Tech neutral vs market (+0.3%)"


def test_format_bullet_neutral_negative():
    assert format_bullet("Tech", -0.003) == "Tech neutral vs market (-0.3%)"


# --- classify_regime ---

def test_buyers_in_control():
    result = classify_regime(qqq_vs_spy=0.003, iwm_vs_spy=0.008, spy_week_return=0.01)
    assert result["label"] == "Buyers in Control"
    assert result["color"] == "#4ade80"


def test_buyers_in_control_requires_spy_green():
    # IWM beats SPY by >0.5% but SPY is red → not Buyers in Control
    result = classify_regime(qqq_vs_spy=0.003, iwm_vs_spy=0.008, spy_week_return=-0.001)
    assert result["label"] != "Buyers in Control"


def test_defensive_tone():
    result = classify_regime(qqq_vs_spy=-0.006, iwm_vs_spy=-0.007, spy_week_return=-0.005)
    assert result["label"] == "Defensive Tone"
    assert result["color"] == "#f97316"


def test_choppy_action_mixed_signals():
    result = classify_regime(qqq_vs_spy=0.008, iwm_vs_spy=-0.003, spy_week_return=0.005)
    assert result["label"] == "Choppy Action"
    assert result["color"] == "#facc15"


def test_choppy_action_iwm_beats_spy_but_market_red():
    result = classify_regime(qqq_vs_spy=0.003, iwm_vs_spy=0.007, spy_week_return=-0.002)
    assert result["label"] == "Choppy Action"


def test_result_has_two_bullets():
    result = classify_regime(qqq_vs_spy=0.003, iwm_vs_spy=0.008, spy_week_return=0.01)
    assert len(result["bullets"]) == 2


def test_result_has_translation():
    result = classify_regime(qqq_vs_spy=0.003, iwm_vs_spy=0.008, spy_week_return=0.01)
    assert isinstance(result["translation"], str) and len(result["translation"]) > 0


def test_all_three_regimes_have_distinct_colors():
    buyers = classify_regime(0.003, 0.008, 0.01)["color"]
    defensive = classify_regime(-0.006, -0.007, -0.005)["color"]
    choppy = classify_regime(0.008, -0.003, 0.005)["color"]
    assert len({buyers, defensive, choppy}) == 3
