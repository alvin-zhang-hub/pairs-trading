# Account
ACCOUNT_SIZE = 20_000.0

# Scanner filters
PRICE_MIN = 10.0
PRICE_MAX = 500.0
AVG_VOLUME_MIN = 500_000
FLOAT_MIN = 10_000_000
FLOAT_MAX = 500_000_000
ATR_MIN_DOLLAR = 0.75
ATR_MIN_PCT = 0.009       # 0.9% of price
GAP_MIN_PCT = 0.02        # 2% from prior close
RVOL_MIN = 1.5
RVOL_LOOKBACK = 20        # trading days

# EMA selection thresholds
EMA_FAST_GAP_THRESHOLD = 0.03    # gap >3% → use 9 EMA
EMA_FAST_ATR_PCT_THRESHOLD = 0.025  # ATR/price >2.5% → use 9 EMA

# Regime
BREADTH_EMA_PERIOD = 20
BREADTH_MIN_VALID_PCT = 0.80  # skip breadth factor if fewer than 80% of tickers return valid data
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
