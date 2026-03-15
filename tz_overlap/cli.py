"""Command-line interface for tz-overlap."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import time, datetime, timezone

from .core import WorkWindow, Member, Team, find_overlap, best_meeting_times
from .utils import parse_timezone, now_in_tz


def parse_time(s: str) -> time:
    """Parse HH:MM string to time object."""
    try:
        parts = s.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        raise argparse.ArgumentTypeError(f"Invalid time format: '{s}'. Use HH:MM (e.g. 09:00)")


def parse_member_string(s: str) -> Member:
    """Parse a --member string like 'Alice Europe/Prague 09:00-18:00' into a Member.

    Format: "Name Timezone [HH:MM-HH:MM]"
    Work hours are optional; defaults to 09:00-18:00.
    """
    parts = s.strip().split()
    if len(parts) < 2:
        raise argparse.ArgumentTypeError(
            f"Invalid --member format: '{s}'. "
            "Use: 'Name Timezone [HH:MM-HH:MM]'"
        )
    name = parts[0]
    tz = parts[1]
    work_start = "09:00"
    work_end = "18:00"
    if len(parts) >= 3:
        hours_match = re.fullmatch(r"(\d{2}:\d{2})-(\d{2}:\d{2})", parts[2])
        if not hours_match:
            raise argparse.ArgumentTypeError(
                f"Invalid work hours: '{parts[2]}'. Use HH:MM-HH:MM (e.g. 09:00-18:00)"
            )
        work_start = hours_match.group(1)
        work_end = hours_match.group(2)
    return Member(name=name, timezone=tz, work_start=work_start, work_end=work_end)


def load_team_file(path: str) -> list[Member]:
    """Load members from a YAML team file.

    Expected format:
        members:
          - name: Alice
            timezone: Europe/Prague
            work_hours: "09:00-18:00"   # optional
    """
    try:
        import yaml
    except ImportError:
        print(
            "Error: PyYAML is required for --team-file. "
            "Install with: pip install tz-overlap[yaml]",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(path) as f:
        data = yaml.safe_load(f)

    if not data or "members" not in data:
        print(f"Error: team file must contain a 'members' list.", file=sys.stderr)
        sys.exit(1)

    members = []
    for entry in data["members"]:
        name = entry.get("name")
        tz = entry.get("timezone")
        if not name or not tz:
            print(f"Error: each member needs 'name' and 'timezone'.", file=sys.stderr)
            sys.exit(1)
        work_start = "09:00"
        work_end = "18:00"
        if "work_hours" in entry:
            m = re.fullmatch(r"(\d{2}:\d{2})-(\d{2}:\d{2})", entry["work_hours"])
            if not m:
                print(
                    f"Error: invalid work_hours for {name}: '{entry['work_hours']}'",
                    file=sys.stderr,
                )
                sys.exit(1)
            work_start = m.group(1)
            work_end = m.group(2)
        members.append(Member(name=name, timezone=tz, work_start=work_start, work_end=work_end))

    return members


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
        "--member",
        action="append",
        dest="members",
        metavar='"Name TZ [HH:MM-HH:MM]"',
        help='Named member: "Alice Europe/Prague 09:00-18:00" (work hours optional)',
    )
    parser.add_argument(
        "--team-file",
        metavar="PATH",
        help="YAML file with team member definitions",
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

    # Determine if using Team/Member mode or legacy positional mode
    team_members: list[Member] = []

    if args.team_file:
        try:
            team_members.extend(load_team_file(args.team_file))
        except (FileNotFoundError, OSError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    if args.members:
        for ms in args.members:
            try:
                team_members.append(parse_member_string(ms))
            except (argparse.ArgumentTypeError, ValueError) as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

    if team_members:
        # Team/Member mode
        if len(team_members) < 2:
            parser.error("Need at least 2 members.")
        team = Team(team_members)
        windows = [m.work_window for m in team_members]
        result = find_overlap(*windows)

        if args.json_output:
            data = {
                "has_overlap": result.has_overlap,
                "overlap_minutes": result.overlap_minutes,
                "overlap_start_utc": (
                    result.overlap_start_utc.isoformat() if result.overlap_start_utc else None
                ),
                "overlap_end_utc": (
                    result.overlap_end_utc.isoformat() if result.overlap_end_utc else None
                ),
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
        return

    # Legacy positional timezone mode
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
