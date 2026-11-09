#!/bin/zsh
# T21 daily paper-trade runner: one clean session per completed market day.
# Idempotent per date — reruns never duplicate fills. Network failure does not
# corrupt the ledger (reads a fresh snapshot; paper-run only records filled days).
set -euo pipefail
cd "$HOME/india-quant-research"
mkdir -p paper
git pull -q origin main || true  # keep latest code; ledger db is local-only

PY=$HOME/india-quant-research/.venv/bin/python
$PY -m india_quant.cli download --out data/prices.csv --years 3 >> paper/runner.log 2>&1

TODAY=$(date +%F)
$PY -m india_quant.cli paper-run --prices data/prices.csv --db paper/paper.db \
    --out paper/reports --date "$TODAY" >> paper/runner.log 2>&1
$PY -m india_quant.cli paper-analyze --db paper/paper.db >> paper/runner.log 2>&1
echo "$(date '+%F %H:%M') runner OK ($TODAY)" >> paper/runner.log
