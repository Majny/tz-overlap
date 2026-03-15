# tz-overlap

Find overlapping working hours across timezones. Built for distributed teams who need to coordinate across time zones without the mental math.

## Install

```bash
pip install tz-overlap
```

## Quick Start

### CLI

```bash
# Find overlap between Prague and New York
tz-overlap Europe/Prague America/New_York

# Three timezones
tz-overlap Europe/Prague America/New_York Asia/Tokyo

# Custom working hours
tz-overlap Europe/Prague America/New_York --start 08:00 --end 18:00

# Get meeting slots
tz-overlap Europe/Prague America/New_York --slots 30

# JSON output (for piping)
tz-overlap Europe/Prague America/New_York --json

# Check current time in a timezone
tz-overlap --now Asia/Tokyo
```

### Python API

```python
from tz_overlap import find_overlap, WorkWindow, get_overlap_windows

# Using WorkWindow objects (full control)
prague = WorkWindow(timezone="Europe/Prague", label="Prague HQ")
ny = WorkWindow(timezone="America/New_York", label="NYC Office")

result = find_overlap(prague, ny)
print(result.summary())
# Overlap: 2h
#   Prague HQ: 15:00–17:00
#   NYC Office: 09:00–11:00

# Quick version with just timezone strings
result = get_overlap_windows(
    ["Europe/Prague", "America/New_York", "Asia/Tokyo"],
    labels=["Prague", "NYC", "Tokyo"]
)

if result.has_overlap:
    print(f"You have {result.overlap_minutes} minutes of overlap!")
    print(result.local_times())
else:
    print("No overlap — consider async handoffs.")

# Find meeting slots
from tz_overlap import best_meeting_times

slots = best_meeting_times(prague, ny, slot_minutes=30)
for slot in slots:
    print(slot["local_times"])
```

## Features

- **IANA timezone database** — uses `zoneinfo` (Python 3.9+), always accurate
- **DST-aware** — handles daylight saving transitions correctly
- **Common aliases** — `EST`, `PST`, `CET`, `JST`, etc. are resolved automatically
- **Meeting slot finder** — break overlap into bookable slots
- **JSON output** — pipe CLI output into other tools
- **Zero dependencies** — pure Python, no external packages required

## API Reference

### `find_overlap(*windows, date=None) → OverlapResult`

Core function. Takes 2+ `WorkWindow` objects and returns the overlap.

### `get_overlap_windows(timezones, work_start, work_end, labels, date) → OverlapResult`

Convenience wrapper that takes timezone strings instead of `WorkWindow` objects.

### `best_meeting_times(*windows, date=None, slot_minutes=30) → list[dict]`

Returns bookable meeting slots within the overlap window.

### `WorkWindow(timezone, start, end, label)`

Represents one team's working hours in their timezone.

### `OverlapResult`

Result object with `.has_overlap`, `.overlap_minutes`, `.local_times()`, `.summary()`.

## Why?

78% of engineering leaders say handoff context loss is the #1 pain point in async work. The first step to fixing handoffs is knowing when your team's working hours actually overlap.

`tz-overlap` is the timezone intelligence layer for [LoopDesk](https://loopdesk.dev) — our async-first workspace for distributed engineering teams.

## License

MIT
