"""Ranking + diff helpers for the Lighthouse scanner.

The headline feature here is `mark_new_today`: comparing the current scan's
ticker set against the previous `scanner_cache.json`, flagging entries that
weren't in the prior scan. This lets the dashboard (and the CSV reader)
distinguish "fresh setups" from "names I saw yesterday."

Sort + merge logic stays in `run_scanner.py` for now; if it grows, move it here.
"""
from __future__ import annotations

import json
import os
from typing import Set

import pandas as pd


def load_prior_tickers(cache_path: str) -> Set[str]:
    """Return the set of ticker symbols from a prior `scanner_cache.json`.

    Returns an empty set if the file is missing, malformed, or has no `results`.
    """
    if not os.path.isfile(cache_path):
        return set()
    try:
        with open(cache_path) as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return set()
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return set()
    return {r["ticker"] for r in results if isinstance(r, dict) and "ticker" in r}


def mark_new_today(df: pd.DataFrame, prior_cache_path: str) -> pd.DataFrame:
    """Add a `new_today` boolean column: True when the ticker is NOT in prior cache."""
    out = df.copy()
    prior = load_prior_tickers(prior_cache_path)
    if "ticker" not in out.columns:
        out["new_today"] = pd.Series(dtype=bool)
        return out
    out["new_today"] = ~out["ticker"].isin(prior)
    return out
