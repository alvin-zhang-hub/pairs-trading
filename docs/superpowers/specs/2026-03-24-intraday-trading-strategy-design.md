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

**Universe:** S&P 500 + Russell 1000 components (~1,500 stocks), maintained as a static list in `config.py` (updated quarterly). The S&P 500 component list is sourced from Wikipedia's S&P 500 table via pandas `read_html`; Russell 1000 from iShares IWB holdings CSV (downloaded manually quarterly).

**Filter pipeline (applied in order to minimize API calls):**

| Step | Filter | Threshold | Notes |
|------|--------|-----------|-------|
| 1 | Price | $10–$500 | Use prior day close |
| 2 | Avg daily volume (20-day) | >500,000 shares | Sufficient as primary liquidity gate |
| 3 | Float | 10M–500M shares | Best-effort: sourced from `yfinance` `info['floatShares']`. If field is `None` or missing, skip float filter for that ticker (do not exclude). Log skipped tickers. |
| 4 | ATR(14) | ≥$0.75 AND ≥1.5% of price | Ensures enough intraday range |
| 5 | Daily gap | >2% from prior close (up or down) | `abs(open - prev_close) / prev_close > 0.02` |
| 6 | RVOL | Today's volume ÷ 20-day avg >1.5x | See note below |
| 7 | ~~Bid-ask spread proxy~~ | ~~<0.1% of price~~ | **Removed** — no reliable OHLC-based proxy without tick data. Avg daily volume >500k (Step 2) serves as the liquidity/spread gate. |

**Float data note:** `yfinance` returns float from Yahoo Finance's cached fundamentals, which can be stale or missing. The filter is applied when available and skipped (not excluded) when absent. For a more reliable source in future iterations, Finviz's screener API or a paid data provider can be substituted.

**RVOL note:** The EOD scanner uses simple daily volume vs. 20-day average — this reflects yesterday's activity and flags stocks with elevated participation. It does **not** predict tomorrow's RVOL. The real intraday RVOL gate is applied in ThinkorSwim at entry time using TOS's native time-of-day adjusted `RelativeVolume` study (20-period lookback). The EOD RVOL filter narrows the watchlist to names that were already in play; the TOS filter is the actual entry gate.

---

## 3. Trend Classification

Calculated on the daily chart using the last 20 candles, appended to each stock in the watchlist output.

**EMA alignment:**

| Trend | EMA Alignment | Price Structure |
|-------|--------------|----------------|
| **Uptrend** | Price above 20 EMA and 50 EMA; 20 EMA above 50 EMA | At least 2 of last 3 swing highs are higher than the prior swing high AND at least 2 of last 3 swing lows are higher than the prior swing low |
| **Downtrend** | Price below 20 EMA and 50 EMA; 20 EMA below 50 EMA | At least 2 of last 3 swing highs are lower than the prior swing high AND at least 2 of last 3 swing lows are lower than the prior swing low |
| **Sideways** | Any other combination | Mixed or unclear swing structure |

**Swing point algorithm:** A swing high is a daily candle whose high is strictly greater than the highs of the 2 candles immediately before it and the 2 candles immediately after it (3-bar fractal, 2-candle lookback on each side). A swing low is the inverse. This produces swing points on the daily chart without a smoothing parameter.

If the 20-candle window yields fewer than 3 swing highs or fewer than 3 swing lows, classify the stock as **Sideways** regardless of EMA alignment. A longer lookback is not used — insufficient swing structure within 20 days is itself a signal of sideways/choppy price action.

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

**When:** Each morning pre-market (~9:00–9:15 AM EST). Uses prior day's closing data — no live feed required.

**Scoring model:** 6 factors, each scored −1 (bearish), 0 (neutral), +1 (bullish). Total range: −6 to +6. When a factor's value falls exactly on a boundary (e.g., QQQ closes precisely on its 20 EMA, or VIX = 18.00), score that factor as 0 (neutral).

| Factor | −1 (Bearish) | 0 (Neutral) | +1 (Bullish) | Data Source |
|--------|-------------|-------------|--------------|-------------|
| QQQ EMA alignment | Price below 20 EMA, OR 20 EMA below 50 EMA | Price between 20 and 50 EMA, 20 and 50 EMA mixed | Price above both 20 and 50 EMA, 20 EMA above 50 EMA | yfinance |
| QQQ price structure | LH/LL on daily (last 10 trading days, 3-bar fractal) | No clear structure / mixed | HH/HL on daily (last 10 trading days, 3-bar fractal) | yfinance |
| VIX level | >25 | 18–25 | <18 | yfinance `^VIX` |
| Market breadth | <40% of S&P 500 above 20 EMA | 40–60% | >60% | yfinance (calculated — see note) |
| Sector rotation (5-day) | XLU+XLP+XLV avg return > XLK+XLY avg return | Difference <0.5% either direction | XLK+XLY avg return > XLU+XLP+XLV avg return by >0.5% | yfinance |
| Put/Call ratio (5-day MA) | >1.1 | 0.85–1.1 | <0.85 | CBOE daily CSV (see note) |

**Market breadth computation:**
- Pull daily close data for all S&P 500 components (static list from `config.py`)
- Calculate each stock's 20-day EMA from prior close data
- Breadth = count of stocks where `close > 20_ema` / total stocks with valid data
- If fewer than 80% of tickers return valid data (yfinance failures), skip this factor (score = 0) and log a warning
- Uses daily close data only — no pre-market data required

**Put/Call ratio source:**
- CBOE publishes daily P/C data as a downloadable CSV at: `https://www.cboe.com/us/options/market_statistics/daily/`
- The file is named `options_YYYYMMDD.csv` and contains the equity-only P/C ratio
- `regime/fetcher.py` downloads the last 5 available trading days of this file and computes the 5-day MA of the equity-only P/C ratio
- If the CBOE URL is unavailable (site change or network failure), skip this factor (score = 0) and log a warning

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
| Choppy/Neutral | All three — all confirmation criteria must be fully met (no "close enough" entries; see each setup's conditions) | All three |
| Bear | Strong catalyst only (gap >4%, RVOL >2x) | All three |
| Strong Bear | Off | All three |

**Terminal output example:**
```
=== MARKET REGIME: 2026-03-24 ===

QQQ EMA Alignment:    +1  (above 20 + 50 EMA, 20 > 50)
QQQ Price Structure:  +1  (HH/HL confirmed, last 10 days)
VIX:                   0  (21.4 — neutral band 18–25)
Market Breadth:       +1  (63% of S&P 500 above 20 EMA)
Sector Rotation:      +1  (XLK+XLY +1.2% vs XLU+XLP+XLV -0.4% over 5d)
Put/Call (5-day MA):   0  (0.92 — neutral band 0.85–1.1)

TOTAL SCORE:          +4  →  STRONG BULL
RISK PER TRADE:       1.5%  ($300 on $20k)
LONG SETUPS:          All three active
SHORT SETUPS:         VWAP reclaim only
```

---

## 5. Setup Rules

### 5.1 ORB Long

**Conditions (Market & Price Action)**
- Regime: Bull or Strong Bull
- Stock has gapped up >2% from prior close with a catalyst
- RVOL >1.5x (time-of-day adjusted, TOS native) at time of breakout
- ATR(14) ≥ $0.75
- ORB range (high − low) between 0.5x and 1.5x of ATR — too tight = weak conviction, too wide = stop placement unreasonable
- Time window: **9:45–10:30 AM EST only** (ORB setup is invalid outside this window)

**Entry Trigger**
- 5-min candle closes above the ORB high
- Entry price within 0.5% of the ORB high — if missed, skip entirely (do not chase)
- Breakout candle volume >1.5x the 20-period average

**Stop & Target**

Stop placement uses a two-step decision:
1. **Default stop:** just below the ORB high (the failed breakout level). This is the tightest valid stop.
2. **Wider stop (ORB midpoint):** only used if the ORB range is between 1x and 1.5x ATR AND the stop distance from entry to ORB midpoint is ≤ 1x ATR. If both conditions are met, the trader may use the midpoint stop at their discretion.
3. **Skip the trade** if stop distance to either level exceeds 1x ATR.

Priority: default stop first. Only consider the midpoint stop if the default stop distance is impractically tight (< $0.20) relative to ATR.

- Target: minimum 2:1 R:R based on the chosen stop distance
- ATR sanity check: target (2:1) must be ≤ 2x ATR from entry — if not, the setup does not offer a reachable target and should be skipped
- Scale: 50% off at 1:1, stop to breakeven, 50% runs to 2:1+

**Invalidation**
- Entry price >0.5% above ORB high (chasing — do not enter)
- ORB range >1.5x ATR (skip)
- Breakout candle is low volume or has a long upper wick
- SPY/QQQ selling off at moment of breakout
- Price closes back below ORB high within 2 candles of entry

---

### 5.2 First Pullback to EMA

**Conditions (Market & Price Action)**
- Long: Regime Neutral or better. Short: Regime Bear or worse.
- Stock has made a directional move of at least 1x ATR off the open or a catalyst before the pullback
- Price is above (long) or below (short) the relevant EMA — trend is intact
- This is the first pullback to the EMA — count touches on the 5-min chart. If there have been 2 or more prior EMA touches since the directional move began, skip.
- Pullback depth: between 0.3x and 0.8x ATR
- **EMA selection rule:** use 9 EMA if the stock gapped >3% from prior close OR ATR/price >2.5%; use 21 EMA otherwise. This is determined at scan time — `run_scanner.py` computes gap% and ATR% and outputs an `ema` column (`9` or `21`) in the watchlist CSV. The trader reads this at morning review. `run_sizing.py` does not need to know which EMA was used.
- RVOL >1.2x (time-of-day adjusted, TOS native) at time of entry
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
- RVOL >1.5x (time-of-day adjusted, TOS native) on the reclaim candle (non-negotiable)
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

**Input interface (`run_sizing.py`):** accepts command-line arguments:
```
python run_sizing.py --entry 47.50 --stop 46.80 --setup orb
python run_sizing.py --entry 52.10 --stop 52.60 --setup vwap_short
```

Valid setup values: `orb`, `ema_pullback`, `vwap_reclaim`. Regime is read automatically from the most recent `run_regime.py` output (cached to `regime/last_regime.json`).

**Sizing formula:**

For **long trades** (`stop < entry`):
```
stop_distance = entry_price - stop_price
shares        = floor((account_size × risk_pct) / stop_distance)
dollar_risk   = shares × stop_distance
target_1      = entry_price + stop_distance          # 1:1
target_2      = entry_price + (2 × stop_distance)   # 2:1
```

For **short trades** (`stop > entry`):
```
stop_distance = stop_price - entry_price
shares        = floor((account_size × risk_pct) / stop_distance)
dollar_risk   = shares × stop_distance
target_1      = entry_price - stop_distance          # 1:1
target_2      = entry_price - (2 × stop_distance)   # 2:1
```

**Built-in guards:**

| Check | Rule | Output |
|-------|------|--------|
| Minimum R:R | Target 2 must be ≤ 2x ATR from entry | Warning if not reachable |
| Stop too wide | Stop distance >1x ATR | Warning — consider skipping |
| Position size cap | Position value >25% of account | Flag for review |
| Setup not allowed | Setup blocked by current regime | Hard block with reason printed |
| Entry too far from ORB trigger | >0.5% above ORB high (passed as `--orb_high`) | Warning — likely chasing |
| Total open risk cap | Total open risk must not exceed $600. Pass current open risk via `--open_risk`. If flag is omitted, assume $0 open risk (no existing positions). | Hard block if exceeded |

**`--open_risk` flag:** optional dollar amount currently at risk in open positions. Enables the total open risk guard. Example:
```
python run_sizing.py --entry 47.50 --stop 46.80 --setup orb --open_risk 250
```

**Terminal output example:**
```
=== POSITION SIZING: ORB LONG ===

Regime:         Strong Bull  →  Risk: 1.5% ($300)
Trade:          LONG

Entry:          $47.50
Stop:           $46.80
Stop Distance:  $0.70  (1.47% | 0.63x ATR)   ✓

Shares:         428
Dollar Risk:    $299.60
Position Value: $20,330  ⚠ >25% of account — review

Target 1 (1:1): $48.20  →  $299.60 profit  [exit 214 shares]
Target 2 (2:1): $48.90  →  $599.20 profit  [exit 214 shares]

R:R:            2.00:1  ✓
ATR Check:      Target 2 is 1.25x ATR from entry  ✓ (reachable)
```

---

## 7. Time-of-Day Rules

| Window | Rule |
|--------|------|
| 9:30–9:35 AM | Observation only — no entries |
| 9:35–9:45 AM | ORB forming — mark high/low, no entries |
| 9:45–**10:30 AM** | ORB Long valid window (ends at 10:30 AM — ORB is stale after this) |
| 9:45–11:30 AM | Primary session — EMA pullback and VWAP reclaim active |
| 11:30 AM–2:00 PM | No new entries — lunch lull |
| 2:00–3:30 PM | Secondary session — EMA pullback and VWAP reclaim only (ORB does not apply) |
| 3:30–4:00 PM | No new entries |
| By 3:55 PM | Close all intraday positions — no unintended overnight holds |

**Note:** The primary session window (9:45–11:30 AM) covers all three setups but ORB is restricted to the first sub-window (9:45–10:30 AM) within it.

**Special rules:**
- **FOMC days:** Fed announcements occur at 2:00 PM EST. No new entries from 11:30 AM through 2:30 PM (replaces the standard lunch blackout and adds a 30-minute post-announcement window). Secondary session resumes at 2:30 PM on FOMC days. FOMC calendar is maintained as a hardcoded list of dates in `config.py`, updated at the start of each year.
- **Pre-earnings:** never hold through an earnings report — close any position in a reporting stock by 3:55 PM.

---

## 8. Daily Risk Rules

| Rule | Value | Notes |
|------|-------|-------|
| Max daily loss | 2% ($400) | Hard stop — close all positions, no more entries that day |
| Max consecutive losers | 2 in a row | Mandatory 30-min break, reassess regime score before re-engaging |
| Max total open risk | $600 at any one time | Hard cap — replaces "2 full-size positions" language. In Strong Bull (1.5% = $300/trade), this allows 2 concurrent positions. In Choppy (0.75% = $150/trade), this allows up to 4 concurrent positions. `run_sizing.py` enforces this via `--open_risk` flag. |
| Max trades per day | 5 total (max 3 in primary, max 2 in secondary) | Day is done once 5 trades are taken, regardless of P&L |
| Daily profit target | 4% ($800) | Soft stop — once hit, only take setups with all confirmation criteria fully met |

---

## 9. Daily Workflow

**Night before (~4:30 PM after close)**
1. Run `python run_scanner.py` → generates `watchlist_YYYY-MM-DD.csv` and `watchlist.txt`
2. Review CSV — note trend classification and flagged setups per stock
3. Import `watchlist.txt` into TOS watchlist
4. Pre-mark key levels on TOS charts: prior day high/low, 9/21 EMA, approximate VWAP anchor

**Pre-market (~9:00–9:15 AM)**
1. Run `python run_regime.py` → prints today's regime tier, risk %, and active setup gates; writes `regime/last_regime.json`
2. Re-filter watchlist in TOS using live pre-market RVOL and gap data
3. Narrow to 3–5 highest conviction names aligned with today's regime

**Market open (9:30–9:45 AM)**
- Observation only — watch how names open, note which side of VWAP they're on, let ORB range form

**Primary session (9:45–11:30 AM)**
- ORB valid through 10:30 AM; EMA pullback and VWAP reclaim valid through 11:30 AM
- Before each entry: `python run_sizing.py --entry X --stop Y --setup Z [--open_risk N]`
- Max 3 trades

**Midday (11:30 AM–2:00 PM)**
- No new entries (2:30 PM on FOMC days)
- Manage open positions only

**Secondary session (2:00–3:30 PM)**
- EMA pullback and VWAP reclaim only
- Max 2 trades

**End of day (3:30–4:00 PM)**
- No new entries after 3:30 PM
- Close all positions by 3:55 PM
- Run `python run_scanner.py` for next day

---

## 10. File Structure

```
intraday/
├── config.py                  # account size, universe list, filter thresholds, FOMC calendar
├── scanner/
│   ├── __init__.py
│   ├── fetcher.py             # pulls OHLCV, ATR, EMA, gap, RVOL via yfinance
│   ├── filters.py             # price, volume, ATR, gap, RVOL filters
│   ├── trend.py               # trend classification (3-bar fractal swing detection)
│   └── scanner.py             # orchestrates scan, produces ranked CSV output
├── regime/
│   ├── __init__.py
│   ├── fetcher.py             # pulls QQQ, VIX, S&P 500 components, sector ETFs, CBOE P/C CSV
│   ├── scorer.py              # scoring matrix, regime classification
│   ├── regime.py              # orchestrates regime scoring, prints output, writes last_regime.json
│   └── last_regime.json       # cached output read by run_sizing.py
├── sizing/
│   ├── __init__.py
│   └── calculator.py          # sizing formula (long + short), guards, formatted terminal output
├── run_scanner.py             # entry point: EOD scan
├── run_regime.py              # entry point: morning regime check
├── run_sizing.py              # entry point: per-trade sizing (CLI args)
└── requirements.txt
```

**Tech stack:** Python 3.10+, yfinance, pandas, numpy, requests (CBOE CSV download), tabulate (formatted terminal output)
