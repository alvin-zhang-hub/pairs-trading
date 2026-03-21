# Avellaneda & Lee Pairs Trading Strategy

A Python implementation of the statistical arbitrage pairs trading strategy from [Avellaneda & Lee (2010)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1494434).

## Strategy Overview

Brief explanation of strategy:
- Identify mean-reverting pairs within sectors
- Residual extraction: regress stock on ETF to isolate idiosyncratic component
- OU modeling: model residuals as mean-reverting Ornstein-Uhlenbeck process
- S-score signals: standardized distance from equilibrium
- Trading rules:
  - Buy (long stock, short ETF) when s-score < −1.25
  - Short (short stock, long ETF) when s-score > +1.25
  - Close long when s-score > −0.50
  - Close short when s-score < +0.75
- Volume weighting: discount high-volume moves, amplify low-volume signals

## Sectors Covered

**Technology** (vs IGV - iShares Global Tech ETF):
- MSFT, AAPL, NVDA, META, GOOGL, TSLA, AVGO, CRM, ADBE, CSCO

**Semiconductors** (vs SMH - iShares Semiconductor ETF):
- NVDA, TSM, AVGO, ASML, INTC, QCOM, AMD, AMAT, LRCX, KLAC

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Run the full pipeline:

```bash
python run.py
```

This will:
1. Fetch 1 year of OHLCV data
2. Generate today's trading signals
3. Run a 6-month backtest
4. Compute performance metrics (Sharpe, max drawdown, win rate)
5. Plot equity curve vs benchmarks

## Output

- **Daily signals table** (printed to console)
- **Trade history** (buy/sell dates, P&L)
- **Equity curve plot** (`equity_curve.png`)

## Key Parameters

Edit `run.py` to adjust:
- Stock universe (SAAS_STOCKS, SEMI_STOCKS)
- Initial capital (INITIAL_CASH)
- Transaction costs (TRANSACTION_COST)
- Regression window (60 days)
- S-score thresholds (−1.25, +1.25, etc.)
- Max half-life filter (30 days)

## Testing

Run unit tests:

```bash
pytest tests/ -v
```

## Project Structure

```
src/
  data/       # Data fetching and preprocessing
  signals/    # Signal generation (regression, OU, s-scores)
  backtest/   # Portfolio simulation
  metrics/    # Performance calculations
  plotting/   # Visualizations

tests/
  test_data.py        # Data fetcher tests
  test_signals.py     # Regression and OU tests
  test_backtest.py    # Portfolio tests
  test_metrics.py     # Metrics tests
  test_integration.py # End-to-end tests

run.py       # Main orchestration script
```

## References

- Avellaneda, M., & Lee, J. H. (2010). Statistical arbitrage in the US equities market. *The Journal of Finance*, 65(5), 1827-1861.
