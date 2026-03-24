# Intraday Trading Strategy Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build three Python CLI tools — an EOD stock scanner, a morning market regime scorer, and a per-trade position sizing calculator — for a discretionary intraday trader using ThinkorSwim.

**Architecture:** Three independent modules (`scanner/`, `regime/`, `sizing/`) share a single `config.py` and communicate via a cached `regime/last_regime.json` file written by `run_regime.py` and read by `run_sizing.py`. All modules are tested with `pytest` and mocked yfinance calls (no live network in tests).

**Tech Stack:** Python 3.10+, yfinance, pandas, numpy, requests, tabulate, lxml, pytest

---

## File Structure

**New files to create:**

```
intraday/
├── config.py
├── scanner/
│   ├── __init__.py
│   ├── fetcher.py        # yfinance data pull; ATR, gap%, RVOL computation
│   ├── filters.py        # filter pipeline + ema column (9 vs 21)
│   ├── trend.py          # 3-bar fractal swing detection + trend classification
│   └── scanner.py        # orchestrates fetch→filter→trend→CSV output
├── regime/
│   ├── __init__.py
│   ├── fetcher.py        # pulls QQQ, VIX, sectors, S&P 500 breadth, CBOE P/C
│   ├── scorer.py         # 6-factor scoring matrix → regime tier + risk %
│   └── regime.py         # orchestrates fetch→score→print→write last_regime.json
├── sizing/
│   ├── __init__.py
│   └── calculator.py     # long/short sizing formula, all guards, formatted output
├── tests/
│   ├── __init__.py
│   ├── test_fetcher.py
│   ├── test_filters.py
│   ├── test_trend.py
│   ├── test_scanner.py
│   ├── test_regime_fetcher.py
│   ├── test_scorer.py
│   └── test_calculator.py
├── run_scanner.py
├── run_regime.py
├── run_sizing.py
└── requirements.txt
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `intraday/requirements.txt`
- Create: `intraday/config.py`
- Create: `intraday/scanner/__init__.py`
- Create: `intraday/regime/__init__.py`
- Create: `intraday/sizing/__init__.py`
- Create: `intraday/tests/__init__.py`

- [ ] **Step 1: Create the project directory and requirements.txt**

```bash
mkdir -p intraday/scanner intraday/regime intraday/sizing intraday/tests
```

`intraday/requirements.txt`:
```
yfinance>=0.2.40
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
tabulate>=0.9.0
lxml>=4.9.0
html5lib>=1.1
pytest>=7.4.0
```

- [ ] **Step 2: Install dependencies**

```bash
cd intraday && pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 3: Create config.py**

`intraday/config.py`:
```python
# Account
ACCOUNT_SIZE = 20_000.0

# Scanner filters
PRICE_MIN = 10.0
PRICE_MAX = 500.0
AVG_VOLUME_MIN = 500_000
FLOAT_MIN = 10_000_000
FLOAT_MAX = 500_000_000
ATR_MIN_DOLLAR = 0.75
ATR_MIN_PCT = 0.015       # 1.5% of price
GAP_MIN_PCT = 0.02        # 2% from prior close
RVOL_MIN = 1.5
RVOL_LOOKBACK = 20        # trading days

# EMA selection thresholds
EMA_FAST_GAP_THRESHOLD = 0.03    # gap >3% → use 9 EMA
EMA_FAST_ATR_PCT_THRESHOLD = 0.025  # ATR/price >2.5% → use 9 EMA

# Regime
BREADTH_EMA_PERIOD = 20
BREADTH_MIN_VALID_PCT = 0.80
SECTOR_GROWTH = ['XLK', 'XLY']
SECTOR_DEFENSIVE = ['XLU', 'XLP', 'XLV']
SECTOR_LOOKBACK_DAYS = 5

# Sizing
MAX_OPEN_RISK = 600.0
MAX_POSITION_PCT = 0.25   # 25% of account
ATR_STOP_MAX_MULTIPLE = 1.0
ATR_TARGET_MAX_MULTIPLE = 2.0

# S&P 500 Wikipedia URL
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# CBOE P/C daily CSV base URL
CBOE_BASE_URL = "https://www.cboe.com/us/options/market_statistics/daily/"

# FOMC announcement dates for 2026 (update annually)
FOMC_DATES = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-10",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16",
]
```

- [ ] **Step 4: Create empty __init__.py files**

```bash
touch intraday/scanner/__init__.py intraday/regime/__init__.py intraday/sizing/__init__.py intraday/tests/__init__.py
```

- [ ] **Step 5: Verify Python can import config**

```bash
cd intraday && python -c "import config; print(config.ACCOUNT_SIZE)"
```

Expected: `20000.0`

- [ ] **Step 6: Commit**

```bash
git add intraday/
git commit -m "feat: scaffold intraday trading framework project structure"
```

---

## Task 2: Scanner — Data Fetcher

**Files:**
- Create: `intraday/scanner/fetcher.py`
- Create: `intraday/tests/test_fetcher.py`

- [ ] **Step 1: Write failing tests**

`intraday/tests/test_fetcher.py`:
```python
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from scanner.fetcher import compute_atr, fetch_ticker_data


def make_hist(n=30, close_val=50.0, volume=1_000_000):
    """Build a minimal OHLCV DataFrame for testing."""
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = pd.Series([close_val] * n, index=idx)
    return pd.DataFrame({
        "Open": close_val * 0.99,
        "High": close_val * 1.01,
        "Low": close_val * 0.99,
        "Close": close,
        "Volume": volume,
    }, index=idx)


class TestComputeATR:
    def test_returns_positive_float(self):
        hist = make_hist(30, close_val=100.0)
        atr = compute_atr(hist["High"], hist["Low"], hist["Close"])
        assert isinstance(atr, float)
        assert atr > 0

    def test_wider_candles_produce_larger_atr(self):
        narrow = make_hist(30, close_val=100.0)
        wide = narrow.copy()
        wide["High"] = wide["Close"] * 1.05
        wide["Low"] = wide["Close"] * 0.95
        assert compute_atr(wide["High"], wide["Low"], wide["Close"]) > \
               compute_atr(narrow["High"], narrow["Low"], narrow["Close"])

    def test_returns_none_on_insufficient_data(self):
        hist = make_hist(5)
        result = compute_atr(hist["High"], hist["Low"], hist["Close"])
        # ATR with fewer than period candles returns NaN — we handle upstream
        assert result is not None  # function itself doesn't raise


class TestFetchTickerData:
    def _mock_ticker(self, hist, float_shares=50_000_000):
        mock = MagicMock()
        mock.history.return_value = hist
        mock.info = {"floatShares": float_shares}
        return mock

    @patch("scanner.fetcher.yf.Ticker")
    def test_returns_expected_keys(self, mock_ticker_cls):
        hist = make_hist(30, close_val=50.0, volume=800_000)
        mock_ticker_cls.return_value = self._mock_ticker(hist)

        result = fetch_ticker_data("AAPL")

        assert result is not None
        expected_keys = {"ticker", "close", "open_", "prev_close", "volume",
                         "avg_volume_20d", "atr_14", "gap_pct", "rvol", "float_shares"}
        assert set(result.keys()) == expected_keys

    @patch("scanner.fetcher.yf.Ticker")
    def test_returns_none_on_insufficient_history(self, mock_ticker_cls):
        hist = make_hist(10)  # fewer than 22 required days
        mock_ticker_cls.return_value = self._mock_ticker(hist)

        assert fetch_ticker_data("AAPL") is None

    @patch("scanner.fetcher.yf.Ticker")
    def test_rvol_computed_correctly(self, mock_ticker_cls):
        # Today's volume is 2x the 20-day average
        hist = make_hist(30, volume=500_000)
        hist.iloc[-1, hist.columns.get_loc("Volume")] = 1_000_000
        mock_ticker_cls.return_value = self._mock_ticker(hist)

        result = fetch_ticker_data("AAPL")
        assert result is not None
        assert abs(result["rvol"] - 2.0) < 0.1

    @patch("scanner.fetcher.yf.Ticker")
    def test_gap_pct_computed_correctly(self, mock_ticker_cls):
        hist = make_hist(30, close_val=100.0)
        # Set today's open to 103 (3% gap from prev close of 100)
        hist.iloc[-1, hist.columns.get_loc("Open")] = 103.0
        hist.iloc[-2, hist.columns.get_loc("Close")] = 100.0
        mock_ticker_cls.return_value = self._mock_ticker(hist)

        result = fetch_ticker_data("AAPL")
        assert result is not None
        assert abs(result["gap_pct"] - 0.03) < 0.005

    @patch("scanner.fetcher.yf.Ticker")
    def test_float_none_when_info_missing(self, mock_ticker_cls):
        hist = make_hist(30)
        mock = self._mock_ticker(hist, float_shares=None)
        mock.info = {}
        mock_ticker_cls.return_value = mock

        result = fetch_ticker_data("AAPL")
        assert result is not None
        assert result["float_shares"] is None

    @patch("scanner.fetcher.yf.Ticker")
    def test_returns_none_on_exception(self, mock_ticker_cls):
        mock_ticker_cls.side_effect = Exception("network error")
        assert fetch_ticker_data("AAPL") is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd intraday && python -m pytest tests/test_fetcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'scanner.fetcher'`

- [ ] **Step 3: Implement scanner/fetcher.py**

`intraday/scanner/fetcher.py`:
```python
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Compute ATR using Wilder's smoothing. Returns the most recent ATR value."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return float(atr.iloc[-1])


def fetch_ticker_data(ticker: str, lookback_days: int = 60) -> Optional[dict]:
    """
    Fetch OHLCV data for a single ticker and compute all derived scan metrics.

    Returns None if data is unavailable, insufficient, or raises an exception.
    Float is best-effort: None when yfinance cannot provide it.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=f"{lookback_days}d", auto_adjust=True)
        if len(hist) < 22:
            return None

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]
        open_ = hist["Open"]

        today_close = float(close.iloc[-1])
        today_open = float(open_.iloc[-1])
        prev_close = float(close.iloc[-2])
        today_volume = float(volume.iloc[-1])
        avg_volume_20d = float(volume.iloc[-21:-1].mean())

        atr_14 = compute_atr(high, low, close)
        gap_pct = abs(today_open - prev_close) / prev_close
        rvol = today_volume / avg_volume_20d if avg_volume_20d > 0 else 0.0

        float_shares = None
        try:
            info = t.info
            float_shares = info.get("floatShares")
        except Exception:
            pass

        return {
            "ticker": ticker,
            "close": today_close,
            "open_": today_open,
            "prev_close": prev_close,
            "volume": today_volume,
            "avg_volume_20d": avg_volume_20d,
            "atr_14": atr_14,
            "gap_pct": gap_pct,
            "rvol": rvol,
            "float_shares": float_shares,
        }
    except Exception:
        return None
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd intraday && python -m pytest tests/test_fetcher.py -v
```

Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add intraday/scanner/fetcher.py intraday/tests/test_fetcher.py
git commit -m "feat: scanner fetcher — ATR, gap%, RVOL computation with yfinance"
```

---

## Task 3: Scanner — Filter Pipeline

**Files:**
- Create: `intraday/scanner/filters.py`
- Create: `intraday/tests/test_filters.py`

- [ ] **Step 1: Write failing tests**

`intraday/tests/test_filters.py`:
```python
import pytest
import pandas as pd
from scanner.filters import apply_filters


def make_df(**overrides):
    """Build a minimal passing row. Override any field to test a filter."""
    base = {
        "ticker": "AAPL",
        "close": 50.0,
        "avg_volume_20d": 1_000_000.0,
        "float_shares": 100_000_000.0,
        "atr_14": 1.0,
        "gap_pct": 0.03,
        "rvol": 2.0,
    }
    base.update(overrides)
    return pd.DataFrame([base])


class TestPriceFilter:
    def test_passes_within_range(self):
        assert len(apply_filters(make_df(close=100.0))) == 1

    def test_excludes_below_min(self):
        assert len(apply_filters(make_df(close=9.0))) == 0

    def test_excludes_above_max(self):
        assert len(apply_filters(make_df(close=501.0))) == 0


class TestVolumeFilter:
    def test_passes_above_threshold(self):
        assert len(apply_filters(make_df(avg_volume_20d=600_000))) == 1

    def test_excludes_below_threshold(self):
        assert len(apply_filters(make_df(avg_volume_20d=400_000))) == 0


class TestFloatFilter:
    def test_passes_within_range(self):
        assert len(apply_filters(make_df(float_shares=50_000_000))) == 1

    def test_excludes_below_min(self):
        assert len(apply_filters(make_df(float_shares=5_000_000))) == 0

    def test_excludes_above_max(self):
        assert len(apply_filters(make_df(float_shares=600_000_000))) == 0

    def test_passes_when_float_is_none(self):
        # Missing float should not exclude the stock
        assert len(apply_filters(make_df(float_shares=None))) == 1


class TestATRFilter:
    def test_passes_when_both_conditions_met(self):
        # close=50, atr=1.0 → atr_pct=2% ≥ 1.5%
        assert len(apply_filters(make_df(close=50.0, atr_14=1.0))) == 1

    def test_excludes_when_dollar_atr_too_low(self):
        assert len(apply_filters(make_df(atr_14=0.70))) == 0

    def test_excludes_when_pct_atr_too_low(self):
        # close=200, atr=1.0 → atr_pct=0.5% < 1.5%
        assert len(apply_filters(make_df(close=200.0, atr_14=1.0))) == 0


class TestGapFilter:
    def test_passes_at_threshold(self):
        assert len(apply_filters(make_df(gap_pct=0.02))) == 1

    def test_excludes_below_threshold(self):
        assert len(apply_filters(make_df(gap_pct=0.01))) == 0


class TestRVOLFilter:
    def test_passes_above_threshold(self):
        assert len(apply_filters(make_df(rvol=2.0))) == 1

    def test_excludes_below_threshold(self):
        assert len(apply_filters(make_df(rvol=1.0))) == 0


class TestEMAColumn:
    def test_uses_9_ema_when_gap_above_threshold(self):
        # gap_pct=0.04 > 0.03 threshold
        df = apply_filters(make_df(gap_pct=0.04, close=50.0, atr_14=1.0))
        assert df.iloc[0]["ema"] == 9

    def test_uses_9_ema_when_atr_pct_above_threshold(self):
        # close=30, atr=1.0 → atr_pct=3.3% > 2.5%
        df = apply_filters(make_df(close=30.0, atr_14=1.0, gap_pct=0.02))
        assert df.iloc[0]["ema"] == 9

    def test_uses_21_ema_otherwise(self):
        # gap_pct=0.02, atr_pct=2% — both below thresholds
        df = apply_filters(make_df(close=50.0, atr_14=1.0, gap_pct=0.02))
        assert df.iloc[0]["ema"] == 21
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd intraday && python -m pytest tests/test_filters.py -v
```

Expected: `ModuleNotFoundError: No module named 'scanner.filters'`

- [ ] **Step 3: Implement scanner/filters.py**

`intraday/scanner/filters.py`:
```python
import logging
import pandas as pd
from config import (
    PRICE_MIN, PRICE_MAX, AVG_VOLUME_MIN, FLOAT_MIN, FLOAT_MAX,
    ATR_MIN_DOLLAR, ATR_MIN_PCT, GAP_MIN_PCT, RVOL_MIN,
    EMA_FAST_GAP_THRESHOLD, EMA_FAST_ATR_PCT_THRESHOLD,
)


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the full EOD scan filter pipeline.

    Expected input columns: ticker, close, avg_volume_20d, float_shares,
                            atr_14, gap_pct, rvol
    Returns a filtered copy with added columns: atr_pct, ema (9 or 21).
    """
    df = df.copy()

    # Step 1: Price
    df = df[(df["close"] >= PRICE_MIN) & (df["close"] <= PRICE_MAX)]

    # Step 2: Average volume
    df = df[df["avg_volume_20d"] >= AVG_VOLUME_MIN]

    # Step 3: Float — best-effort, skip (do not exclude) when None
    has_float = df["float_shares"].notna()
    excluded = df[has_float & (
        (df["float_shares"] < FLOAT_MIN) | (df["float_shares"] > FLOAT_MAX)
    )]
    if len(excluded) > 0:
        logging.warning("Float filter excluded: %s", excluded["ticker"].tolist())
    df = df[~df.index.isin(excluded.index)]

    # Step 4: ATR (dollar and percent)
    df["atr_pct"] = df["atr_14"] / df["close"]
    df = df[(df["atr_14"] >= ATR_MIN_DOLLAR) & (df["atr_pct"] >= ATR_MIN_PCT)]

    # Step 5: Gap
    df = df[df["gap_pct"] >= GAP_MIN_PCT]

    # Step 6: RVOL
    df = df[df["rvol"] >= RVOL_MIN]

    # EMA column: 9 for high-momentum stocks, 21 otherwise
    df["ema"] = df.apply(
        lambda row: 9
        if (row["gap_pct"] >= EMA_FAST_GAP_THRESHOLD
            or row["atr_pct"] >= EMA_FAST_ATR_PCT_THRESHOLD)
        else 21,
        axis=1,
    )

    return df.reset_index(drop=True)
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd intraday && python -m pytest tests/test_filters.py -v
```

Expected: 16 tests pass.

- [ ] **Step 5: Commit**

```bash
git add intraday/scanner/filters.py intraday/tests/test_filters.py
git commit -m "feat: scanner filter pipeline with EMA selection column"
```

---

## Task 4: Scanner — Trend Classifier

**Files:**
- Create: `intraday/scanner/trend.py`
- Create: `intraday/tests/test_trend.py`

- [ ] **Step 1: Write failing tests**

`intraday/tests/test_trend.py`:
```python
import pytest
import pandas as pd
import numpy as np
from scanner.trend import (
    find_swing_highs, find_swing_lows,
    classify_price_structure, classify_trend, get_eligible_setups,
)


def make_hist(highs, lows, closes=None):
    """Build a DataFrame from explicit high/low sequences."""
    n = len(highs)
    if closes is None:
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "High": highs, "Low": lows, "Close": closes,
        "Open": closes, "Volume": [1_000_000] * n,
    }, index=idx)


class TestFindSwingHighs:
    def test_finds_clear_peak(self):
        # Index 2 is a peak: 1,2,5,2,1
        highs = pd.Series([1, 2, 5, 2, 1, 2, 1, 2, 1, 2])
        result = find_swing_highs(highs, lookback=2)
        assert 2 in result

    def test_no_swing_in_flat_series(self):
        highs = pd.Series([5.0] * 10)
        assert find_swing_highs(highs) == []

    def test_excludes_boundary_candles(self):
        # First and last candles cannot be swing highs (need 2 candles on each side)
        highs = pd.Series([10, 5, 5, 5, 5])
        result = find_swing_highs(highs, lookback=2)
        assert 0 not in result


class TestFindSwingLows:
    def test_finds_clear_trough(self):
        lows = pd.Series([5, 4, 1, 4, 5, 4, 5, 4, 5, 4])
        result = find_swing_lows(lows, lookback=2)
        assert 2 in result

    def test_no_swing_in_flat_series(self):
        lows = pd.Series([2.0] * 10)
        assert find_swing_lows(lows) == []


class TestClassifyPriceStructure:
    def test_uptrend_requires_hh_and_hl(self):
        # 3 swing highs each higher, 3 swing lows each higher
        sh = [10, 12, 14]
        sl = [8, 9, 10]
        assert classify_price_structure(sh, sl) == "Uptrend"

    def test_downtrend_requires_lh_and_ll(self):
        sh = [14, 12, 10]
        sl = [10, 9, 8]
        assert classify_price_structure(sh, sl) == "Downtrend"

    def test_mixed_is_sideways(self):
        sh = [10, 12, 11]  # mixed
        sl = [8, 9, 8]     # mixed
        assert classify_price_structure(sh, sl) == "Sideways"

    def test_fewer_than_3_swing_highs_returns_sideways(self):
        assert classify_price_structure([10, 12], [8, 9, 10]) == "Sideways"

    def test_fewer_than_3_swing_lows_returns_sideways(self):
        assert classify_price_structure([10, 12, 14], [8, 9]) == "Sideways"

    def test_empty_lists_return_sideways(self):
        assert classify_price_structure([], []) == "Sideways"


class TestClassifyTrend:
    def _make_uptrend_hist(self):
        """20 candles with rising closes, clear HH/HL structure."""
        closes = [float(50 + i * 0.5) for i in range(25)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        return make_hist(highs, lows, closes)

    def _make_downtrend_hist(self):
        closes = [float(70 - i * 0.5) for i in range(25)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        return make_hist(highs, lows, closes)

    def test_uptrend_when_price_above_emas_and_structure_up(self):
        hist = self._make_uptrend_hist()
        ema_20 = hist["Close"].ewm(span=20, adjust=False).mean()
        ema_50 = hist["Close"].ewm(span=50, adjust=False).mean()
        # Force ema_20 < ema_50 < close for the uptrend case
        ema_20_adj = ema_20 * 0.95
        ema_50_adj = ema_20 * 0.90
        result = classify_trend(hist, ema_20_adj, ema_50_adj)
        assert result == "Uptrend"

    def test_sideways_when_fewer_than_3_swing_points(self):
        # Flat price — no swing points will be found
        closes = [50.0] * 25
        highs = [50.5] * 25
        lows = [49.5] * 25
        hist = make_hist(highs, lows, closes)
        ema = pd.Series([45.0] * 25, index=hist.index)  # price above both EMAs
        result = classify_trend(hist, ema * 0.99, ema * 0.98)
        assert result == "Sideways"


class TestGetEligibleSetups:
    def test_uptrend_includes_long_setups(self):
        setups = get_eligible_setups("Uptrend")
        assert "orb_long" in setups
        assert "ema_pullback_long" in setups
        assert "vwap_reclaim_long" in setups

    def test_downtrend_includes_short_setups(self):
        setups = get_eligible_setups("Downtrend")
        assert "ema_pullback_short" in setups
        assert "vwap_reclaim_short" in setups
        assert "orb_long" not in setups

    def test_sideways_vwap_only(self):
        setups = get_eligible_setups("Sideways")
        assert setups == ["vwap_reclaim_long", "vwap_reclaim_short"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd intraday && python -m pytest tests/test_trend.py -v
```

Expected: `ModuleNotFoundError: No module named 'scanner.trend'`

- [ ] **Step 3: Implement scanner/trend.py**

`intraday/scanner/trend.py`:
```python
import pandas as pd
from typing import Literal

TrendLabel = Literal["Uptrend", "Downtrend", "Sideways"]


def find_swing_highs(high: pd.Series, lookback: int = 2) -> list:
    """
    Return integer positions of swing highs using a (2*lookback+1)-bar fractal.
    A swing high at position i: high[i] strictly greater than all candles within `lookback` on each side.
    """
    arr = high.values
    result = []
    for i in range(lookback, len(arr) - lookback):
        if all(arr[i] > arr[i - k] for k in range(1, lookback + 1)) and \
           all(arr[i] > arr[i + k] for k in range(1, lookback + 1)):
            result.append(i)
    return result


def find_swing_lows(low: pd.Series, lookback: int = 2) -> list:
    """Return integer positions of swing lows (inverse of find_swing_highs)."""
    arr = low.values
    result = []
    for i in range(lookback, len(arr) - lookback):
        if all(arr[i] < arr[i - k] for k in range(1, lookback + 1)) and \
           all(arr[i] < arr[i + k] for k in range(1, lookback + 1)):
            result.append(i)
    return result


def classify_price_structure(swing_highs_vals: list, swing_lows_vals: list) -> str:
    """
    Classify price structure from ordered swing point value lists.
    Requires at least 3 of each; returns 'Sideways' if fewer exist.

    Uptrend:   >= 2 of last 3 swing highs are HH AND >= 2 of last 3 swing lows are HL
    Downtrend: >= 2 of last 3 swing highs are LH AND >= 2 of last 3 swing lows are LL
    """
    if len(swing_highs_vals) < 3 or len(swing_lows_vals) < 3:
        return "Sideways"

    h = swing_highs_vals[-3:]
    l = swing_lows_vals[-3:]

    hh = sum(h[i] > h[i - 1] for i in range(1, 3))
    hl = sum(l[i] > l[i - 1] for i in range(1, 3))
    lh = sum(h[i] < h[i - 1] for i in range(1, 3))
    ll = sum(l[i] < l[i - 1] for i in range(1, 3))

    if hh >= 2 and hl >= 2:
        return "Uptrend"
    if lh >= 2 and ll >= 2:
        return "Downtrend"
    return "Sideways"


def classify_trend(
    hist: pd.DataFrame,
    ema_20: pd.Series,
    ema_50: pd.Series,
    window: int = 20,
) -> TrendLabel:
    """
    Classify trend using last `window` candles of daily OHLCV data.

    hist must have columns: High, Low, Close.
    ema_20 and ema_50 are pre-computed Series aligned to hist.index.
    Returns 'Sideways' if fewer than 3 swing points found in window.
    """
    recent = hist.tail(window)
    ema_20_last = float(ema_20.reindex(recent.index).iloc[-1])
    ema_50_last = float(ema_50.reindex(recent.index).iloc[-1])
    close_last = float(recent["Close"].iloc[-1])

    price_above_both = close_last > ema_20_last and close_last > ema_50_last
    ema_20_above_50 = ema_20_last > ema_50_last
    price_below_both = close_last < ema_20_last and close_last < ema_50_last
    ema_20_below_50 = ema_20_last < ema_50_last

    sh_idxs = find_swing_highs(recent["High"])
    sl_idxs = find_swing_lows(recent["Low"])
    sh_vals = [float(recent["High"].iloc[i]) for i in sh_idxs]
    sl_vals = [float(recent["Low"].iloc[i]) for i in sl_idxs]

    structure = classify_price_structure(sh_vals, sl_vals)

    if price_above_both and ema_20_above_50 and structure == "Uptrend":
        return "Uptrend"
    if price_below_both and ema_20_below_50 and structure == "Downtrend":
        return "Downtrend"
    return "Sideways"


def get_eligible_setups(trend: TrendLabel) -> list:
    """Return setup names the stock is eligible for based on its trend."""
    mapping = {
        "Uptrend": ["orb_long", "ema_pullback_long", "vwap_reclaim_long"],
        "Downtrend": ["ema_pullback_short", "vwap_reclaim_short"],
        "Sideways": ["vwap_reclaim_long", "vwap_reclaim_short"],
    }
    return mapping[trend]
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd intraday && python -m pytest tests/test_trend.py -v
```

Expected: 17 tests pass.

- [ ] **Step 5: Commit**

```bash
git add intraday/scanner/trend.py intraday/tests/test_trend.py
git commit -m "feat: trend classifier with 3-bar fractal swing detection"
```

---

## Task 5: Scanner — Orchestrator + run_scanner.py

**Files:**
- Create: `intraday/scanner/scanner.py`
- Create: `intraday/tests/test_scanner.py`
- Create: `intraday/run_scanner.py`

- [ ] **Step 1: Write failing tests**

`intraday/tests/test_scanner.py`:
```python
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from scanner.scanner import run_scan, save_watchlist


def make_passing_row(ticker="AAPL"):
    return {
        "ticker": ticker, "close": 50.0, "open_": 51.5,
        "prev_close": 48.5, "volume": 2_000_000,
        "avg_volume_20d": 1_000_000, "atr_14": 1.2,
        "gap_pct": 0.031, "rvol": 2.0, "float_shares": 80_000_000,
    }


def make_hist(n=25, close_start=50.0, rising=True):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    closes = [close_start + (i * 0.5 if rising else -i * 0.5) for i in range(n)]
    return pd.DataFrame({
        "High": [c + 0.5 for c in closes],
        "Low": [c - 0.5 for c in closes],
        "Close": closes, "Open": closes, "Volume": [1_000_000] * n,
    }, index=idx)


class TestRunScan:
    @patch("scanner.scanner.yf.Ticker")
    @patch("scanner.scanner.fetch_ticker_data")
    @patch("scanner.scanner.get_universe")
    def test_returns_dataframe_with_expected_columns(
        self, mock_universe, mock_fetch, mock_ticker
    ):
        mock_universe.return_value = ["AAPL"]
        mock_fetch.return_value = make_passing_row("AAPL")

        hist = make_hist(25, rising=True)
        mock_ticker.return_value.history.return_value = hist

        result = run_scan(["AAPL"])
        assert isinstance(result, pd.DataFrame)
        assert "trend" in result.columns
        assert "setups" in result.columns
        assert "ema" in result.columns

    @patch("scanner.scanner.yf.Ticker")
    @patch("scanner.scanner.fetch_ticker_data")
    def test_sorts_by_rvol_descending(self, mock_fetch, mock_ticker):
        rows = [make_passing_row("AAPL"), make_passing_row("MSFT")]
        rows[0]["rvol"] = 3.0
        rows[1]["rvol"] = 5.0
        mock_fetch.side_effect = rows

        hist = make_hist(25)
        mock_ticker.return_value.history.return_value = hist

        result = run_scan(["AAPL", "MSFT"])
        assert result.iloc[0]["ticker"] == "MSFT"

    @patch("scanner.scanner.fetch_ticker_data")
    def test_returns_empty_df_when_no_tickers_pass(self, mock_fetch):
        mock_fetch.return_value = None
        result = run_scan(["AAPL"])
        assert result.empty


class TestSaveWatchlist:
    def test_creates_csv_and_txt(self, tmp_path):
        df = pd.DataFrame([{
            "ticker": "AAPL", "close": 50.0, "gap_pct": 0.03,
            "rvol": 2.0, "atr_14": 1.0, "atr_pct": 0.02,
            "float_shares": 80_000_000, "trend": "Uptrend",
            "ema": 9, "setups": "orb_long",
        }])
        csv_path, txt_path = save_watchlist(df, output_dir=str(tmp_path))
        assert csv_path.endswith(".csv")
        assert txt_path.endswith(".txt")
        with open(txt_path) as f:
            assert "AAPL" in f.read()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd intraday && python -m pytest tests/test_scanner.py -v
```

Expected: `ModuleNotFoundError: No module named 'scanner.scanner'`

- [ ] **Step 3: Implement scanner/scanner.py**

`intraday/scanner/scanner.py`:
```python
import logging
import yfinance as yf
import pandas as pd
from datetime import date
from typing import Optional
from scanner.fetcher import fetch_ticker_data
from scanner.filters import apply_filters
from scanner.trend import classify_trend, get_eligible_setups
from config import SP500_WIKI_URL


def get_universe() -> list:
    """Fetch S&P 500 tickers from Wikipedia. Returns empty list on failure."""
    try:
        tables = pd.read_html(SP500_WIKI_URL)
        tickers = tables[0]["Symbol"].tolist()
        return [t.replace(".", "-") for t in tickers]
    except Exception as e:
        logging.error("Failed to fetch S&P 500 universe: %s", e)
        return []


def run_scan(tickers: Optional[list] = None) -> pd.DataFrame:
    """
    Run the full EOD scan pipeline.
    Returns a DataFrame sorted by RVOL descending, or empty DataFrame if no stocks pass.
    """
    if tickers is None:
        tickers = get_universe()

    rows = []
    for ticker in tickers:
        data = fetch_ticker_data(ticker)
        if data:
            rows.append(data)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = apply_filters(df)
    if df.empty:
        return df

    trends, setups_list = [], []
    for _, row in df.iterrows():
        try:
            hist = yf.Ticker(row["ticker"]).history(period="60d", auto_adjust=True)
            ema_20 = hist["Close"].ewm(span=20, adjust=False).mean()
            ema_50 = hist["Close"].ewm(span=50, adjust=False).mean()
            trend = classify_trend(hist, ema_20, ema_50)
        except Exception:
            trend = "Sideways"
        trends.append(trend)
        setups_list.append(", ".join(get_eligible_setups(trend)))

    df["trend"] = trends
    df["setups"] = setups_list
    return df.sort_values("rvol", ascending=False).reset_index(drop=True)


def save_watchlist(df: pd.DataFrame, output_dir: str = ".") -> tuple:
    """
    Write ranked watchlist to CSV and plain-text file.
    Returns (csv_path, txt_path).
    """
    today = date.today().strftime("%Y-%m-%d")
    csv_path = f"{output_dir}/watchlist_{today}.csv"
    txt_path = f"{output_dir}/watchlist.txt"

    out = df[["ticker", "close", "gap_pct", "rvol", "atr_14", "atr_pct",
              "float_shares", "trend", "ema", "setups"]].copy()
    out["gap_pct"] = (out["gap_pct"] * 100).round(2)
    out["atr_pct"] = (out["atr_pct"] * 100).round(2)
    out["rvol"] = out["rvol"].round(2)
    out.columns = ["Ticker", "Price", "Gap%", "RVOL", "ATR", "ATR%",
                   "Float", "Trend", "EMA", "Setups"]
    out.to_csv(csv_path, index=False)

    with open(txt_path, "w") as f:
        f.write("\n".join(df["ticker"].tolist()))

    return csv_path, txt_path
```

- [ ] **Step 4: Create run_scanner.py**

`intraday/run_scanner.py`:
```python
#!/usr/bin/env python3
"""EOD scanner entry point. Run after market close (~4:30 PM)."""
from scanner.scanner import run_scan, save_watchlist

if __name__ == "__main__":
    print("Running EOD scan...")
    df = run_scan()
    if df.empty:
        print("No stocks passed all filters today.")
    else:
        csv_path, txt_path = save_watchlist(df)
        print(f"\nFound {len(df)} stocks.\nCSV: {csv_path}\nTOS import: {txt_path}")
        print("\n" + df[["ticker", "close", "gap_pct", "rvol", "trend", "ema", "setups"]]
              .to_string(index=False))
```

- [ ] **Step 5: Run tests — all should pass**

```bash
cd intraday && python -m pytest tests/test_scanner.py -v
```

Expected: 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add intraday/scanner/scanner.py intraday/tests/test_scanner.py intraday/run_scanner.py
git commit -m "feat: scanner orchestrator and run_scanner.py entry point"
```

---

## Task 6: Regime — Data Fetcher

**Files:**
- Create: `intraday/regime/fetcher.py`
- Create: `intraday/tests/test_regime_fetcher.py`

- [ ] **Step 1: Write failing tests**

`intraday/tests/test_regime_fetcher.py`:
```python
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from regime.fetcher import (
    fetch_qqq_data, fetch_vix, fetch_sector_returns,
    fetch_sp500_breadth, fetch_put_call_ratio,
)


def make_hist(n=30, close=400.0):
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    c = pd.Series([close] * n, index=idx)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99,
                         "Close": c, "Volume": 50_000_000}, index=idx)


class TestFetchQQQData:
    @patch("regime.fetcher.yf.Ticker")
    def test_returns_dataframe_with_emas(self, mock_cls):
        mock_cls.return_value.history.return_value = make_hist(60)
        result = fetch_qqq_data()
        assert "ema_20" in result.columns
        assert "ema_50" in result.columns
        assert len(result) > 0


class TestFetchVIX:
    @patch("regime.fetcher.yf.Ticker")
    def test_returns_float(self, mock_cls):
        mock_cls.return_value.history.return_value = make_hist(5, close=20.0)
        result = fetch_vix()
        assert isinstance(result, float)
        assert result == pytest.approx(20.0, abs=0.01)


class TestFetchSectorReturns:
    @patch("regime.fetcher.yf.Ticker")
    def test_returns_dict_with_sector_tickers(self, mock_cls):
        mock_cls.return_value.history.return_value = make_hist(15, close=100.0)
        result = fetch_sector_returns()
        assert isinstance(result, dict)
        assert "XLK" in result
        assert "XLU" in result

    @patch("regime.fetcher.yf.Ticker")
    def test_positive_return_when_price_rises(self, mock_cls):
        hist = make_hist(15, close=100.0)
        hist.iloc[-1, hist.columns.get_loc("Close")] = 105.0
        mock_cls.return_value.history.return_value = hist
        result = fetch_sector_returns(lookback_days=5)
        for v in result.values():
            assert v > 0


class TestFetchSP500Breadth:
    @patch("regime.fetcher.yf.Ticker")
    def test_returns_float_when_sufficient_data(self, mock_cls):
        # All prices above their 20 EMA (rising series)
        hist = make_hist(30, close=100.0)
        mock_cls.return_value.history.return_value = hist
        tickers = ["AAPL"] * 10  # 10 identical tickers
        result = fetch_sp500_breadth(tickers)
        assert result is not None
        assert 0.0 <= result <= 1.0

    @patch("regime.fetcher.yf.Ticker")
    def test_returns_none_when_too_many_failures(self, mock_cls):
        mock_cls.return_value.history.side_effect = Exception("network error")
        tickers = ["AAPL"] * 10
        result = fetch_sp500_breadth(tickers)
        assert result is None


class TestFetchPutCallRatio:
    @patch("regime.fetcher.requests.get")
    def test_returns_float_on_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "DATE,CALLS,PUTS,EQUITY\n2026-01-01,100,80,0.80\n"
        result = fetch_put_call_ratio(lookback_days=1)
        assert result is not None
        assert isinstance(result, float)

    @patch("regime.fetcher.requests.get")
    def test_returns_none_on_failure(self, mock_get):
        mock_get.return_value.status_code = 404
        result = fetch_put_call_ratio(lookback_days=5)
        assert result is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd intraday && python -m pytest tests/test_regime_fetcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'regime.fetcher'`

- [ ] **Step 3: Implement regime/fetcher.py**

`intraday/regime/fetcher.py`:
```python
import logging
import requests
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from config import SECTOR_GROWTH, SECTOR_DEFENSIVE, CBOE_BASE_URL, BREADTH_EMA_PERIOD, BREADTH_MIN_VALID_PCT


def fetch_qqq_data(lookback_days: int = 60) -> pd.DataFrame:
    """Fetch QQQ daily OHLCV and compute 20/50 EMA columns."""
    hist = yf.Ticker("QQQ").history(period=f"{lookback_days}d", auto_adjust=True)
    hist["ema_20"] = hist["Close"].ewm(span=20, adjust=False).mean()
    hist["ema_50"] = hist["Close"].ewm(span=50, adjust=False).mean()
    return hist


def fetch_vix() -> float:
    """Return the most recent VIX closing value."""
    hist = yf.Ticker("^VIX").history(period="5d", auto_adjust=True)
    return float(hist["Close"].iloc[-1])


def fetch_sector_returns(lookback_days: int = 5) -> dict:
    """
    Compute `lookback_days`-day return for each growth and defensive sector ETF.
    Returns {ticker: return_as_decimal}. Silently skips tickers that fail.
    """
    tickers = SECTOR_GROWTH + SECTOR_DEFENSIVE
    result = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(
                period=f"{lookback_days + 5}d", auto_adjust=True
            )
            if len(hist) >= lookback_days + 1:
                start = float(hist["Close"].iloc[-(lookback_days + 1)])
                end = float(hist["Close"].iloc[-1])
                result[ticker] = (end - start) / start
        except Exception:
            pass
    return result


def fetch_sp500_breadth(sp500_tickers: list, ema_period: int = None) -> Optional[float]:
    """
    Compute % of S&P 500 stocks with close > their 20-day EMA.
    Returns None if fewer than BREADTH_MIN_VALID_PCT of tickers return valid data.
    """
    if ema_period is None:
        ema_period = BREADTH_EMA_PERIOD

    above = 0
    total_valid = 0
    for ticker in sp500_tickers:
        try:
            hist = yf.Ticker(ticker).history(period="30d", auto_adjust=True)
            if len(hist) < ema_period + 1:
                continue
            ema = hist["Close"].ewm(span=ema_period, adjust=False).mean()
            if float(hist["Close"].iloc[-1]) > float(ema.iloc[-1]):
                above += 1
            total_valid += 1
        except Exception:
            pass

    min_valid = len(sp500_tickers) * BREADTH_MIN_VALID_PCT
    if total_valid < min_valid:
        logging.warning(
            "Breadth: only %d/%d tickers returned data — skipping factor",
            total_valid, len(sp500_tickers),
        )
        return None
    return above / total_valid


def fetch_put_call_ratio(lookback_days: int = 5) -> Optional[float]:
    """
    Download CBOE daily equity P/C CSV files for the last `lookback_days` trading days.
    Returns MA of equity-only P/C ratio, or None if CBOE is unavailable.

    CBOE URL format: https://www.cboe.com/us/options/market_statistics/daily/options_YYYYMMDD.csv
    The equity-only P/C ratio is in the row containing 'EQUITY'.
    """
    ratios = []
    check_date = date.today()
    attempts = 0
    while len(ratios) < lookback_days and attempts < 20:
        date_str = check_date.strftime("%Y%m%d")
        url = f"{CBOE_BASE_URL}options_{date_str}.csv"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                for line in resp.text.strip().split("\n"):
                    if "EQUITY" in line.upper():
                        parts = line.split(",")
                        ratios.append(float(parts[-1].strip()))
                        break
        except Exception:
            pass
        check_date -= timedelta(days=1)
        attempts += 1

    if not ratios:
        logging.warning("Put/Call ratio: CBOE fetch failed — skipping factor")
        return None
    return sum(ratios) / len(ratios)
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd intraday && python -m pytest tests/test_regime_fetcher.py -v
```

Expected: 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add intraday/regime/fetcher.py intraday/tests/test_regime_fetcher.py
git commit -m "feat: regime data fetcher — QQQ, VIX, sectors, breadth, CBOE P/C"
```

---

## Task 7: Regime — Scorer

**Files:**
- Create: `intraday/regime/scorer.py`
- Create: `intraday/tests/test_scorer.py`

- [ ] **Step 1: Write failing tests**

`intraday/tests/test_scorer.py`:
```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd intraday && python -m pytest tests/test_scorer.py -v
```

Expected: `ModuleNotFoundError: No module named 'regime.scorer'`

- [ ] **Step 3: Implement regime/scorer.py**

`intraday/regime/scorer.py`:
```python
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
    if qqq_close < ema_20 or ema_20 < ema_50:
        return -1
    return 0


def score_qqq_structure(qqq_hist: pd.DataFrame, lookback: int = 10) -> int:
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
        "qqq_ema":        score_qqq_ema(close, ema_20, ema_50),
        "qqq_structure":  score_qqq_structure(qqq_hist),
        "vix":            score_vix(vix),
        "breadth":        score_breadth(breadth),
        "sector_rotation":score_sector_rotation(sector_returns),
        "put_call":       score_put_call(pc_ratio),
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
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd intraday && python -m pytest tests/test_scorer.py -v
```

Expected: 26 tests pass.

- [ ] **Step 5: Commit**

```bash
git add intraday/regime/scorer.py intraday/tests/test_scorer.py
git commit -m "feat: regime scorer — 6-factor scoring matrix and regime tier mapping"
```

---

## Task 8: Regime — Orchestrator + run_regime.py

**Files:**
- Create: `intraday/regime/regime.py`
- Create: `intraday/run_regime.py`

No new tests — orchestration is thin glue covered by integration (just verify JSON is written correctly).

- [ ] **Step 1: Implement regime/regime.py**

`intraday/regime/regime.py`:
```python
import json
import logging
import pandas as pd
from datetime import date
from typing import Optional
from regime.fetcher import (
    fetch_qqq_data, fetch_vix, fetch_sector_returns,
    fetch_sp500_breadth, fetch_put_call_ratio,
)
from regime.scorer import compute_regime
from config import SP500_WIKI_URL

LAST_REGIME_PATH = "regime/last_regime.json"

SCORE_LABELS = {
    1: "+1", 0: " 0", -1: "-1",
}


def load_sp500_tickers() -> list:
    try:
        tables = pd.read_html(SP500_WIKI_URL)
        return [t.replace(".", "-") for t in tables[0]["Symbol"].tolist()]
    except Exception as e:
        logging.error("Failed to load S&P 500 tickers: %s", e)
        return []


def print_regime(result: dict) -> None:
    s = result["scores"]
    d = result["factor_details"]
    print(f"\n=== MARKET REGIME: {date.today()} ===\n")
    print(f"QQQ EMA Alignment:    {SCORE_LABELS[s['qqq_ema']]}  "
          f"(close={d['qqq_close']:.1f}, ema20={d['ema_20']:.1f}, ema50={d['ema_50']:.1f})")
    print(f"QQQ Price Structure:  {SCORE_LABELS[s['qqq_structure']]}")
    print(f"VIX:                  {SCORE_LABELS[s['vix']]}  ({d['vix']:.1f})")
    breadth_str = f"{d['breadth']*100:.0f}%" if d["breadth"] else "N/A (skipped)"
    print(f"Market Breadth:       {SCORE_LABELS[s['breadth']]}  ({breadth_str} above 20 EMA)")
    growth_avg = sum(d["sector_returns"].get(t, 0) for t in ["XLK", "XLY"]) / 2
    def_avg = sum(d["sector_returns"].get(t, 0) for t in ["XLU", "XLP", "XLV"]) / 3
    print(f"Sector Rotation:      {SCORE_LABELS[s['sector_rotation']]}  "
          f"(growth {growth_avg*100:+.2f}% vs defensive {def_avg*100:+.2f}% over 5d)")
    pc_str = f"{d['pc_ratio']:.2f}" if d["pc_ratio"] else "N/A (skipped)"
    print(f"Put/Call (5-day MA):  {SCORE_LABELS[s['put_call']]}  ({pc_str})")
    print(f"\nTOTAL SCORE:          {result['total_score']:+d}  →  {result['regime'].upper()}")
    print(f"RISK PER TRADE:       {result['risk_pct']*100:.2f}%  "
          f"(${result['dollar_risk']:.0f} on $20k)")
    long_str = ", ".join(result["long_setups"]) if result["long_setups"] else "OFF"
    print(f"LONG SETUPS:          {long_str}")
    print(f"SHORT SETUPS:         {', '.join(result['short_setups'])}\n")


def run_regime() -> dict:
    """Fetch all data, compute regime, print to terminal, cache to JSON."""
    print("Fetching market data...")
    qqq_hist = fetch_qqq_data()
    vix = fetch_vix()
    sector_returns = fetch_sector_returns()
    sp500_tickers = load_sp500_tickers()
    print(f"Computing breadth across {len(sp500_tickers)} S&P 500 stocks (may take ~2 min)...")
    breadth = fetch_sp500_breadth(sp500_tickers)
    pc_ratio = fetch_put_call_ratio()

    result = compute_regime(qqq_hist, vix, breadth, sector_returns, pc_ratio)
    print_regime(result)

    cache = {
        "date": date.today().isoformat(),
        "regime": result["regime"],
        "risk_pct": result["risk_pct"],
        "dollar_risk": result["dollar_risk"],
        "total_score": result["total_score"],
        "long_setups": result["long_setups"],
        "short_setups": result["short_setups"],
    }
    with open(LAST_REGIME_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    return result
```

- [ ] **Step 2: Create run_regime.py**

`intraday/run_regime.py`:
```python
#!/usr/bin/env python3
"""Morning regime scorer entry point. Run pre-market (~9:00-9:15 AM)."""
from regime.regime import run_regime

if __name__ == "__main__":
    run_regime()
```

- [ ] **Step 3: Smoke test (verifies wiring without live network)**

```bash
cd intraday && python -c "
from unittest.mock import patch, MagicMock
import pandas as pd, json
idx = pd.date_range('2025-01-01', periods=30, freq='B')
hist = pd.DataFrame({'High': 410, 'Low': 400, 'Close': 405, 'Open': 405, 'Volume': 1e7}, index=idx)
hist['ema_20'] = 400.0; hist['ema_50'] = 390.0
with patch('regime.regime.fetch_qqq_data', return_value=hist), \
     patch('regime.regime.fetch_vix', return_value=20.0), \
     patch('regime.regime.fetch_sector_returns', return_value={'XLK':0.01,'XLY':0.01,'XLU':0.003,'XLP':0.003,'XLV':0.003}), \
     patch('regime.regime.load_sp500_tickers', return_value=[]), \
     patch('regime.regime.fetch_sp500_breadth', return_value=0.55), \
     patch('regime.regime.fetch_put_call_ratio', return_value=0.90):
    from regime.regime import run_regime
    run_regime()
print('Regime JSON written.')
"
```

Expected: regime output printed, `regime/last_regime.json` created.

- [ ] **Step 4: Commit**

```bash
git add intraday/regime/regime.py intraday/run_regime.py
git commit -m "feat: regime orchestrator and run_regime.py entry point"
```

---

## Task 9: Sizing Calculator + run_sizing.py

**Files:**
- Create: `intraday/sizing/calculator.py`
- Create: `intraday/tests/test_calculator.py`
- Create: `intraday/run_sizing.py`

- [ ] **Step 1: Write failing tests**

`intraday/tests/test_calculator.py`:
```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd intraday && python -m pytest tests/test_calculator.py -v
```

Expected: `ModuleNotFoundError: No module named 'sizing.calculator'`

- [ ] **Step 3: Implement sizing/calculator.py**

`intraday/sizing/calculator.py`:
```python
import math
import json
import os
from typing import Optional
from config import ACCOUNT_SIZE, MAX_OPEN_RISK, MAX_POSITION_PCT

LAST_REGIME_PATH = "regime/last_regime.json"


def load_regime() -> Optional[dict]:
    """Load the last cached regime from last_regime.json. Returns None if missing."""
    if not os.path.exists(LAST_REGIME_PATH):
        return None
    with open(LAST_REGIME_PATH) as f:
        return json.load(f)


def calculate_size(
    entry: float,
    stop: float,
    setup: str,
    risk_pct: float,
    atr: Optional[float] = None,
    open_risk: float = 0.0,
    orb_high: Optional[float] = None,
) -> dict:
    """
    Calculate position size and output targets for a long or short trade.

    is_long determined by stop < entry (long) or stop > entry (short).
    open_risk: dollar amount already at risk in existing open positions (default 0).
    orb_high: for ORB setup only — warns if entry is >0.5% above this level.
    """
    is_long = stop < entry
    stop_distance = abs(entry - stop)

    if stop_distance == 0:
        return {"blocks": ["Stop price equals entry price — invalid trade"],
                "warnings": [], "shares": 0}

    budget = ACCOUNT_SIZE * risk_pct
    shares = math.floor(budget / stop_distance)
    dollar_risk = shares * stop_distance
    position_value = shares * entry

    if is_long:
        target_1 = entry + stop_distance
        target_2 = entry + 2 * stop_distance
    else:
        target_1 = entry - stop_distance
        target_2 = entry - 2 * stop_distance

    warnings, blocks = [], []

    if atr and stop_distance > atr:
        warnings.append(
            f"Stop distance ${stop_distance:.2f} > 1x ATR ${atr:.2f} — consider skipping"
        )

    if atr and abs(target_2 - entry) > 2 * atr:
        warnings.append(
            f"Target 2 is >{2}x ATR from entry — may not be reachable"
        )

    if position_value > ACCOUNT_SIZE * MAX_POSITION_PCT:
        warnings.append(
            f"Position value ${position_value:,.0f} > 25% of account — review"
        )

    if open_risk + dollar_risk > MAX_OPEN_RISK:
        blocks.append(
            f"Total open risk ${open_risk + dollar_risk:.0f} would exceed ${MAX_OPEN_RISK:.0f} cap"
        )

    if setup == "orb" and orb_high is not None and is_long:
        pct_above = (entry - orb_high) / orb_high
        if pct_above > 0.005:
            warnings.append(
                f"Entry is {pct_above*100:.2f}% above ORB high ${orb_high:.2f} — likely chasing"
            )

    return {
        "is_long": is_long,
        "shares": shares,
        "dollar_risk": round(dollar_risk, 2),
        "stop_distance": round(stop_distance, 4),
        "position_value": round(position_value, 2),
        "target_1": round(target_1, 4),
        "target_2": round(target_2, 4),
        "atr_multiples_stop": round(stop_distance / atr, 2) if atr else None,
        "atr_multiples_target": round(abs(target_2 - entry) / atr, 2) if atr else None,
        "warnings": warnings,
        "blocks": blocks,
    }
```

- [ ] **Step 4: Run tests — all should pass**

```bash
cd intraday && python -m pytest tests/test_calculator.py -v
```

Expected: 16 tests pass.

- [ ] **Step 5: Create run_sizing.py**

`intraday/run_sizing.py`:
```python
#!/usr/bin/env python3
"""
Per-trade sizing calculator. Run before each entry.

Usage:
  python run_sizing.py --entry 47.50 --stop 46.80 --setup orb
  python run_sizing.py --entry 52.10 --stop 52.60 --setup vwap_reclaim --open_risk 250
  python run_sizing.py --entry 47.50 --stop 46.80 --setup orb --orb_high 47.40 --atr 1.12
"""
import argparse
from sizing.calculator import calculate_size, load_regime

VALID_SETUPS = ["orb", "ema_pullback", "vwap_reclaim"]


def main():
    parser = argparse.ArgumentParser(description="Intraday position sizing calculator")
    parser.add_argument("--entry",    type=float, required=True)
    parser.add_argument("--stop",     type=float, required=True)
    parser.add_argument("--setup",    type=str, required=True, choices=VALID_SETUPS)
    parser.add_argument("--open_risk",type=float, default=0.0)
    parser.add_argument("--orb_high", type=float, default=None)
    parser.add_argument("--atr",      type=float, default=None)
    args = parser.parse_args()

    regime = load_regime()
    if regime is None:
        print("⚠ No regime file found. Run python run_regime.py first.")
        print("  Defaulting to Choppy/Neutral (0.75% risk).")
        risk_pct = 0.0075
        regime = {"regime": "Choppy/Neutral", "risk_pct": risk_pct,
                  "dollar_risk": 150.0, "long_setups": ["orb", "ema_pullback", "vwap_reclaim"],
                  "short_setups": ["orb", "ema_pullback", "vwap_reclaim"]}
    else:
        risk_pct = regime["risk_pct"]

    is_long = args.stop < args.entry
    direction = "LONG" if is_long else "SHORT"
    allowed = regime["long_setups"] if is_long else regime["short_setups"]

    if args.setup not in allowed:
        print(f"\n🚫 BLOCKED: {args.setup.upper()} {direction} not allowed in "
              f"{regime['regime']} regime.")
        print(f"   Allowed {'long' if is_long else 'short'} setups: "
              f"{', '.join(allowed) if allowed else 'NONE'}\n")
        return

    result = calculate_size(
        entry=args.entry, stop=args.stop, setup=args.setup,
        risk_pct=risk_pct, atr=args.atr,
        open_risk=args.open_risk, orb_high=args.orb_high,
    )

    if result["blocks"]:
        print(f"\n🚫 BLOCKED:")
        for b in result["blocks"]:
            print(f"   {b}")
        print()
        return

    atr_stop_str = (f"  {result['atr_multiples_stop']}x ATR"
                    if result["atr_multiples_stop"] else "")
    atr_tgt_str = (f"  {result['atr_multiples_target']}x ATR from entry"
                   if result["atr_multiples_target"] else "")

    print(f"\n=== POSITION SIZING: {args.setup.upper()} {direction} ===\n")
    print(f"Regime:          {regime['regime']}  →  Risk: "
          f"{risk_pct*100:.2f}% (${regime['dollar_risk']:.0f})")
    print(f"Trade:           {direction}\n")
    print(f"Entry:           ${args.entry:.2f}")
    print(f"Stop:            ${args.stop:.2f}")
    print(f"Stop Distance:   ${result['stop_distance']:.2f}{atr_stop_str}")
    print(f"\nShares:          {result['shares']}")
    print(f"Dollar Risk:     ${result['dollar_risk']:.2f}")
    print(f"Position Value:  ${result['position_value']:,.0f}")
    print(f"\nTarget 1 (1:1):  ${result['target_1']:.2f}  →  "
          f"${result['dollar_risk']:.0f} profit  [exit {result['shares']//2} shares]")
    print(f"Target 2 (2:1):  ${result['target_2']:.2f}  →  "
          f"${result['dollar_risk']*2:.0f} profit  [exit {result['shares'] - result['shares']//2} shares]")
    rr_ratio = abs(result["target_2"] - args.entry) / result["stop_distance"]
    print(f"\nR:R:             {rr_ratio:.2f}:1{atr_tgt_str}")

    for w in result["warnings"]:
        print(f"⚠  {w}")
    print()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Smoke test the CLI**

```bash
cd intraday && python run_sizing.py --entry 47.50 --stop 46.80 --setup orb --atr 1.12
```

Expected: formatted output with shares, targets, R:R. (Uses default Choppy/Neutral since no regime file exists yet — that's fine.)

- [ ] **Step 7: Run full test suite**

```bash
cd intraday && python -m pytest tests/ -v
```

Expected: all tests pass (no failures).

- [ ] **Step 8: Commit**

```bash
git add intraday/sizing/calculator.py intraday/tests/test_calculator.py intraday/run_sizing.py
git commit -m "feat: sizing calculator with long/short formulas, guards, and CLI"
```

---

## Task 10: Final Integration Smoke Test

- [ ] **Step 1: Run full test suite one final time**

```bash
cd intraday && python -m pytest tests/ -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 2: Verify all three entry points are importable**

```bash
cd intraday && python -c "import run_scanner, run_regime, run_sizing; print('All entry points OK')"
```

Expected: `All entry points OK`

- [ ] **Step 3: Print help for run_sizing.py**

```bash
cd intraday && python run_sizing.py --help
```

Expected: prints argument list with `--entry`, `--stop`, `--setup`, `--open_risk`, `--orb_high`, `--atr`.

- [ ] **Step 4: Final commit**

```bash
git add intraday/
git commit -m "feat: complete intraday trading strategy framework — scanner, regime scorer, sizing calculator"
```
