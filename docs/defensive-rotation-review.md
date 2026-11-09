# defensive_rotation: why it lags, and what to do

Date: 2026-11-09 · Data: `paper/bt` (3-year, 2,214 rows) + `paper/bt5y` (5-year, walk-forward)

## Verdict

`defensive_rotation` is a benchmark, not a candidate. Keep it in the enum as the
risk-floor reference; do not fund it against `equal_weight` / `balanced` /
`event_defensive` at the T21 allocation talk.

## What the strategy does (src/india_quant/strategies.py:72-89)

1. Needs 200+ days of history. Below that: zero weights (all cash).
2. Scores each symbol: 126-day momentum / 63-day volatility, gated by a 200-day mean trend filter.
3. Holds the top 2 positive scorers, weighted by inverse volatility.

## Why it lags (evidence)

- Full-period 5y: CAGR 3.74%, maxDD −11.00% vs equal_weight 9.65% / −11.98%. The
  drawdown protection buys −4.5% of return for −1.0% of drawdown — a bad price.
  3y is worse: 2.98% / −9.26%.
- Cash drag: when the trend filter fails on every symbol, weights go to 0.0. After
  each reset the strategy buys back late. Bull phases therefore accrue to the
  static allocations, not to it.
- Concentration: inverse-vol weighting skews into the least-volatile asset in the
  universe. In this 3-symbol ETF set (NIFTYBEES / GOLDBEES / LIQUIDBEES) that is
  often the cash-like sleeve — the position is de-facto cash with extra steps.
- Turnover: first walk-forward window shows turnover 104% on 9 trades — large
  single-day rebalances, fee-heavy, and they occupy the risk budget without
  improving the trend signal.
- Stress (`report.json`, bootstrapped drawdowns): P05 maxDD −18.8%, median −9.5%,
  P95 −5.7%, probability of loss 44.3%. The tail is fatter than the backtest's
  headline −11% suggests.

## What stays true about it

- It needs no forecast model, no calendar, and no tuning. It is the honest
  "protect first" reference point.
- Its Sharpe is not the worst in every window; in walk-forward window 1 it posted
  Sharpe 2.85 (window-specific). Judge it over windows, not by one row.

## Recommendation

1. Keep in the enum; report it in every summary; exclude from the funded set.
2. If a T21 allocation debate needs a defensive arm, `balanced` (0.60/0.20/0.15)
   with the min-cash buffer already does that job at CAGR 9.18%.
3. Revisit only if the universe grows (more symbols → less concentration) or the
   gate moves from CAGR-first to drawdown-first.
