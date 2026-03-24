# Intraday Trading Strategy Framework — Design Spec

**Date:** 2026-03-24
**Approach:** Systematic + discretionary hybrid
**Account size:** $20,000
**Execution platform:** ThinkorSwim
**Data stack:** Python + yfinance

---

## 1. Overview

A framework for taking high-probability intraday setups with clear, rule-based entry/exit logic, regime-adjusted position sizing, and a nightly EOD scanner that builds a watchlist for the following day. The trader is available at market open and throughout the day. The goal is selectivity over frequency — fewer, higher-conviction trades.

**Three setups:**
1. Opening Range Breakout (ORB) Long
2. First Pullback to EMA (Long and Short)
3. VWAP Reclaim (Long and Short)

**Three Python modules:**
1. `run_scanner.py` — EOD watchlist builder
2. `run_regime.py` — morning market regime scorer
3. `run_sizing.py` — per-trade position sizing calculator

---

## 2. Stock Universe & Scan Filters

**Universe:** S&P 500 + Russell 1000 components (~1,500 stocks), maintained as a static list in `config.py`, updated quarterly.

**Filter pipeline (applied in order):**

| Step | Filter | Threshold |
|------|--------|-----------|
| 1 | Price | $10–$500 |
| 2 | Avg daily volume (20-day) | >500,000 shares |
| 3 | Float | 10M–500M shares |
| 4 | ATR(14) | ≥$0.75 AND ≥1.5% of price |
| 5 | Daily gap | >2% from prior close (up or down) |
| 6 | RVOL | Today's volume ÷ 20-day avg >1.5x |
| 7 | Bid-ask spread proxy | <0.1% of price (estimated from OHLC) |

**RVOL definition:** 20-day lookback. EOD scanner uses simple daily volume vs. 20-day average (full day volume available). Intraday use in TOS uses time-of-day adjusted RVOL (TOS native, 20-period lookback).

---

## 3. Trend Classification

Calculated on the daily chart, appended to each stock in the watchlist output.

| Trend | Criteria |
|-------|----------|
| **Uptrend** | Price above 20 EMA and 50 EMA, 20 EMA above 50 EMA, at least 2 of last 3 swing points are HH/HL |
| **Downtrend** | Price below 20 EMA and 50 EMA, 20 EMA below 50 EMA, at least 2 of last 3 swing points are LH/LL |
| **Sideways** | Mixed EMA alignment or price oscillating through EMAs without directional structure |

**Trend-to-setup mapping:**

| Setup | Preferred Trend |
|-------|----------------|
| ORB Long | Uptrend |
| First Pullback Long | Uptrend |
| First Pullback Short | Downtrend |
| VWAP Reclaim Long | Uptrend or Sideways |
| VWAP Reclaim Short | Downtrend or Sideways |

---

## 4. Market Regime Scorer

**When:** Each morning pre-market (~9:00–9:15 AM EST).

**Scoring model:** 6 factors, each scored −1 (bearish), 0 (neutral), +1 (bullish). Total range: −6 to +6.

| Factor | −1 (Bearish) | 0 (Neutral) | +1 (Bullish) | Data Source |
|--------|-------------|-------------|--------------|-------------|
| QQQ trend (EMA alignment) | Below 20 EMA OR 20 below 50 | Between 20 and 50, mixed | Above both, 20 above 50 | yfinance |
| QQQ price structure | LH/LL (last 10 days) | No clear structure | HH/HL (last 10 days) | yfinance |
| VIX level | >25 | 18–25 | <18 | yfinance `^VIX` |
| Market breadth | <40% of S&P 500 above 20 EMA | 40–60% | >60% | yfinance (calculated) |
| Sector rotation (5-day) | Defensives (XLU, XLP, XLV) outperforming growth (XLK, XLY) | Mixed | Growth outperforming defensives | yfinance |
| Put/Call ratio (5-day MA) | >1.1 | 0.85–1.1 | <0.85 | CBOE scrape |

**Regime tier mapping:**

| Score | Regime | Risk % | Dollar Risk ($20k) |
|-------|--------|--------|--------------------|
| +4 to +6 | Strong Bull | 1.5% | $300 |
| +1 to +3 | Bull | 1.25% | $250 |
| −1 to 0 | Choppy/Neutral | 0.75% | $150 |
| −2 to −3 | Bear | 0.5% | $100 |
| −4 to −6 | Strong Bear | 0.5% | $100 |

**Setup gates by regime:**

| Regime | Long Setups | Short Setups |
|--------|-------------|--------------|
| Strong Bull | All three | VWAP reclaim only |
| Bull | All three | VWAP reclaim only |
| Choppy/Neutral | All three (max confirmation required) | All three |
| Bear | Strong catalyst only | All three |
| Strong Bear | Off | All three |

---

## 5. Setup Rules

### 5.1 ORB Long

**Conditions (Market & Price Action)**
- Regime: Bull or Strong Bull
- Stock has gapped up >2% from prior close with a catalyst
- RVOL >1.5x (time-of-day adjusted) at time of breakout
- ATR(14) ≥ $0.75
- ORB range (high − low) between 0.5x and 1.5x of ATR — too tight = weak conviction, too wide = stop placement unreasonable
- Time window: 9:45–10:30 AM EST only

**Entry Trigger**
- 5-min candle closes above the ORB high
- Entry price within 0.5% of the ORB high — if missed, skip entirely
- Breakout candle volume >1.5x the 20-period average

**Stop & Target**
- Stop: below the ORB high (failed breakout level)
- If ORB range is wide, stop can be at ORB midpoint — only if stop distance ≤ 1x ATR
- If stop distance >1x ATR: skip the trade
- Target: minimum 2:1 R:R based on stop distance
- ATR sanity check: target must be reachable within 1–2x ATR from entry
- Scale: 50% off at 1:1, stop to breakeven, 50% runs to 2:1+

**Invalidation**
- Entry price >0.5% above ORB high (chasing — do not enter)
- ORB range >1.5x ATR
- Breakout candle is low volume or has a long upper wick
- SPY/QQQ selling off at moment of breakout
- Price closes back below ORB high within 2 candles of entry

---

### 5.2 First Pullback to EMA

**Conditions (Market & Price Action)**
- Long: Regime Neutral or better. Short: Regime Bear or worse.
- Stock has made a directional move of at least 1x ATR off the open or a catalyst before the pullback
- Price is above (long) or below (short) the relevant EMA — trend is intact
- This is the first pullback to the EMA (count touches — 2nd or 3rd touch has diminished edge)
- Pullback depth: between 0.3x and 0.8x ATR
- EMA selection: 9 EMA for high-momentum/gapped stocks; 21 EMA for steadier trends
- RVOL >1.2x at time of entry
- Time: primary (9:45–11:30 AM) or secondary (2:00–3:30 PM) session

**Entry Trigger**
- 5-min candle touches the EMA and closes back above it (long) or below it (short)
- Candle shows structure: hammer, bullish engulfing, or close in upper 50% of range (long); inverse for short
- Body interaction with EMA required — wick tags alone are not valid entries

**Stop & Target**
- Stop: below the pullback candle low (long) or above it (short) — typically 0.25–0.5x ATR from the EMA
- If stop distance >0.75x ATR: skip (pullback is too deep)
- Target: 2:1 R:R minimum; ATR-based target at 1.5–2x ATR from entry
- Scale: 50% at 1:1, stop to breakeven, trail remainder with 9 EMA on 5-min

**Invalidation**
- Pullback depth exceeds 1x ATR (likely a trend reversal, not a pullback)
- This is the 2nd or 3rd EMA touch
- Entry candle closes back through the EMA on the next bar
- RVOL dropping below 1x (participation fading)
- Broader market moving sharply against your direction during the trade

---

### 5.3 VWAP Reclaim (Long & Short)

**Conditions (Market & Price Action)**
- Long: Regime Neutral or better. Short: Any regime.
- Price has spent at least 3 consecutive 5-min candles below VWAP (long) or above VWAP (short) before the reclaim
- Distance from VWAP at time of reclaim: ≤ 1x ATR — stretched reclaims fail at a higher rate
- RVOL >1.5x on the reclaim candle (non-negotiable)
- Time: primary (9:45–11:30 AM) or secondary (2:00–3:30 PM) session. Strongest setups occur in the first 90 minutes or after 2 PM.

**Entry Trigger**
- 5-min candle closes above VWAP (long) or below VWAP (short)
- Reclaim candle volume >1.5x the 20-period average
- Long: reclaim candle closes in upper 50% of its range
- Short: breakdown candle closes in lower 50% of its range

**Stop & Target**
- Long stop: 0.25–0.5x ATR below VWAP
- Short stop: 0.25–0.5x ATR above VWAP
- If stop distance >0.75x ATR: reduce size by 50% or skip
- Target: 2:1 R:R minimum. Anchor to logical levels — prior high/low, round numbers, or +1x ATR from entry
- Scale: 50% at 1:1, stop to breakeven, trail remainder

**Invalidation**
- Price crosses back through VWAP within 2 candles of entry (false reclaim — exit immediately)
- Multiple failed VWAP reclaim attempts earlier in the session (VWAP acting as resistance)
- Low volume on the reclaim candle
- Broader market moving sharply against your direction

---

## 6. Position Sizing Calculator

**Formula:**
```
shares      = floor((account_size × risk_pct) / (entry_price − stop_price))
dollar_risk = shares × (entry_price − stop_price)
target_1    = entry_price + (entry_price − stop_price)        # 1:1
target_2    = entry_price + 2 × (entry_price − stop_price)   # 2:1
```

**Built-in guards:**

| Check | Rule | Output |
|-------|------|--------|
| Minimum R:R | Target 2 must be reachable (≤2x ATR from entry) | Warning if not |
| Stop too wide | Stop distance >1x ATR | Warning — skip or reduce |
| Position too large | Position value >25% of account | Flag for review |
| Setup not allowed | Setup blocked by current regime | Hard block with reason |
| Entry too far from trigger | >0.5% above ORB high | Warning — likely chasing |

---

## 7. Time-of-Day Rules

| Window | Rule |
|--------|------|
| 9:30–9:35 AM | Observation only — no entries |
| 9:35–9:45 AM | ORB forming — mark high/low, no entries |
| 9:45–11:30 AM | Primary session — all setups active |
| 11:30 AM–2:00 PM | No new entries — lunch lull |
| 2:00–3:30 PM | Secondary session — EMA pullback and VWAP reclaim only |
| 3:30–4:00 PM | No new entries |
| By 3:55 PM | Close all intraday positions |

**Special rules:**
- FOMC days: no entries until 30 minutes after Fed announcement
- Pre-earnings: never hold through an earnings report — close by 3:55 PM

---

## 8. Daily Risk Rules

| Rule | Value |
|------|-------|
| Max daily loss | 2% ($400) — hard stop, close all positions, no more entries |
| Max consecutive losers | 2 — mandatory 30-min break, reassess regime before re-engaging |
| Max simultaneous open risk | 3% ($600) — no more than 2 full-size positions open at once |
| Max trades per day | 5 total (3 in primary session, 2 in secondary) |
| Daily profit target | 4% ($800) — soft stop, become highly selective or stop |

---

## 9. Daily Workflow

**Night before (~4:30 PM)**
1. Run `python run_scanner.py` → `watchlist_YYYY-MM-DD.csv` + `watchlist.txt`
2. Review output — note trend, flagged setups per stock
3. Import `watchlist.txt` into TOS
4. Pre-mark key levels on TOS charts: prior day high/low, 9/21 EMA, VWAP anchor

**Pre-market (~9:00–9:15 AM)**
1. Run `python run_regime.py` → today's regime tier and risk %
2. Re-filter watchlist in TOS using live pre-market RVOL and gap data
3. Narrow to 3–5 highest conviction names

**Market open (9:30–9:45 AM)**
- Observation only — watch how names open, note VWAP side, let ORB range form

**Primary session (9:45–11:30 AM)**
- All setups active subject to regime gates
- Before each entry: run `python run_sizing.py` → confirm size, stop, targets
- Max 3 trades

**Midday (11:30 AM–2:00 PM)**
- No new entries
- Manage open positions

**Secondary session (2:00–3:30 PM)**
- EMA pullback and VWAP reclaim only
- Max 2 trades

**End of day (3:30–4:00 PM)**
- No new entries after 3:30 PM
- Close all positions by 3:55 PM
- Run scanner for next day

---

## 10. File Structure

```
intraday/
├── config.py                  # account size, universe list, filter thresholds
├── scanner/
│   ├── __init__.py
│   ├── fetcher.py             # pulls OHLCV, ATR, EMA, float via yfinance
│   ├── filters.py             # price, volume, ATR, gap, RVOL, spread filters
│   ├── trend.py               # trend classification (uptrend/downtrend/sideways)
│   └── scanner.py             # orchestrates scan, produces ranked output
├── regime/
│   ├── __init__.py
│   ├── fetcher.py             # pulls QQQ, VIX, SPY components, sector ETFs
│   ├── scorer.py              # scoring matrix, regime classification
│   └── regime.py             # orchestrates regime scoring, prints output
├── sizing/
│   ├── __init__.py
│   └── calculator.py          # sizing formula, guards, formatted output
├── run_scanner.py             # entry point: EOD scan
├── run_regime.py              # entry point: morning regime check
├── run_sizing.py              # entry point: per-trade sizing
└── requirements.txt
```

**Tech stack:** Python 3.10+, yfinance, pandas, numpy, requests (CBOE scrape), tabulate (formatted terminal output)
