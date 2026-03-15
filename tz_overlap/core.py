"""Core overlap computation engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, date as date_type, time, timedelta, timezone
from itertools import combinations
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


# ---------------------------------------------------------------------------
# Team / Member API  (Sprint 2 — blog-post-promised surface)
# ---------------------------------------------------------------------------

def _parse_duration(s: str) -> timedelta:
    """Parse a human duration string like '30m', '1h', '1h30m' into timedelta."""
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?", s)
    if not m or (m.group(1) is None and m.group(2) is None):
        raise ValueError(f"Invalid duration format: '{s}'. Use e.g. '30m', '1h', '1h30m'.")
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    return timedelta(hours=hours, minutes=minutes)


@dataclass(frozen=True)
class OverlapWindow:
    """A computed overlap window between a subset of team members.

    Attributes:
        members: Member objects who overlap (also accessible as names via member_names).
        start_utc: Start of overlap in UTC.
        end_utc: End of overlap in UTC.
        duration: Duration as a timedelta.
    """

    members: list  # list[Member] — forward ref avoids circular
    start_utc: datetime
    end_utc: datetime
    duration: timedelta

    @property
    def member_names(self) -> list[str]:
        """Return names of members in this window."""
        return [m.name if hasattr(m, 'name') else str(m) for m in self.members]

    @property
    def duration_minutes(self) -> int:
        return int(self.duration.total_seconds() // 60)

    def __repr__(self) -> str:
        mins = self.duration_minutes
        names = ", ".join(self.member_names)
        return (
            f"OverlapWindow(members=[{names}], "
            f"start_utc={self.start_utc.strftime('%H:%M')}, "
            f"end_utc={self.end_utc.strftime('%H:%M')}, "
            f"duration={mins}m)"
        )


@dataclass(frozen=True)
class BestWindowResult:
    """Result of Team.best_window().

    Attributes:
        start_utc: Start of the best window in UTC.
        end_utc: End of the best window in UTC.
        members_included: Names of members whose work hours fall inside the window.
        has_out_of_hours: True if any included member is outside their normal hours.
        out_of_hours_members: Names of members outside their normal hours.
    """

    start_utc: datetime
    end_utc: datetime
    members_included: list  # list[Member]
    has_out_of_hours: bool = False
    out_of_hours_members: list = field(default_factory=list)  # list[Member]

    @property
    def duration(self) -> timedelta:
        return self.end_utc - self.start_utc

    @property
    def duration_minutes(self) -> int:
        return int(self.duration.total_seconds() // 60)


@dataclass(frozen=True)
class CoverageGap:
    """A gap in team coverage.

    Attributes:
        start_utc: Start of the gap in UTC.
        end_utc: End of the gap in UTC.
        duration: Duration of the gap.
    """

    start_utc: datetime
    end_utc: datetime
    duration: timedelta

    @property
    def duration_minutes(self) -> int:
        return int(self.duration.total_seconds() // 60)


@dataclass
class Member:
    """A team member with timezone and working hours.

    Attributes:
        name: Human-readable name.
        timezone: IANA timezone string.
        work_start: Start of working hours as HH:MM (default "09:00").
        work_end: End of working hours as HH:MM (default "18:00").
    """

    name: str
    timezone: str
    work_start: str = "09:00"
    work_end: str = "18:00"

    def __post_init__(self):
        # Validate timezone
        parse_timezone(self.timezone)

    @property
    def _start_time(self) -> time:
        h, m = self.work_start.split(":")
        return time(int(h), int(m))

    @property
    def _end_time(self) -> time:
        h, m = self.work_end.split(":")
        return time(int(h), int(m))

    @property
    def work_window(self) -> WorkWindow:
        """Return the underlying WorkWindow for this member."""
        return WorkWindow(
            timezone=self.timezone,
            start=self._start_time,
            end=self._end_time,
            label=self.name,
        )


class Team:
    """A team of members across timezones.

    Args:
        members: List of Member instances.
    """

    def __init__(self, members: list[Member]):
        if not members:
            raise ValueError("Team must have at least one member.")
        self.members = members

    def _resolve_date(self, date: str | datetime | date_type | None) -> datetime:
        """Convert a date argument to a timezone-aware datetime."""
        if date is None:
            return datetime.now(timezone.utc)
        if isinstance(date, str):
            d = datetime.strptime(date, "%Y-%m-%d")
            return d.replace(tzinfo=timezone.utc)
        if isinstance(date, date_type) and not isinstance(date, datetime):
            return datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
        if isinstance(date, datetime):
            if date.tzinfo is None:
                return date.replace(tzinfo=timezone.utc)
            return date
        raise TypeError(f"Unsupported date type: {type(date)}")

    def find_overlaps(
        self,
        date: str | datetime | date_type | None = None,
    ) -> list[OverlapWindow]:
        """Find all overlap windows among team members for the given date.

        Computes the full-team overlap and all subsets of size >= 2.
        Returns only subsets that produce a positive overlap, sorted by
        number of members (descending) then duration (descending).
        """
        ref = self._resolve_date(date)
        member_map: dict[str, Member] = {m.name: m for m in self.members}
        windows_map: dict[str, WorkWindow] = {
            m.name: m.work_window for m in self.members
        }
        names = list(windows_map.keys())
        results: list[OverlapWindow] = []
        seen_intervals: set[tuple[str, ...]] = set()

        # Check subsets from full team down to pairs
        for size in range(len(names), 1, -1):
            for combo in combinations(names, size):
                ws = [windows_map[n] for n in combo]
                utc_ranges = [w.utc_range(ref) for w in ws]
                latest_start = max(r[0] for r in utc_ranges)
                earliest_end = min(r[1] for r in utc_ranges)
                if latest_start < earliest_end:
                    key = tuple(sorted(combo))
                    if key not in seen_intervals:
                        seen_intervals.add(key)
                        dur = earliest_end - latest_start
                        results.append(
                            OverlapWindow(
                                members=[member_map[n] for n in combo],
                                start_utc=latest_start,
                                end_utc=earliest_end,
                                duration=dur,
                            )
                        )

        # Sort: most members first, then longest duration
        results.sort(key=lambda ow: (len(ow.members), ow.duration), reverse=True)
        return results

    def best_window(
        self,
        min_members: int = 2,
        min_duration: str = "30m",
        date: str | datetime | date_type | None = None,
    ) -> BestWindowResult | None:
        """Find the best overlap window for at least *min_members* people.

        "Best" = most members, then longest duration, then earliest start.
        If *min_duration* is given (e.g. '30m', '1h'), windows shorter than
        that threshold are excluded.

        Returns None if no window meets the criteria.
        """
        min_td = _parse_duration(min_duration)
        overlaps = self.find_overlaps(date=date)

        for ow in overlaps:
            if len(ow.members) >= min_members and ow.duration >= min_td:
                return BestWindowResult(
                    start_utc=ow.start_utc,
                    end_utc=ow.end_utc,
                    members_included=ow.members,
                    has_out_of_hours=False,
                    out_of_hours_members=[],
                )

        return None

    def find_coverage_gaps(
        self,
        coverage_target: str = "24/7",
        date: str | datetime | date_type | None = None,
    ) -> list[CoverageGap]:
        """Find gaps where no team member is working.

        Args:
            coverage_target: Currently only '24/7' is supported (full-day coverage).
            date: Reference date.

        Returns:
            List of CoverageGap objects for uncovered periods.
        """
        if coverage_target != "24/7":
            raise ValueError(f"Unsupported coverage target: '{coverage_target}'. Use '24/7'.")

        ref = self._resolve_date(date)
        day_start = datetime(ref.year, ref.month, ref.day, 0, 0, tzinfo=timezone.utc)
        day_end = day_start + timedelta(hours=24)

        # Collect all UTC working ranges
        ranges: list[tuple[datetime, datetime]] = []
        for m in self.members:
            s, e = m.work_window.utc_range(ref)
            # Clamp to day boundaries
            s = max(s, day_start)
            e = min(e, day_end)
            if s < e:
                ranges.append((s, e))

        if not ranges:
            return [CoverageGap(start_utc=day_start, end_utc=day_end, duration=timedelta(hours=24))]

        # Merge overlapping ranges
        ranges.sort()
        merged: list[tuple[datetime, datetime]] = [ranges[0]]
        for s, e in ranges[1:]:
            if s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))

        # Gaps are the spaces between merged ranges and the day boundaries
        gaps: list[CoverageGap] = []
        cursor = day_start
        for s, e in merged:
            if cursor < s:
                gaps.append(CoverageGap(start_utc=cursor, end_utc=s, duration=s - cursor))
            cursor = e
        if cursor < day_end:
            gaps.append(CoverageGap(start_utc=cursor, end_utc=day_end, duration=day_end - cursor))

        return gaps
