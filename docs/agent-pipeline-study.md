# Agent-pipeline study — AutoHedge + Vibe-Trading mapped to india-quant

Closes backlog T15/T16 (M1). Study of the two IG-referenced agent pipelines,
what maps onto this repository, and what is worth borrowing. Nothing here
auto-trades; live stays behind the approval gate (`LIVE-TRADING.md`).

## The AutoHedge pipeline (The-Swarm-Corporation/AutoHedge, MIT)

Agents: **Director → Quant → Risk → Execution**. The quant agent sizes
positions from analysis, risk vetoes/back-tests the thesis, execution routes
orders, the director orchestrates.

| AutoHedge role | Repo today | Verdict |
|---|---|---|
| Director | `research_report` batch + human strategy comparison; no auto-selection | keep human-in-loop |
| Quant agent | `strategies.target_weights` deterministic rules (+ `calendar.py` event windows) | already covered for fixed strategies; code-gen strategies = future (T12) |
| Risk agent | `stress.bootstrap_drawdowns`, `PortfolioConfig` caps, `PaperRiskConfig` | ours is stricter (deterministic, testable) |
| Execution | `backtest._execute` / `paper.py` fills; `broker.py` approval-gated live plan | keep |

Borrow list: their "portfolio analyst report" framing (annual return,
Sharpe, max drawdown + position commentary in one artifact) — already
half-covered by `reports/summary.csv` + `walk_forward.csv`.

## Vibe-Trading (HKUDS/Vibe-Trading, MIT)

Research agent: NL prompt → backtest → report, 29 data sources, plus a
"shadow account" that paper-trades alongside a real one. Also
`vibetrade-ai/vibe-trade` (Dhan broker, approve-gated — India-relevant).

| Vibe-Trading feature | Repo today | Borrow? |
|---|---|---|
| NL → backtest agent | CLI subcommands, explicit args | **no** — we backtest reproducibly, not conversationally |
| Shadow paper account | `PaperLedger` SQLite, idempotent replays | ours predates and is stricter (source-hash idempotence) |
| 29 data sources | `data.py` Yahoo adapter + `calendar.py` committed event table | adopt per-use (next: alt-data only when a strategy consumes it) |
| Dhan approve-gated orders | `broker.py` KiteLive (approval signature gate) | pattern identical; no code to borrow |

## Decision

No installs, no adapters joined to either package: our deterministic,
idempotent, test-first pipeline already implements the parts that matter for
the ₹1,00,000 go-live gate (T21). The only genuinely new idea was
event-calendar weighting, which landed as `calendar.py` + `event_defensive`
(same date as this note). Everything else is re-derivable if/when the
agent/code-gen milestones (T12) start.
