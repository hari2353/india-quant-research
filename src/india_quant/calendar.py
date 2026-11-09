"""Committed market-event calendar (RBI MPC decisions, Union Budget).

Dates come from published advance schedules and are committed here instead of
fetched at runtime, so backtests and paper runs stay reproducible and causal.
Re-check against the RBI / government calendars before live trading.

shortcut: movable NSE holidays and unscheduled events are not modeled; add
them when a strategy actually consumes them.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

EVENT_LOOKAHEAD_DAYS = 7

# (date, name): decision day (last day) of each RBI MPC meeting, plus Union
# Budget presentation days. Sorted by date.
EVENTS: tuple[tuple[date, str], ...] = (
    (date(2025, 12, 5), "RBI MPC decision"),
    (date(2026, 2, 1), "Union Budget"),
    (date(2026, 2, 6), "RBI MPC decision"),
    (date(2026, 4, 8), "RBI MPC decision"),
    (date(2026, 6, 5), "RBI MPC decision"),
    (date(2026, 8, 7), "RBI MPC decision"),
    (date(2026, 10, 1), "RBI MPC decision"),
    (date(2026, 12, 4), "RBI MPC decision"),
    (date(2027, 2, 1), "Union Budget"),
)


def upcoming_events(as_of: date, within_days: int = EVENT_LOOKAHEAD_DAYS) -> list[tuple[date, str]]:
    """Events in the window [as_of, as_of + within_days], in calendar order."""
    horizon = as_of + timedelta(days=within_days)
    return [(day, name) for day, name in EVENTS if as_of <= day <= horizon]


def calendar_frame() -> pd.DataFrame:
    """The committed calendar as a DataFrame(date, event), sorted."""
    return pd.DataFrame(sorted(EVENTS), columns=["date", "event"])
