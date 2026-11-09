from datetime import date

from india_quant.calendar import EVENT_LOOKAHEAD_DAYS, EVENTS, calendar_frame, upcoming_events


def test_window_covers_budget_and_mpc():
    events = upcoming_events(date(2026, 1, 31))
    assert (date(2026, 2, 1), "Union Budget") in events
    assert (date(2026, 2, 6), "RBI MPC decision") in events
    assert events == sorted(events)
    # An event is live on its own day and dead after the horizon.
    assert upcoming_events(date(2026, 2, 1))[0] == (date(2026, 2, 1), "Union Budget")
    assert upcoming_events(date(2026, 4, 1), within_days=1) == []
    assert upcoming_events(date(2026, 3, 10)) == []


def test_default_window_matches_constant():
    day = date(2026, 1, 31)
    assert upcoming_events(day) == upcoming_events(day, EVENT_LOOKAHEAD_DAYS)
    assert EVENT_LOOKAHEAD_DAYS == 7


def test_calendar_frame_is_sorted_and_complete():
    frame = calendar_frame()
    assert list(frame.columns) == ["date", "event"]
    assert len(frame) == len(EVENTS)
    assert list(frame["date"]) == sorted(day for day, _ in EVENTS)
    assert frame["date"].iloc[0] == date(2025, 12, 5)
    assert frame["date"].iloc[-1] == date(2027, 2, 1)
