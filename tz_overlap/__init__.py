"""tz-overlap: Find overlapping working hours across timezones."""

__version__ = "0.1.0"

from .core import (
    find_overlap,
    get_overlap_windows,
    best_meeting_times,
    WorkWindow,
    OverlapResult,
)
from .utils import parse_timezone, now_in_tz, format_time_range

__all__ = [
    "find_overlap",
    "get_overlap_windows",
    "best_meeting_times",
    "WorkWindow",
    "OverlapResult",
    "parse_timezone",
    "now_in_tz",
    "format_time_range",
]
