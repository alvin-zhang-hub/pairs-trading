"""Hard liquidity gate for the Lighthouse small-cap scanner.

Three thresholds, all required:
  - market cap < $5B (small-cap focus)
  - last price >= $5 (filter out penny stocks / data noise)
  - 20-day average dollar volume >= $5M (tradeable size)
"""
from __future__ import annotations

import math
from typing import Mapping

import pandas as pd

MAX_MARKET_CAP = 5_000_000_000
MIN_PRICE = 5.0
MIN_ADV_DOLLAR = 5_000_000

# Industries excluded from the scanner. Biotech is binary event-driven (FDA
# approvals/rejections, trial results) — not the accumulation/inflection
# pattern this scanner is designed to find. Add keywords here (lowercase) to
# extend; matched as a case-insensitive substring against yfinance's industry.
EXCLUDED_INDUSTRY_KEYWORDS = ("biotech",)


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def _is_excluded_industry(industry) -> bool:
    if industry is None:
        return False
    text = str(industry).lower()
    return any(kw in text for kw in EXCLUDED_INDUSTRY_KEYWORDS)


def passes_gate(row: Mapping) -> bool:
    mcap = row.get("mcap")
    price = row.get("price")
    adv = row.get("adv_20d_dollar")

    if _is_missing(mcap) or _is_missing(price) or _is_missing(adv):
        return False

    if _is_excluded_industry(row.get("industry")):
        return False

    return (
        float(mcap) < MAX_MARKET_CAP
        and float(price) >= MIN_PRICE
        and float(adv) >= MIN_ADV_DOLLAR
    )


def apply_liquidity_gate(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) == 0:
        return df.reset_index(drop=True)
    mask = df.apply(passes_gate, axis=1)
    return df[mask].reset_index(drop=True)
