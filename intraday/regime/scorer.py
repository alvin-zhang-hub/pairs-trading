from typing import Optional
import pandas as pd
from scanner.trend import find_swing_highs, find_swing_lows
from config import ACCOUNT_SIZE, SECTOR_GROWTH, SECTOR_DEFENSIVE

REGIME_TIERS = [
    (4,  6,  "Strong Bull",    0.015),
    (1,  3,  "Bull",           0.0125),
    (-1, 0,  "Choppy/Neutral", 0.0075),
    (-3, -2, "Bear",           0.005),
    (-6, -4, "Strong Bear",    0.005),
]

SETUP_GATES = {
    "Strong Bull":    {"long": ["orb", "ema_pullback", "vwap_reclaim"], "short": ["vwap_reclaim"]},
    "Bull":           {"long": ["orb", "ema_pullback", "vwap_reclaim"], "short": ["vwap_reclaim"]},
    "Choppy/Neutral": {"long": ["orb", "ema_pullback", "vwap_reclaim"], "short": ["orb", "ema_pullback", "vwap_reclaim"]},
    "Bear":           {"long": ["vwap_reclaim"], "short": ["orb", "ema_pullback", "vwap_reclaim"]},
    "Strong Bear":    {"long": [], "short": ["orb", "ema_pullback", "vwap_reclaim"]},
}


def score_qqq_ema(qqq_close: float, ema_20: float, ema_50: float) -> int:
    if qqq_close > ema_20 and qqq_close > ema_50 and ema_20 > ema_50:
        return 1
    if qqq_close <= ema_50 or ema_20 < ema_50:
        return -1
    return 0


def score_qqq_structure(qqq_hist: pd.DataFrame, lookback: int = 20) -> int:
    """Score QQQ price structure using 3-bar fractal over last `lookback` days."""
    recent = qqq_hist.tail(lookback)
    sh_idxs = find_swing_highs(recent["High"])
    sl_idxs = find_swing_lows(recent["Low"])
    sh_vals = [float(recent["High"].iloc[i]) for i in sh_idxs]
    sl_vals = [float(recent["Low"].iloc[i]) for i in sl_idxs]

    if len(sh_vals) < 2 or len(sl_vals) < 2:
        return 0

    hh = sh_vals[-1] > sh_vals[-2]
    hl = sl_vals[-1] > sl_vals[-2]
    lh = sh_vals[-1] < sh_vals[-2]
    ll = sl_vals[-1] < sl_vals[-2]

    if hh and hl:
        return 1
    if lh and ll:
        return -1
    return 0


def score_vix(vix: float) -> int:
    if vix < 18:
        return 1
    if vix > 25:
        return -1
    return 0


def score_breadth(breadth: Optional[float]) -> int:
    if breadth is None:
        return 0
    if breadth > 0.60:
        return 1
    if breadth < 0.40:
        return -1
    return 0


def score_sector_rotation(sector_returns: dict) -> int:
    growth = [sector_returns[t] for t in SECTOR_GROWTH if t in sector_returns]
    defensive = [sector_returns[t] for t in SECTOR_DEFENSIVE if t in sector_returns]
    if not growth or not defensive:
        return 0
    diff = sum(growth) / len(growth) - sum(defensive) / len(defensive)
    if diff > 0.005:
        return 1
    if diff < -0.005:
        return -1
    return 0


def score_put_call(pc_ratio: Optional[float]) -> int:
    if pc_ratio is None:
        return 0
    if pc_ratio < 0.85:
        return 1
    if pc_ratio > 1.1:
        return -1
    return 0


def get_regime_tier(score: int) -> tuple:
    """Map total score to (regime_name, risk_pct). Clamps to extremes."""
    for low, high, name, risk in REGIME_TIERS:
        if low <= score <= high:
            return name, risk
    return ("Strong Bull", 0.015) if score > 6 else ("Strong Bear", 0.005)


def compute_regime(
    qqq_hist: pd.DataFrame,
    vix: float,
    breadth: Optional[float],
    sector_returns: dict,
    pc_ratio: Optional[float],
) -> dict:
    """Compute full regime from all inputs. Returns a result dict."""
    close = float(qqq_hist["Close"].iloc[-1])
    ema_20 = float(qqq_hist["ema_20"].iloc[-1])
    ema_50 = float(qqq_hist["ema_50"].iloc[-1])

    scores = {
        "qqq_ema":         score_qqq_ema(close, ema_20, ema_50),
        "qqq_structure":   score_qqq_structure(qqq_hist),
        "vix":             score_vix(vix),
        "breadth":         score_breadth(breadth),
        "sector_rotation": score_sector_rotation(sector_returns),
        "put_call":        score_put_call(pc_ratio),
    }
    total = sum(scores.values())
    regime, risk_pct = get_regime_tier(total)
    gates = SETUP_GATES[regime]

    return {
        "scores":       scores,
        "total_score":  total,
        "regime":       regime,
        "risk_pct":     risk_pct,
        "dollar_risk":  round(ACCOUNT_SIZE * risk_pct, 2),
        "long_setups":  gates["long"],
        "short_setups": gates["short"],
        "factor_details": {
            "qqq_close": close, "ema_20": ema_20, "ema_50": ema_50,
            "vix": vix, "breadth": breadth,
            "sector_returns": sector_returns, "pc_ratio": pc_ratio,
        },
    }
