"""Tests for utility functions."""

import pytest
from zoneinfo import ZoneInfo

from tz_overlap.utils import parse_timezone, now_in_tz, format_time_range, list_common_timezones


def test_parse_valid_timezone():
    tz = parse_timezone("Europe/Prague")
    assert tz == ZoneInfo("Europe/Prague")


def test_parse_alias_est():
    tz = parse_timezone("EST")
    assert tz == ZoneInfo("America/New_York")


def test_parse_alias_pst():
    tz = parse_timezone("PST")
    assert tz == ZoneInfo("America/Los_Angeles")


def test_parse_alias_cet():
    tz = parse_timezone("CET")
    assert tz == ZoneInfo("Europe/Paris")


def test_parse_invalid():
    with pytest.raises(ValueError, match="Unknown timezone"):
        parse_timezone("Fake/Zone")


def test_now_in_tz():
    dt = now_in_tz("Europe/Prague")
    assert dt.tzinfo is not None
    assert str(dt.tzinfo) == "Europe/Prague"


def test_format_time_range():
    assert format_time_range("09:00", "17:00") == "09:00–17:00"


def test_list_common_timezones():
    tzs = list_common_timezones()
    assert len(tzs) > 100
    assert "Europe/Prague" in tzs
    assert "America/New_York" in tzs
