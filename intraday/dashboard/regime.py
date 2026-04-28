THRESHOLD = 0.005  # 0.5%

_TRANSLATIONS = {
    "Buyers in Control": "Risk-on environment, money flowing into riskier assets",
    "Defensive Tone":    "Money hiding in mega-caps, avoid aggressive longs",
    "Choppy Action":     "No strong sector leadership, market lacks conviction",
}

_COLORS = {
    "Buyers in Control": "#4ade80",
    "Defensive Tone":    "#f97316",
    "Choppy Action":     "#facc15",
}


def format_bullet(label: str, delta: float) -> str:
    """Format a relative-performance bullet line."""
    pct = delta * 100
    if delta > THRESHOLD:
        return f"{label} outperforming market ({pct:+.1f}%)"
    if delta < -THRESHOLD:
        return f"{label} underperforming market ({pct:+.1f}%)"
    return f"{label} neutral vs market ({pct:+.1f}%)"


def classify_regime(
    qqq_vs_spy: float,
    iwm_vs_spy: float,
    spy_week_return: float,
) -> dict:
    """
    Classify market regime from weekly index return deltas.

    Returns:
        {
            "label": str,
            "color": str,
            "bullets": [str, str],
            "translation": str,
        }
    """
    risk_on   = iwm_vs_spy > THRESHOLD
    tech_lead = qqq_vs_spy > THRESHOLD
    spy_green = spy_week_return > 0

    if risk_on and spy_green:
        label = "Buyers in Control"
    elif (not risk_on) and (not tech_lead) and (not spy_green):
        label = "Defensive Tone"
    else:
        label = "Choppy Action"

    return {
        "label":       label,
        "color":       _COLORS[label],
        "bullets":     [
            format_bullet("Tech", qqq_vs_spy),
            format_bullet("Small caps", iwm_vs_spy),
        ],
        "translation": _TRANSLATIONS[label],
    }
