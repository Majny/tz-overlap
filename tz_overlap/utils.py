"""Timezone utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones


def parse_timezone(tz_str: str) -> ZoneInfo:
    """Parse and validate an IANA timezone string.

    Args:
        tz_str: IANA timezone identifier (e.g. 'America/New_York').

    Returns:
        ZoneInfo instance.

    Raises:
        ValueError: If the timezone is not a valid IANA identifier.
    """
    # Allow common aliases
    aliases = {
        "UTC": "UTC",
        "EST": "America/New_York",
        "CST": "America/Chicago",
        "MST": "America/Denver",
        "PST": "America/Los_Angeles",
        "CET": "Europe/Paris",
        "EET": "Europe/Bucharest",
        "IST": "Asia/Kolkata",
        "JST": "Asia/Tokyo",
        "AEST": "Australia/Sydney",
        "GMT": "Europe/London",
    }

    resolved = aliases.get(tz_str.upper(), tz_str)

    try:
        return ZoneInfo(resolved)
    except (KeyError, Exception):
        raise ValueError(
            f"Unknown timezone: '{tz_str}'. Use IANA identifiers like 'America/New_York' or 'Europe/Prague'."
        )


def now_in_tz(tz_str: str) -> datetime:
    """Get the current time in a specific timezone.

    Args:
        tz_str: IANA timezone string.

    Returns:
        Current datetime in the specified timezone.
    """
    tz = parse_timezone(tz_str)
    return datetime.now(timezone.utc).astimezone(tz)


def format_time_range(start: str, end: str) -> str:
    """Format a time range for display.

    Args:
        start: Start time as HH:MM string.
        end: End time as HH:MM string.

    Returns:
        Formatted string like '09:00–17:00'.
    """
    return f"{start}–{end}"


def list_common_timezones() -> list[str]:
    """Return a sorted list of common IANA timezone identifiers.

    Filters to major city timezones (excludes obscure/deprecated ones).
    """
    all_tzs = sorted(available_timezones())
    # Filter to well-known regions
    regions = ("Africa/", "America/", "Asia/", "Australia/", "Europe/", "Pacific/")
    return [tz for tz in all_tzs if any(tz.startswith(r) for r in regions)]
