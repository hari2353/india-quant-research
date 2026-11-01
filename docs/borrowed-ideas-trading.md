# Borrowed ideas — trading repo (T13/T14 follow-up)

Cross-pollination from the open-source tools installed/studied this session.
Each idea maps to an existing india-quant module; nothing here auto-trades
(live stays behind the plan-approval gate per `LIVE-TRADING.md`).

| Source | Best idea | Where it lands in india-quant |
|---|---|---|
| **AutoHedge** (`The-Swarm-Corporation/AutoHedge`, MIT, pip `autohedge`) | Multi-agent pipeline: Director → Quant → Risk → Execution, with a hard risk gate before execution | `strategies.py` + `backtest.py` already split concerns; the risk gate mirrors `paper.py._risk_gate`. Borrow the explicit Director/Quant/Risk/Execution *role split* as separate functions in a future `orchestrator.py` (M2). |
| **Vibe-Trading** (`HKUDS/Vibe-Trading`, MIT, pip `vibe-trading-ai`) | "Shadow account": compare the paper ledger against a real broker journal; 29 data sources with smart fallback; broker-authorized live trading (opt-in) | `paper.py` ledger is the shadow account already; add a `shadow_compare(broker_journal)` helper (M2). Data-adapter fallback pattern → `data.py` (already adapter-shaped). |
| **Vibe-Trade** (`vibetrade-ai/vibe-trade`) | Dhan broker (India-relevant), approve-gated trades, trade journal with reasoning | Already have `broker.py` + `cli.py live-plan/approve-plan/live-execute`. Borrow the trade-journal-with-reasoning idea into `paper.py` orders (add `reason` column — already present). |
| **OpenBB** (`OpenBB-finance/OpenBB`, AGPL, pip `openbb`) | Open Data Platform: standardized data integrations, 600+ commands | `data.py` is already an adapter; document the adapter contract so new sources (news/calendar) plug in without touching strategies. |
| **Fincept** (`Fincept-Corporation/FinceptTerminal`, AGPL) | 100+ data connectors, QuantLib pricing, multi-agent research | Borrow the connector/adapter pattern for a second data source (news/calendar) — next M1 slice. Backtesting only in Enterprise; our `backtest.py` stays the source of truth. |
| **Octop** (`TencentCloud/Octop`, MIT, docker) | Self-hosted multi-agent, single process, SQLite control plane, IM channels, cron | Borrow cron scheduling + IM notification for `paper-run` automation (M2). Control-plane-in-SQLite mirrors our paper ledger. |
| **OpenShell** (`NVIDIA/OpenShell`) | Policy-enforced egress/fs/process isolation for agent fleets | Borrow the policy-as-code idea for live trading (already gated by approval; add an explicit policy file). |
| **Sure** (`we-promise/sure`, AGPL fork of maybe) | Net-worth/portfolio tracking UI | Reference only — india-quant is CLI/research-focused; UI is out of scope for M1. |
| **openworker** (`andrewyng/openworker`, MIT) | Governed-by-design: every action approval-gated and logged | Already in `LIVE-TRADING.md` + `broker.py`. Reinforce: no auto-send. |
| **openjev** (`GPT-AGI/OpenJev`, MIT, npm) | Sub-3ms System One decision model for fast routing | Reference for a fast trade-router (M2+); CC BY-NC weights → non-commercial only. |
| **AutoHedge** | Risk-first architecture: position sizing + risk assessment before execution | Already in `paper.py._risk_gate`; borrow the explicit Risk Manager role. |

## Adoption order (paper-first)

1. Second data adapter (news/calendar) behind the existing `data.py` interface.
2. Shadow-account comparison: `paper.py` ledger vs a real broker journal.
3. Cron + IM notifications (Octop pattern) for unattended `paper-run`.
4. Agent role split (Director/Quant/Risk/Execution) as separate functions.
5. Policy file for live trading (OpenShell pattern).
EOF