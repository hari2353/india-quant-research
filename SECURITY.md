# Security & Privacy

## What this repo is

quant research over public Yahoo data. Paper trading only; live broker code (broker.py) is approval-gated and disabled by default. API keys never enter the repo.

## Supported versions

Security fixes land on `main` only — pull the latest rather than pinning old tags.

## Reporting a vulnerability

Do **not** open a public issue. Use GitHub's private security advisory
(`india-quant-research` → Security → Report a vulnerability); it reaches @hari2353 directly.
Expect a first response within one week.

## Baseline controls

- Dependencies are scanned in CI (pip-audit / govulncheck, weekly scheduled), reports fail the build.
- No secrets in code or history; tests enforce credential hygiene where applicable.
- Gov-cloud readiness and the honest certification-lane map live in the master workspace
  `docs/gov-cloud-certification.md` (FedRAMP/StateRAMP authorization is organizational,
  not a repo attribute — see that file).
