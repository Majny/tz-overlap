"""Tests for CLI interface."""

import json
from unittest.mock import patch

import pytest

from tz_overlap.cli import main


def test_cli_basic(capsys):
    main(["Europe/Prague", "America/New_York"])
    output = capsys.readouterr().out
    assert "Overlap" in output or "No overlapping" in output


def test_cli_json(capsys):
    main(["--json", "Europe/Prague", "America/New_York"])
    output = capsys.readouterr().out
    data = json.loads(output)
    assert "has_overlap" in data
    assert "overlap_minutes" in data


def test_cli_slots(capsys):
    main(["Europe/Prague", "America/New_York", "--slots", "30"])
    output = capsys.readouterr().out
    assert "slot" in output.lower() or "Overlap" in output


def test_cli_now(capsys):
    main(["--now", "Europe/Prague"])
    output = capsys.readouterr().out
    assert "Europe/Prague" in output


def test_cli_too_few_timezones():
    with pytest.raises(SystemExit):
        main(["Europe/Prague"])


def test_cli_invalid_timezone(capsys):
    with pytest.raises(SystemExit):
        main(["Fake/Zone", "Europe/Prague"])


def test_cli_version():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_cli_custom_hours(capsys):
    main(["Europe/Prague", "America/New_York", "--start", "08:00", "--end", "16:00"])
    output = capsys.readouterr().out
    assert "Overlap" in output or "No overlapping" in output
