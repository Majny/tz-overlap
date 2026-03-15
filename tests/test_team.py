"""Tests for Team / Member API (Sprint 2)."""

from datetime import datetime, date, timedelta, timezone

import pytest

from tz_overlap import Member, Team, OverlapWindow, BestWindowResult, CoverageGap


# ── Reference date: 2026-03-17 (a Tuesday, US in EDT, Europe still CET) ──
REF_DATE_STR = "2026-03-17"
REF_DATE_DT = datetime(2026, 3, 17, tzinfo=timezone.utc)


# ===================================================================
# 1. Member creation
# ===================================================================

class TestMemberCreation:
    def test_default_work_hours(self):
        m = Member(name="Alice", timezone="Europe/Prague")
        assert m.work_start == "09:00"
        assert m.work_end == "18:00"

    def test_custom_work_hours(self):
        m = Member(name="Bob", timezone="America/New_York", work_start="08:00", work_end="16:00")
        assert m.work_start == "08:00"
        assert m.work_end == "16:00"

    def test_invalid_timezone_raises(self):
        with pytest.raises(ValueError, match="Unknown timezone"):
            Member(name="Ghost", timezone="Fake/Nowhere")

    def test_work_window_property(self):
        m = Member(name="Carol", timezone="Asia/Kolkata", work_start="10:00", work_end="19:00")
        ww = m.work_window
        assert ww.timezone == "Asia/Kolkata"
        assert ww.label == "Carol"
        from datetime import time
        assert ww.start == time(10, 0)
        assert ww.end == time(19, 0)


# ===================================================================
# 2. Team creation
# ===================================================================

class TestTeamCreation:
    def test_empty_team_raises(self):
        with pytest.raises(ValueError, match="at least one member"):
            Team([])

    def test_single_member_team(self):
        team = Team([Member(name="Solo", timezone="UTC")])
        assert len(team.members) == 1


# ===================================================================
# 3. Team.find_overlaps()
# ===================================================================

class TestFindOverlaps:
    def test_prague_newyork_overlap(self):
        """Prague CET (UTC+1) 09-18 and NY EDT (UTC-4) 09-18.

        Prague in UTC: 08:00-17:00
        NY in UTC:     13:00-22:00
        Overlap:       13:00-17:00 = 4 hours = 240 min
        """
        prague = Member(name="Prague", timezone="Europe/Prague")
        ny = Member(name="NewYork", timezone="America/New_York")
        team = Team([prague, ny])
        overlaps = team.find_overlaps(date=REF_DATE_STR)

        assert len(overlaps) >= 1
        full = overlaps[0]  # Sorted by member count desc
        assert len(full.members) == 2
        assert full.start_utc.hour == 13
        assert full.end_utc.hour == 17
        assert full.duration_minutes == 240

    def test_four_members_full_overlap(self):
        """Prague, Kolkata, Lisbon, New York — check full team overlap exists.

        Prague CET (UTC+1):   09-18 -> UTC 08-17
        Kolkata IST (UTC+5:30): 09-18 -> UTC 03:30-12:30
        Lisbon WET (UTC+0):   09-18 -> UTC 09-18
        NY EDT (UTC-4):       09-18 -> UTC 13-22

        Full-team overlap: UTC 13:00-12:30 — wait, 13>12:30, so no full overlap.
        Let's verify: Kolkata ends at 12:30, NY starts at 13:00 — no 4-way overlap.
        But 3-way overlaps should exist: Prague+Lisbon+NY = 13:00-17:00.
        """
        prague = Member(name="Prague", timezone="Europe/Prague")
        kolkata = Member(name="Kolkata", timezone="Asia/Kolkata")
        lisbon = Member(name="Lisbon", timezone="Europe/Lisbon")
        ny = Member(name="NewYork", timezone="America/New_York")
        team = Team([prague, kolkata, lisbon, ny])
        overlaps = team.find_overlaps(date=REF_DATE_STR)

        assert len(overlaps) > 0
        # Check that at least a 3-member overlap exists (Prague+Lisbon+NY)
        three_plus = [o for o in overlaps if len(o.members) >= 3]
        assert len(three_plus) >= 1
        # All overlaps should have positive duration
        for o in overlaps:
            assert o.duration_minutes > 0

    def test_date_as_string(self):
        team = Team([
            Member(name="A", timezone="Europe/Prague"),
            Member(name="B", timezone="America/New_York"),
        ])
        overlaps = team.find_overlaps(date="2026-03-17")
        assert len(overlaps) >= 1

    def test_date_as_datetime(self):
        team = Team([
            Member(name="A", timezone="Europe/Prague"),
            Member(name="B", timezone="America/New_York"),
        ])
        overlaps = team.find_overlaps(date=datetime(2026, 3, 17, tzinfo=timezone.utc))
        assert len(overlaps) >= 1

    def test_date_as_none_uses_today(self):
        team = Team([
            Member(name="A", timezone="Europe/Prague"),
            Member(name="B", timezone="America/New_York"),
        ])
        overlaps = team.find_overlaps(date=None)
        # Should not raise; result depends on today but should still find overlap
        assert isinstance(overlaps, list)

    def test_no_overlap_at_all(self):
        """Tokyo 09:00-12:00 and LA 09:00-12:00 — no overlap.

        Tokyo (UTC+9): 09-12 -> UTC 00-03
        LA EDT? No, LA is America/Los_Angeles.
        On 2026-03-17 LA is PDT (UTC-7): 09-12 -> UTC 16-19
        No overlap between 00-03 and 16-19.
        """
        tokyo = Member(name="Tokyo", timezone="Asia/Tokyo",
                        work_start="09:00", work_end="12:00")
        la = Member(name="LA", timezone="America/Los_Angeles",
                     work_start="09:00", work_end="12:00")
        team = Team([tokyo, la])
        overlaps = team.find_overlaps(date=REF_DATE_STR)
        assert len(overlaps) == 0


# ===================================================================
# 4. Team.best_window()
# ===================================================================

class TestBestWindow:
    def test_min_members_3(self):
        prague = Member(name="Prague", timezone="Europe/Prague")
        lisbon = Member(name="Lisbon", timezone="Europe/Lisbon")
        ny = Member(name="NewYork", timezone="America/New_York")
        team = Team([prague, lisbon, ny])

        result = team.best_window(min_members=3, date=REF_DATE_STR)
        assert result is not None
        assert len(result.members_included) >= 3

    def test_min_duration_1h(self):
        prague = Member(name="Prague", timezone="Europe/Prague")
        ny = Member(name="NewYork", timezone="America/New_York")
        team = Team([prague, ny])

        result = team.best_window(min_duration="1h", date=REF_DATE_STR)
        assert result is not None
        assert result.duration_minutes >= 60

    def test_returns_none_when_no_window(self):
        """Require 2 members but they have no overlap -> None."""
        tokyo = Member(name="Tokyo", timezone="Asia/Tokyo",
                        work_start="09:00", work_end="12:00")
        la = Member(name="LA", timezone="America/Los_Angeles",
                     work_start="09:00", work_end="12:00")
        team = Team([tokyo, la])

        result = team.best_window(min_members=2, date=REF_DATE_STR)
        assert result is None

    def test_returns_none_when_duration_too_long(self):
        """Prague+NY overlap 4h, but require 10h -> None."""
        prague = Member(name="Prague", timezone="Europe/Prague")
        ny = Member(name="NewYork", timezone="America/New_York")
        team = Team([prague, ny])

        result = team.best_window(min_duration="10h", date=REF_DATE_STR)
        assert result is None


# ===================================================================
# 5. Team.find_coverage_gaps()
# ===================================================================

class TestCoverageGaps:
    def test_24h_coverage_no_gaps(self):
        """Members spanning enough timezones to cover 24h."""
        # Cover the full day with extended shifts
        m1 = Member(name="A", timezone="UTC", work_start="00:00", work_end="08:00")
        m2 = Member(name="B", timezone="UTC", work_start="08:00", work_end="16:00")
        m3 = Member(name="C", timezone="UTC", work_start="16:00", work_end="23:59")
        team = Team([m1, m2, m3])
        gaps = team.find_coverage_gaps(date=REF_DATE_STR)
        # Gaps should be minimal (at most 1 minute from 23:59-00:00)
        total_gap = sum(g.duration_minutes for g in gaps)
        assert total_gap <= 1

    def test_team_with_gaps(self):
        """Single member in UTC 09-17 leaves 16 hours uncovered."""
        m = Member(name="Solo", timezone="UTC", work_start="09:00", work_end="17:00")
        team = Team([m])
        gaps = team.find_coverage_gaps(date=REF_DATE_STR)
        assert len(gaps) >= 1
        total_gap = sum(g.duration_minutes for g in gaps)
        # 24h - 8h = 16h = 960 min
        assert total_gap == 960
        # Verify gap times
        for gap in gaps:
            assert gap.start_utc < gap.end_utc
            assert gap.duration_minutes > 0

    def test_invalid_coverage_target_raises(self):
        m = Member(name="A", timezone="UTC")
        team = Team([m])
        with pytest.raises(ValueError, match="Unsupported coverage target"):
            team.find_coverage_gaps(coverage_target="business_hours")

    def test_gap_has_correct_utc_times(self):
        """UTC member 10:00-14:00 -> gaps 00:00-10:00 and 14:00-24:00."""
        m = Member(name="A", timezone="UTC", work_start="10:00", work_end="14:00")
        team = Team([m])
        gaps = team.find_coverage_gaps(date=REF_DATE_STR)
        assert len(gaps) == 2
        # First gap: 00:00 - 10:00
        assert gaps[0].start_utc.hour == 0
        assert gaps[0].end_utc.hour == 10
        assert gaps[0].duration_minutes == 600
        # Second gap: 14:00 - 24:00
        assert gaps[1].start_utc.hour == 14
        assert gaps[1].duration_minutes == 600


# ===================================================================
# 6. OverlapWindow.member_names
# ===================================================================

class TestOverlapWindowMemberNames:
    def test_returns_list_of_strings(self):
        prague = Member(name="Prague", timezone="Europe/Prague")
        ny = Member(name="NewYork", timezone="America/New_York")
        team = Team([prague, ny])
        overlaps = team.find_overlaps(date=REF_DATE_STR)
        assert len(overlaps) >= 1
        names = overlaps[0].member_names
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
        assert set(names) == {"Prague", "NewYork"}


# ===================================================================
# 7. OverlapWindow.duration_minutes
# ===================================================================

class TestOverlapWindowDurationMinutes:
    def test_returns_int(self):
        prague = Member(name="Prague", timezone="Europe/Prague")
        ny = Member(name="NewYork", timezone="America/New_York")
        team = Team([prague, ny])
        overlaps = team.find_overlaps(date=REF_DATE_STR)
        assert len(overlaps) >= 1
        dm = overlaps[0].duration_minutes
        assert isinstance(dm, int)
        assert dm > 0
