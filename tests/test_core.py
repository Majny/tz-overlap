"""Tests for tz-overlap core functionality."""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from tz_overlap import (
    WorkWindow,
    find_overlap,
    get_overlap_windows,
    best_meeting_times,
)


# --- WorkWindow ---

def test_work_window_creation():
    w = WorkWindow(timezone="Europe/Prague")
    assert w.start == time(9, 0)
    assert w.end == time(17, 0)
    assert w.tz == ZoneInfo("Europe/Prague")


def test_work_window_invalid_tz():
    with pytest.raises(ValueError, match="Unknown timezone"):
        WorkWindow(timezone="Fake/Nowhere")


def test_work_window_custom_hours():
    w = WorkWindow(timezone="America/New_York", start=time(8, 0), end=time(16, 0))
    assert w.start == time(8, 0)
    assert w.end == time(16, 0)


def test_work_window_utc_range():
    w = WorkWindow(timezone="UTC")
    date = datetime(2026, 3, 15, tzinfo=timezone.utc)
    start, end = w.utc_range(date)
    assert start.hour == 9
    assert end.hour == 17


# --- find_overlap ---

def test_overlap_prague_newyork():
    """Prague (CET, UTC+1) and New York (EST, UTC-5) — 6 hour difference."""
    date = datetime(2026, 1, 15, tzinfo=timezone.utc)  # Winter, no DST
    prague = WorkWindow(timezone="Europe/Prague", label="Prague")
    ny = WorkWindow(timezone="America/New_York", label="New York")
    result = find_overlap(prague, ny, date=date)

    assert result.has_overlap
    # Prague 09-17 = UTC 08-16, NY 09-17 = UTC 14-22
    # Overlap: UTC 14:00 - 16:00 = 2 hours
    assert result.overlap_minutes == 120
    local = result.local_times()
    assert local["Prague"] == ("15:00", "17:00")
    assert local["New York"] == ("09:00", "11:00")


def test_overlap_three_timezones():
    """Prague, New York, and Tokyo."""
    date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    prague = WorkWindow(timezone="Europe/Prague", label="Prague")
    ny = WorkWindow(timezone="America/New_York", label="NY")
    tokyo = WorkWindow(timezone="Asia/Tokyo", label="Tokyo")
    result = find_overlap(prague, ny, tokyo, date=date)

    # Prague UTC 08-16, NY UTC 14-22, Tokyo UTC 00-08
    # No three-way overlap
    assert not result.has_overlap
    assert result.overlap_minutes == 0


def test_no_overlap():
    """Sydney and San Francisco — should have minimal or no overlap."""
    date = datetime(2026, 6, 15, tzinfo=timezone.utc)  # Summer
    sydney = WorkWindow(timezone="Australia/Sydney", label="Sydney")
    sf = WorkWindow(timezone="America/Los_Angeles", label="SF")
    result = find_overlap(sydney, sf, date=date)

    # Sydney AEST (UTC+10) in June: 09-17 = UTC 23(prev)-07
    # SF PDT (UTC-7) in June: 09-17 = UTC 16-00(next)
    # No overlap
    assert not result.has_overlap


def test_overlap_adjacent_timezones():
    """London and Paris — should have 7 hours overlap."""
    date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    london = WorkWindow(timezone="Europe/London", label="London")
    paris = WorkWindow(timezone="Europe/Paris", label="Paris")
    result = find_overlap(london, paris, date=date)

    assert result.has_overlap
    # London UTC 09-17, Paris UTC 08-16
    # Overlap: 09-16 UTC = 7 hours
    assert result.overlap_minutes == 420


def test_overlap_same_timezone():
    """Same timezone — full 8 hours overlap."""
    date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    a = WorkWindow(timezone="Europe/Prague", label="Team A")
    b = WorkWindow(timezone="Europe/Prague", label="Team B")
    result = find_overlap(a, b, date=date)

    assert result.has_overlap
    assert result.overlap_minutes == 480


def test_fewer_than_two_windows():
    with pytest.raises(ValueError, match="at least 2"):
        find_overlap(WorkWindow(timezone="UTC"))


# --- get_overlap_windows convenience ---

def test_get_overlap_windows_basic():
    result = get_overlap_windows(
        ["Europe/Prague", "America/New_York"],
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    assert result.has_overlap
    assert result.overlap_minutes == 120


def test_get_overlap_windows_with_labels():
    result = get_overlap_windows(
        ["Europe/Prague", "America/New_York"],
        labels=["Prague HQ", "NYC Office"],
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    local = result.local_times()
    assert "Prague HQ" in local
    assert "NYC Office" in local


def test_get_overlap_windows_labels_mismatch():
    with pytest.raises(ValueError, match="labels must match"):
        get_overlap_windows(
            ["Europe/Prague", "America/New_York"],
            labels=["only one"],
        )


# --- best_meeting_times ---

def test_best_meeting_times_30min():
    date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    prague = WorkWindow(timezone="Europe/Prague", label="Prague")
    ny = WorkWindow(timezone="America/New_York", label="NY")
    slots = best_meeting_times(prague, ny, date=date, slot_minutes=30)

    # 2 hours overlap = 4 slots of 30 min
    assert len(slots) == 4
    assert "start_utc" in slots[0]
    assert "local_times" in slots[0]


def test_best_meeting_times_no_overlap():
    date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    tokyo = WorkWindow(timezone="Asia/Tokyo")
    sf = WorkWindow(timezone="America/Los_Angeles")
    # They likely have no overlap or very little
    slots = best_meeting_times(tokyo, sf, date=date, slot_minutes=30)
    # Tokyo UTC 00-08, SF UTC 17-01 (winter PST UTC-8)
    # Actually: Tokyo 09-17 JST = UTC 00-08, SF 09-17 PST = UTC 17-01
    # No overlap
    assert len(slots) == 0


# --- DST handling ---

def test_dst_transition_spring():
    """Test overlap during US spring-forward (March 2026)."""
    # US springs forward March 8, 2026; Europe March 29, 2026
    date_between = datetime(2026, 3, 15, tzinfo=timezone.utc)
    prague = WorkWindow(timezone="Europe/Prague", label="Prague")  # Still CET (UTC+1)
    ny = WorkWindow(timezone="America/New_York", label="NY")  # Now EDT (UTC-4)

    result = find_overlap(prague, ny, date=date_between)
    assert result.has_overlap
    # Prague CET: 09-17 = UTC 08-16
    # NY EDT: 09-17 = UTC 13-21
    # Overlap: UTC 13-16 = 3 hours (1 more than winter!)
    assert result.overlap_minutes == 180


def test_dst_transition_both():
    """After both US and Europe spring forward."""
    date = datetime(2026, 4, 1, tzinfo=timezone.utc)
    prague = WorkWindow(timezone="Europe/Prague", label="Prague")  # CEST (UTC+2)
    ny = WorkWindow(timezone="America/New_York", label="NY")  # EDT (UTC-4)

    result = find_overlap(prague, ny, date=date)
    assert result.has_overlap
    # Prague CEST: 09-17 = UTC 07-15
    # NY EDT: 09-17 = UTC 13-21
    # Overlap: UTC 13-15 = 2 hours (back to normal)
    assert result.overlap_minutes == 120


# --- summary output ---

def test_summary_with_overlap():
    date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    result = find_overlap(
        WorkWindow(timezone="Europe/Prague", label="Prague"),
        WorkWindow(timezone="America/New_York", label="NY"),
        date=date,
    )
    summary = result.summary()
    assert "2h" in summary
    assert "Prague" in summary
    assert "NY" in summary


def test_summary_no_overlap():
    date = datetime(2026, 1, 15, tzinfo=timezone.utc)
    result = find_overlap(
        WorkWindow(timezone="Asia/Tokyo", label="Tokyo"),
        WorkWindow(timezone="Europe/Prague", label="Prague"),
        WorkWindow(timezone="America/Los_Angeles", label="SF"),
        date=date,
    )
    assert "No overlapping" in result.summary()
