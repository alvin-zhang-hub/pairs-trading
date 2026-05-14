"""Growth-inflection fundamental score (0-10) for the Lighthouse scanner.

The scoring philosophy: we're hunting for *future market leaders at an
inflection point*, not deep-value names. So every component rewards
*positive momentum in the business*, not absolute cheapness.

  Component                Max   Rule
  --------                 ---   ----
  Revenue growth (YoY)     3     >40% / 25-40% / 15-25% / <15%
  Gross margin expansion   2     2 / 1 / 0 consecutive Q/Q expansions
  Profitability path       2     FCF>0 (2) | op-loss narrowing 2+ Qs (1)
  Forward PE compression   2     fwdPE/trailPE < 0.7 (2) | <0.85 (1)
  Earnings beat            1     earningsQuarterlyGrowth > 0

All five components return 0 on missing/insufficient data — yfinance gives
inconsistent coverage for small caps, and we'd rather a low score than a crash.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

# Thresholds
REV_TIER_HIGH = 0.40
REV_TIER_MID = 0.25
REV_TIER_LOW = 0.15
PE_COMPRESS_STRONG = 0.70
PE_COMPRESS_MILD = 0.85

# Line item names yfinance uses
REVENUE_ROW = "Total Revenue"
GROSS_PROFIT_ROW = "Gross Profit"
OPERATING_INCOME_ROW = "Operating Income"
FCF_ROW = "Free Cash Flow"


def _row_values_recent_first(df: Optional[pd.DataFrame], row_name: str) -> Optional[List[float]]:
    """Return a row's values as floats, ordered most-recent-first.

    yfinance columns are typically sorted with the most recent date leftmost;
    we sort defensively anyway. Returns None if the row or DataFrame is missing.
    """
    if df is None or len(df) == 0 or row_name not in df.index:
        return None
    series = df.loc[row_name]
    try:
        sorted_series = series.sort_index(ascending=False)
    except TypeError:
        sorted_series = series  # non-comparable index — accept yfinance order
    return [float(v) for v in sorted_series.values if pd.notna(v)]


# -----------------------------------------------------------------------------
# 1. Revenue growth (Y/Y)
# -----------------------------------------------------------------------------

def score_revenue_growth(quarterly_financials: Optional[pd.DataFrame]) -> int:
    rev = _row_values_recent_first(quarterly_financials, REVENUE_ROW)
    if rev is None or len(rev) < 5:
        return 0
    latest = rev[0]
    a_year_ago = rev[4]
    if a_year_ago <= 0:
        return 0
    yoy = latest / a_year_ago - 1
    if yoy > REV_TIER_HIGH:
        return 3
    if yoy > REV_TIER_MID:
        return 2
    if yoy > REV_TIER_LOW:
        return 1
    return 0


# -----------------------------------------------------------------------------
# 2. Gross margin expansion
# -----------------------------------------------------------------------------

def _gross_margins(quarterly_financials: Optional[pd.DataFrame]) -> List[float]:
    rev = _row_values_recent_first(quarterly_financials, REVENUE_ROW)
    gp = _row_values_recent_first(quarterly_financials, GROSS_PROFIT_ROW)
    if rev is None or gp is None:
        return []
    margins: List[float] = []
    for r, g in zip(rev, gp):
        if r <= 0:
            return []  # bail on any zero/negative revenue quarter
        margins.append(g / r)
    return margins


def score_margin_expansion(quarterly_financials: Optional[pd.DataFrame]) -> int:
    margins = _gross_margins(quarterly_financials)
    if len(margins) < 3:
        return 0
    score = 0
    # Most recent quarter expanded vs prior
    if margins[0] > margins[1]:
        score += 1
        # Prior quarter also expanded vs the one before — two consecutive
        if margins[1] > margins[2]:
            score += 1
    return score


# -----------------------------------------------------------------------------
# 3. Profitability path
# -----------------------------------------------------------------------------

def score_profitability_path(
    quarterly_financials: Optional[pd.DataFrame],
    quarterly_cashflow: Optional[pd.DataFrame],
) -> int:
    # 2 pts if latest FCF positive
    fcf = _row_values_recent_first(quarterly_cashflow, FCF_ROW)
    if fcf and len(fcf) >= 1 and fcf[0] > 0:
        return 2

    # 1 pt if operating losses narrowing for 2+ consecutive quarters
    op_inc = _row_values_recent_first(quarterly_financials, OPERATING_INCOME_ROW)
    if op_inc and len(op_inc) >= 3:
        # All three must be negative AND each more recent value is greater (less negative)
        if op_inc[0] < 0 and op_inc[1] < 0 and op_inc[2] < 0:
            if op_inc[0] > op_inc[1] > op_inc[2]:
                return 1
    return 0


# -----------------------------------------------------------------------------
# 4. Forward PE compression (proxy for analyst upward revisions)
# -----------------------------------------------------------------------------

def score_pe_compression(info: Optional[dict]) -> int:
    if not info:
        return 0
    fwd = info.get("forwardPE")
    trail = info.get("trailingPE")
    if fwd is None or trail is None:
        return 0
    try:
        fwd = float(fwd)
        trail = float(trail)
    except (TypeError, ValueError):
        return 0
    if fwd <= 0 or trail <= 0:
        return 0
    ratio = fwd / trail
    if ratio < PE_COMPRESS_STRONG:
        return 2
    if ratio < PE_COMPRESS_MILD:
        return 1
    return 0


# -----------------------------------------------------------------------------
# 5. Earnings beat (proxy via EPS Y/Y growth)
# -----------------------------------------------------------------------------

def score_earnings_beat(info: Optional[dict]) -> int:
    if not info:
        return 0
    growth = info.get("earningsQuarterlyGrowth")
    if growth is None:
        return 0
    try:
        return 1 if float(growth) > 0 else 0
    except (TypeError, ValueError):
        return 0


# -----------------------------------------------------------------------------
# Aggregate
# -----------------------------------------------------------------------------

def growth_inflection_score(
    quarterly_financials: Optional[pd.DataFrame],
    quarterly_cashflow: Optional[pd.DataFrame],
    info: Optional[dict],
) -> Dict[str, int]:
    components = {
        "revenue_growth": score_revenue_growth(quarterly_financials),
        "margin_expansion": score_margin_expansion(quarterly_financials),
        "profitability_path": score_profitability_path(quarterly_financials, quarterly_cashflow),
        "pe_compression": score_pe_compression(info),
        "earnings_beat": score_earnings_beat(info),
    }
    components["total"] = sum(components.values())
    return components
