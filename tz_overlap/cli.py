"""Command-line interface for tz-overlap."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import time, datetime, timezone

from .core import WorkWindow, find_overlap, best_meeting_times
from .utils import parse_timezone, now_in_tz


def parse_time(s: str) -> time:
    """Parse HH:MM string to time object."""
    try:
        parts = s.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        raise argparse.ArgumentTypeError(f"Invalid time format: '{s}'. Use HH:MM (e.g. 09:00)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="tz-overlap",
        description="Find overlapping working hours across timezones.",
        epilog="Example: tz-overlap Europe/Prague America/New_York Asia/Tokyo",
    )

    parser.add_argument(
        "timezones",
        nargs="*",
        help="IANA timezone identifiers (e.g. Europe/Prague America/New_York)",
    )
    parser.add_argument(
        "--start",
        type=parse_time,
        default=time(9, 0),
        help="Work start time in HH:MM (default: 09:00)",
    )
    parser.add_argument(
        "--end",
        type=parse_time,
        default=time(17, 0),
        help="Work end time in HH:MM (default: 17:00)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )
    parser.add_argument(
        "--slots",
        type=int,
        default=0,
        metavar="MINUTES",
        help="Show meeting slots of given duration in minutes",
    )
    parser.add_argument(
        "--now",
        metavar="TZ",
        help="Show current time in the given timezone and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    args = parser.parse_args(argv)

    # --now mode: just show current time
    if args.now:
        try:
            current = now_in_tz(args.now)
            print(f"{args.now}: {current.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if len(args.timezones) < 2:
        parser.error("Need at least 2 timezones. Example: tz-overlap Europe/Prague America/New_York")

    # Build windows
    try:
        windows = [
            WorkWindow(timezone=tz, start=args.start, end=args.end)
            for tz in args.timezones
        ]
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = find_overlap(*windows)

    if args.json_output:
        data = {
            "has_overlap": result.has_overlap,
            "overlap_minutes": result.overlap_minutes,
            "overlap_start_utc": result.overlap_start_utc.isoformat() if result.overlap_start_utc else None,
            "overlap_end_utc": result.overlap_end_utc.isoformat() if result.overlap_end_utc else None,
            "local_times": result.local_times(),
        }
        if args.slots and result.has_overlap:
            data["slots"] = best_meeting_times(*windows, slot_minutes=args.slots)
        print(json.dumps(data, indent=2))
    else:
        print(result.summary())
        if args.slots and result.has_overlap:
            print(f"\nAvailable {args.slots}-minute slots:")
            slots = best_meeting_times(*windows, slot_minutes=args.slots)
            for i, slot in enumerate(slots, 1):
                parts = []
                for label, times in slot["local_times"].items():
                    parts.append(f"{label}: {times['start']}–{times['end']}")
                print(f"  {i}. {' | '.join(parts)}")


if __name__ == "__main__":
    main()
