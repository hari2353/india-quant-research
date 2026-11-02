# Time-series foundation models → india-quant (T13/T14 follow-up)

Two foundation models are wired into the research pipeline as **optional** signal
sources. Both are zero-shot: no training on our data; they provide a directional
forecast that a strategy can consume as an additional feature. The existing
deterministic strategies remain the source of truth; the forecast is a feature,
not a decision.

## Kronos (shiyu-coder/Kronos, MIT)

- **What:** a foundation model for the "language of financial markets" — tokenizes
  OHLCV bars and forecasts future bars (close, volume) via a transformer.
- **Repo:** https://github.com/shiyu-coder/Kronos (MIT). HuggingFace: `NeoQuasar/Kronos-small`.
- **Install:** `pip install -r requirements.txt` (needs torch, pyqlib). Heavy; runs on GPU.
- **Use in india-quant:** optional `KronosPredictor`-based feature in a strategy.
  Falls back to the existing momentum rule when unavailable. Adapter lives in
  `forecast.py` (Kronos branch, guarded import).

## TimesFM (google-research/timesfm, Apache 2.0 source)

- **What:** Google's time-series foundation model for zero-shot forecasting.
- **Repo:** https://github.com/google-research/timesfm. pip: `pip install timesfm[torch]`.
- **Weights:** TimesFM 2.5 weights are Apache 2.0 (commercial OK). TimesFM 3.0 weights
  are non-commercial (`timesfm-non-commercial-license-v1.0`) — use 2.5 for anything
  commercial.
- **Use in india-quant:** `forecast.py` wraps `TimesFM_2p5_200M_torch` for zero-shot
  point + quantile forecasts of the ETF close series. Optional; falls back to a
  naive (last-value) forecast when the model/weights are unavailable.

## Adoption rules (paper-first, consistent with LIVE-TRADING.md)

1. Forecast is a **feature**, not a decision. Strategies consume it; the risk gate
   (`paper.py._risk_gate`) and approval gate (`broker.py`) are unchanged.
2. Every forecast is logged with the model name + version so a paper run is
   reproducible (mirrors `source_hash` in the paper ledger).
3. No new data leaves the machine; both models run locally.
4. If a model is unavailable (no GPU, no weights), the strategy falls back to the
   existing deterministic rule — never blocks the pipeline.
EOF