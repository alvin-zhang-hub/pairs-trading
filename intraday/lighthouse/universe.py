"""Fetch and clean the US-listed common-stock universe from Nasdaq Trader.

Two source files (pipe-delimited, daily-refreshed):
  - nasdaqlisted.txt  — Nasdaq stocks
  - otherlisted.txt   — NYSE, NYSE American, NYSE Arca

We exclude ETFs, test issues, warrants, units, rights, and preferred shares.
Symbols are normalized to Yahoo Finance format (e.g. BRK.A -> BRK-A).
"""
from __future__ import annotations

import json
import os
from datetime import date
from io import StringIO
from typing import List

import pandas as pd
import requests

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

# Suffix patterns indicating non-common-stock securities
NON_COMMON_SUFFIXES = ("W", "WS", "U", "R")
NAME_EXCLUSION_KEYWORDS = ("warrant", "unit", "preferred", "rights", "depositary")


def _parse_pipe_table(text: str, symbol_field: str) -> List[dict]:
    if not text.strip():
        return []
    df = pd.read_csv(StringIO(text), sep="|", dtype=str)
    records = []
    for _, row in df.iterrows():
        symbol = row.get(symbol_field)
        if symbol is None or (isinstance(symbol, float) and pd.isna(symbol)):
            continue
        symbol = str(symbol).strip()
        if not symbol or symbol.startswith("File Creation Time"):
            continue
        records.append({
            "symbol": symbol,
            "security_name": str(row.get("Security Name", "") or "").strip(),
            "etf": str(row.get("ETF", "N") or "N").strip(),
            "test_issue": str(row.get("Test Issue", "N") or "N").strip(),
        })
    return records


def parse_nasdaq_listed(text: str) -> List[dict]:
    return _parse_pipe_table(text, symbol_field="Symbol")


def parse_other_listed(text: str) -> List[dict]:
    return _parse_pipe_table(text, symbol_field="ACT Symbol")


def is_common_stock(record: dict) -> bool:
    if record.get("etf") == "Y":
        return False
    if record.get("test_issue") == "Y":
        return False

    symbol = record.get("symbol", "")
    if "$" in symbol:  # NYSE preferred-shares delimiter
        return False

    # Trailing-character heuristic for warrants/units/rights.
    # A 4+ letter symbol ending in W/WS/U/R is almost always a non-common-stock derivative.
    # We protect tickers shorter than 4 chars (e.g. "U", "F") to avoid false-positives
    # on legitimate single-letter or 3-letter common stocks.
    if len(symbol) >= 5:
        for suffix in NON_COMMON_SUFFIXES:
            if symbol.endswith(suffix):
                return False

    name_lower = record.get("security_name", "").lower()
    for kw in NAME_EXCLUSION_KEYWORDS:
        if kw in name_lower:
            return False

    return True


def to_yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def build_universe(nasdaq_text: str, other_text: str) -> List[str]:
    records = parse_nasdaq_listed(nasdaq_text) + parse_other_listed(other_text)
    tickers = {
        to_yahoo_symbol(r["symbol"])
        for r in records
        if is_common_stock(r)
    }
    return sorted(tickers)


def _http_get(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_universe(cache_dir: str | None = None) -> List[str]:
    """Download the listed files and build a clean universe.

    If `cache_dir` is provided, cache results to `<cache_dir>/universe_<YYYY-MM-DD>.json`
    and reuse same-day cache to avoid re-hitting the FTP HTTP endpoint.
    """
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"universe_{date.today().isoformat()}.json")
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                return json.load(f)

    nasdaq = _http_get(NASDAQ_LISTED_URL)
    other = _http_get(OTHER_LISTED_URL)
    universe = build_universe(nasdaq, other)

    if cache_dir:
        with open(cache_path, "w") as f:
            json.dump(universe, f)

    return universe
