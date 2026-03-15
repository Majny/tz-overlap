"""Core overlap computation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from .utils import parse_timezone


@dataclass(frozen=True)
class WorkWindow:
    """A working-hours window in a specific timezone.

    Attributes:
        timezone: IANA timezone string (e.g. 'Europe/Prague').
        start: Start of working hours (default 09:00).
        end: End of working hours (default 17:00).
        label: Optional human-readable label (e.g. 'Prague team').
    """

    timezone: str
    start: time = field(default_factory=lambda: time(9, 0))
    end: time = field(default_factory=lambda: time(17, 0))
    label: str | None = None

    def __post_init__(self):
        # Validate the timezone is real IANA
        parse_timezone(self.timezone)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def utc_range(self, date: datetime) -> tuple[datetime, datetime]:
        """Return (start_utc, end_utc) for this window on the given date.

        Handles DST transitions correctly by anchoring to the local date.
        """
        local_start = datetime.combine(date.date(), self.start, tzinfo=self.tz)
        local_end = datetime.combine(date.date(), self.end, tzinfo=self.tz)
        return (
            local_start.astimezone(timezone.utc),
            local_end.astimezone(timezone.utc),
        )


@dataclass(frozen=True)
class OverlapResult:
    """Result of an overlap computation.

    Attributes:
        windows: The input work windows.
        overlap_start_utc: Start of overlap in UTC.
        overlap_end_utc: End of overlap in UTC.
        overlap_minutes: Duration of overlap in minutes.
        date: The reference date used.
    """

    windows: tuple[WorkWindow, ...]
    overlap_start_utc: datetime | None
    overlap_end_utc: datetime | None
    overlap_minutes: int
    date: datetime

    @property
    def has_overlap(self) -> bool:
        return self.overlap_minutes > 0

    def local_times(self) -> dict[str, tuple[str, str]]:
        """Return overlap expressed in each participant's local time.

        Returns:
            Dict mapping timezone string to (start_local, end_local) formatted strings.
        """
        if not self.has_overlap:
            return {}
        result = {}
        for w in self.windows:
            tz = ZoneInfo(w.timezone)
            local_start = self.overlap_start_utc.astimezone(tz)
            local_end = self.overlap_end_utc.astimezone(tz)
            label = w.label or w.timezone
            result[label] = (
                local_start.strftime("%H:%M"),
                local_end.strftime("%H:%M"),
            )
        return result

    def summary(self) -> str:
        """Human-readable summary of the overlap."""
        if not self.has_overlap:
            return "No overlapping working hours found."
        hours = self.overlap_minutes // 60
        mins = self.overlap_minutes % 60
        duration = f"{hours}h{mins:02d}m" if mins else f"{hours}h"
        lines = [f"Overlap: {duration}"]
        for label, (start, end) in self.local_times().items():
            lines.append(f"  {label}: {start}–{end}")
        return "\n".join(lines)


def find_overlap(
    *windows: WorkWindow,
    date: Optional[datetime] = None,
) -> OverlapResult:
    """Find the overlapping working hours across multiple timezone windows.

    Args:
        *windows: Two or more WorkWindow instances.
        date: Reference date for DST calculation. Defaults to today (UTC).

    Returns:
        OverlapResult with the computed overlap.

    Raises:
        ValueError: If fewer than 2 windows are provided.
    """
    if len(windows) < 2:
        raise ValueError("Need at least 2 work windows to compute overlap.")

    if date is None:
        date = datetime.now(timezone.utc)

    # Convert all windows to UTC ranges
    utc_ranges = [w.utc_range(date) for w in windows]

    # Overlap = intersection of all ranges
    latest_start = max(r[0] for r in utc_ranges)
    earliest_end = min(r[1] for r in utc_ranges)

    if latest_start >= earliest_end:
        return OverlapResult(
            windows=tuple(windows),
            overlap_start_utc=None,
            overlap_end_utc=None,
            overlap_minutes=0,
            date=date,
        )

    overlap_delta = earliest_end - latest_start
    overlap_minutes = int(overlap_delta.total_seconds() // 60)

    return OverlapResult(
        windows=tuple(windows),
        overlap_start_utc=latest_start,
        overlap_end_utc=earliest_end,
        overlap_minutes=overlap_minutes,
        date=date,
    )


def get_overlap_windows(
    timezones: list[str],
    work_start: time = time(9, 0),
    work_end: time = time(17, 0),
    labels: Optional[list[str]] = None,
    date: Optional[datetime] = None,
) -> OverlapResult:
    """Convenience function: find overlap from a list of timezone strings.

    Args:
        timezones: List of IANA timezone strings.
        work_start: Working hours start (applied to all).
        work_end: Working hours end (applied to all).
        labels: Optional labels for each timezone.
        date: Reference date. Defaults to today.

    Returns:
        OverlapResult.
    """
    if labels and len(labels) != len(timezones):
        raise ValueError("labels must match timezones length")

    windows = []
    for i, tz in enumerate(timezones):
        label = labels[i] if labels else None
        windows.append(WorkWindow(timezone=tz, start=work_start, end=work_end, label=label))

    return find_overlap(*windows, date=date)


def best_meeting_times(
    *windows: WorkWindow,
    date: Optional[datetime] = None,
    slot_minutes: int = 30,
) -> list[dict]:
    """Find all available meeting slots within the overlap window.

    Args:
        *windows: Two or more WorkWindow instances.
        date: Reference date.
        slot_minutes: Slot duration in minutes (default 30).

    Returns:
        List of dicts with 'start_utc', 'end_utc', and 'local_times' for each slot.
    """
    result = find_overlap(*windows, date=date)
    if not result.has_overlap:
        return []

    slots = []
    current = result.overlap_start_utc
    slot_delta = timedelta(minutes=slot_minutes)

    while current + slot_delta <= result.overlap_end_utc:
        slot_end = current + slot_delta
        local = {}
        for w in windows:
            tz = ZoneInfo(w.timezone)
            label = w.label or w.timezone
            local[label] = {
                "start": current.astimezone(tz).strftime("%H:%M"),
                "end": slot_end.astimezone(tz).strftime("%H:%M"),
            }
        slots.append({
            "start_utc": current.isoformat(),
            "end_utc": slot_end.isoformat(),
            "local_times": local,
        })
        current += slot_delta

    return slots
