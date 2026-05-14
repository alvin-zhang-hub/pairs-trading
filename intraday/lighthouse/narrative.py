"""Narrative layer for the Lighthouse scanner.

For each scanner hit we surface three things to support fast triage:
  1. Sector + industry (from yfinance, already in the quote bundle)
  2. Business summary (truncated for at-a-glance scanning)
  3. Theme tags (user-curated `themes/*.txt` ticker lists)

The theme system is opt-in: empty themes/ directory means no tags. Users
populate theme files over time as patterns crystallize (e.g. ai-infra.txt,
nuclear.txt, reshoring.txt). Tags appear in the output's `themes` column
so you can filter the dashboard later (e.g. "show me all hits in `nuclear`").
"""
from __future__ import annotations

import glob
import os
from typing import Dict, List, Set

import pandas as pd

DEFAULT_SUMMARY_MAX_CHARS = 400


def load_themes(themes_dir: str) -> Dict[str, Set[str]]:
    """Return {theme_name: {ticker, ...}} for every `*.txt` file in the directory.

    Each line is one ticker. Blank lines and lines starting with `#` are ignored.
    Tickers are uppercased.
    """
    if not os.path.isdir(themes_dir):
        return {}
    themes: Dict[str, Set[str]] = {}
    for path in glob.glob(os.path.join(themes_dir, "*.txt")):
        name = os.path.splitext(os.path.basename(path))[0]
        tickers: Set[str] = set()
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                tickers.add(line.upper())
        themes[name] = tickers
    return themes


def match_themes(ticker: str, themes: Dict[str, Set[str]]) -> List[str]:
    return sorted(name for name, members in themes.items() if ticker in members)


def truncate_summary(text, max_chars: int = DEFAULT_SUMMARY_MAX_CHARS) -> str:
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= max_chars:
        return text
    # Try to truncate at the last word boundary inside the limit
    cutoff = text.rfind(" ", 0, max_chars)
    if cutoff == -1 or cutoff < max_chars // 2:
        cutoff = max_chars
    return text[:cutoff].rstrip() + "..."


def enrich_dataframe(
    df: pd.DataFrame,
    themes_dir: str,
    summary_max_chars: int = DEFAULT_SUMMARY_MAX_CHARS,
) -> pd.DataFrame:
    """Add `themes` column and truncate `business_summary` in place on a copy."""
    out = df.copy()
    themes = load_themes(themes_dir)

    if "business_summary" in out.columns:
        out["business_summary"] = out["business_summary"].apply(
            lambda s: truncate_summary(s, max_chars=summary_max_chars)
        )
    else:
        out["business_summary"] = ""

    if "ticker" in out.columns:
        out["themes"] = out["ticker"].apply(lambda t: match_themes(t, themes))
    else:
        out["themes"] = [[] for _ in range(len(out))]

    return out
