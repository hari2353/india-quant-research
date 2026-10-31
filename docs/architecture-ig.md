# Architecture mapping — IG post `De2EFbZjBHi` (@arwazaz_) → india-quant

The IG post proposed a research-agent trading pipeline. This doc maps each of
its layers onto this repository so the roadmap is explicit: what exists, what
is deferred, and the order we adopt it (paper-first; live stays behind the
plan-approval gate — see `LIVE-TRADING.md`).

| IG layer | Repo today | Status |
|---|---|---|
| Research agents | `strategies.py` fixed strategies (equal_weight, balanced, defensive_rotation, buy_hold); per-strategy weights from info available pre-rebalance | **v1 done** (deterministic rules instead of agents) |
| Orchestrator | `backtest.py` scores all strategies over one walk-forward; `paper.py` runs each strategy's ledger independently | **v1 done** (batch compare, not adversarial selection) |
| Code-gen of strategies | — | deferred; same shape as STAIR/QLoRA milestones (graph-memory T12) rather than LLM code-gen |
| Backtest / OOS / robustness gates | `backtest.py` walk-forward, `stress.py` (drawdown/crash/fee-stress), `metrics.py` (CAGR, maxDD, PF, trades) | **done** |
| Versioned self-improvement loop | git history + immutable SQLite paper ledger (idempotent replays via `source_hash`) | **partial** — versioned inputs recorded, no auto-promotion; promotion stays a human decision |
| Error-analysis memory | `orders.status/reason` + `runs.reason` in the SQLite ledgers (`paper/paper.db`) | **partial v1** — rejections recorded; analysis views deferred |
| Data: Yahoo (research) | `data.py` adapter | done (research-only, not a market-data licence) |
| Data: TradingView / MT5 | — | deferred behind the same adapter interface in `data.py` |
| Data: news/calendar, alt-data | — | deferred |
| Broker adapter | `broker.py` + `cli.py live-plan/approve-plan/live-execute` | **done, approval-gated**, disabled by default |
| Live/paper switch | `LIVE-TRADING.md`, plan files + signed approval, separate `live/live.db` | done |

## Adoption order (paper-first, per ledger T13/T21)

1. Real Yahoo data → backtest → **paper-run daily/monthly** on the DB (running).
2. Error-analysis SQL views over the existing ledger tables (small addition).
3. Second data adapter (news/calendar) only after a use in strategies exists.
4. Code-gen/orchestrator/agents and self-improvement remain future work
   (graph-memory T12); nothing auto-trades.
