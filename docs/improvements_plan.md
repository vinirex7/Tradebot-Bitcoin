# Tradebot-Bitcoin improvement plan

This branch was created to test safer BTC allocation improvements before merging to main.

## Proposed changes

1. Add a sideways-market filter to reduce unnecessary rebalance churn.
2. Add volatility scaling so target allocation is reduced when ATR is unusually high.
3. Improve recovery logic after large drawdowns with progressive re-entry.
4. Expand backtests across multiple windows instead of relying on one period.
5. Improve live safety checks before orders.

## Test checklist

- Run full backtest from 2017.
- Run 1-year, 2-year, 3-year and 4-year windows.
- Compare return, max drawdown, Sharpe, Sortino and number of trades against buy and hold.
- Only merge if the strategy improves risk-adjusted results and does not overfit.