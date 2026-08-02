"""
Tests for the time offset calculation helper functions.

These tests use parse_time() to get datetime objects, then extract
hours/minutes to test calculate_time_offset_minutes() with realistic data.
"""

import pytest
from datetime import datetime, timedelta
import zoneinfo

# Import helper functions
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTimeOffsetWithParseTime:
    """Tests using parse_time() + calculate_time_offset_minutes() together."""

    def test_parse_time_and_offset_same_time(self):
        """Test when reference and guess are the same time using parse_time."""
        from scripts.record_inference import parse_time
        from main import calculate_time_offset_minutes
        reference = parse_time("12:00")
        guess = parse_time("12:00", reference)
        offset = calculate_time_offset_minutes(
            reference.hour, reference.minute,
            guess.hour, guess.minute
        )
        assert offset == 0

    def test_parse_time_and_offset_twelve_hours_apart(self):
        """Test when diff is 12 hours - should return 720, not 0."""
        from scripts.record_inference import parse_time
        from main import calculate_time_offset_minutes
        reference = parse_time("06:00")
        guess = parse_time("18:00", reference)
        offset = calculate_time_offset_minutes(
            reference.hour, reference.minute,
            guess.hour, guess.minute
        )
        assert offset == 720

    def test_parse_time_and_offset_one_hour_behind(self):
        """Test when guess is 1 hour behind reference."""
        from scripts.record_inference import parse_time
        from main import calculate_time_offset_minutes
        reference = parse_time("06:00")
        guess = parse_time("05:00", reference)
        offset = calculate_time_offset_minutes(
            reference.hour, reference.minute,
            guess.hour, guess.minute
        )
        assert offset == 60

    def test_parse_time_and_offset_one_hour_ahead(self):
        """Test when guess is 1 hour ahead of reference."""
        from scripts.record_inference import parse_time
        from main import calculate_time_offset_minutes
        reference = parse_time("06:00")
        guess = parse_time("07:00", reference)
        offset = calculate_time_offset_minutes(
            reference.hour, reference.minute,
            guess.hour, guess.minute
        )
        assert offset == 60

    def test_parse_time_and_offset_cross_midnight_previous_day(self):
        """Test when guess is on previous day (wrap-around)."""
        from scripts.record_inference import parse_time
        from main import calculate_time_offset_minutes
        # Reference: 00:05, Guess: 23:55 (10 minutes before next day = 10 min offset)
        reference = parse_time("00:05")
        guess = parse_time("23:55", reference)
        offset = calculate_time_offset_minutes(
            reference.hour, reference.minute,
            guess.hour, guess.minute
        )
        assert offset == 10

    def test_parse_time_and_offset_cross_midnight_next_day(self):
        """Test when guess is on next day (wrap-around)."""
        from scripts.record_inference import parse_time
        from main import calculate_time_offset_minutes
        # Reference: 23:55, Guess: 00:10 (15 minutes after midnight = 15 min offset)
        reference = parse_time("23:55")
        guess = parse_time("00:10", reference)
        offset = calculate_time_offset_minutes(
            reference.hour, reference.minute,
            guess.hour, guess.minute
        )
        assert offset == 15

    def test_parse_time_and_offset_with_timezone(self):
        """Test that parse_time uses PST timezone correctly."""
        from scripts.record_inference import parse_time
        from main import calculate_time_offset_minutes
        reference = parse_time("07:01")
        guess = parse_time("12:00", reference)
        # 12:00 - 07:01 = 4 hours 59 minutes = 299 minutes
        offset = calculate_time_offset_minutes(
            reference.hour, reference.minute,
            guess.hour, guess.minute
        )
        assert offset == 299

    def test_parse_time_and_offset_midnight_boundary(self):
        """Test offset calculation around midnight boundary."""
        from scripts.record_inference import parse_time
        from main import calculate_time_offset_minutes
        # Reference: 23:55, Guess: 00:05 (10 minutes across midnight)
        reference = parse_time("23:55")
        guess = parse_time("00:05", reference)
        offset = calculate_time_offset_minutes(
            reference.hour, reference.minute,
            guess.hour, guess.minute
        )
        assert offset == 10


class TestTimeOffsetCalculation:
    """Tests for calculate_time_offset_minutes helper function with raw hours/minutes."""

    def test_same_time_offset_zero(self):
        """Test when reference and guess are the same time."""
        from main import calculate_time_offset_minutes
        offset = calculate_time_offset_minutes(12, 0, 12, 0)
        assert offset == 0

    def test_twelve_hours_apart(self):
        """Test when diff is 12 hours - should return 720, not 0."""
        from main import calculate_time_offset_minutes
        # Reference: 06:00, Guess: 18:00 (12 hours apart)
        offset = calculate_time_offset_minutes(6, 0, 18, 0)
        assert offset == 720

    def test_one_hour_behind(self):
        """Test when guess is 1 hour behind reference."""
        from main import calculate_time_offset_minutes
        # Reference: 06:00, Guess: 05:00
        offset = calculate_time_offset_minutes(6, 0, 5, 0)
        assert offset == 60

    def test_one_hour_ahead(self):
        """Test when guess is 1 hour ahead of reference."""
        from main import calculate_time_offset_minutes
        # Reference: 06:00, Guess: 07:00
        offset = calculate_time_offset_minutes(6, 0, 7, 0)
        assert offset == 60

    def test_cross_midnight_previous_day(self):
        """Test when guess is on previous day (wrap-around)."""
        from main import calculate_time_offset_minutes
        # Reference: 00:05, Guess: 23:55 (10 minutes before next day = 10 min offset)
        offset = calculate_time_offset_minutes(0, 5, 23, 55)
        assert offset == 10

    def test_cross_midnight_next_day(self):
        """Test when guess is on next day (wrap-around)."""
        from main import calculate_time_offset_minutes
        # Reference: 23:55, Guess: 00:10 (15 minutes after midnight = 15 min offset)
        offset = calculate_time_offset_minutes(23, 55, 0, 10)
        assert offset == 15

    def test_offset_is_never_negative(self):
        """Test that offset is always non-negative."""
        from main import calculate_time_offset_minutes
        test_cases = [
            (0, 0, 23, 59),
            (23, 59, 0, 0),
            (6, 0, 18, 0),
            (18, 0, 6, 0),
        ]
        for ref_h, ref_m, guess_h, guess_m in test_cases:
            offset = calculate_time_offset_minutes(ref_h, ref_m, guess_h, guess_m)
            assert offset >= 0, f"Offset should be non-negative for {ref_h:02d}:{ref_m:02d} -> {guess_h:02d}:{guess_m:02d}"

    def test_offset_is_never_more_than_12_hours(self):
        """Test that offset is never more than 720 minutes (12 hours)."""
        from main import calculate_time_offset_minutes
        test_cases = [
            (0, 0, 12, 0),
            (12, 0, 0, 0),
            (3, 0, 15, 0),
            (15, 0, 3, 0),
        ]
        for ref_h, ref_m, guess_h, guess_m in test_cases:
            offset = calculate_time_offset_minutes(ref_h, ref_m, guess_h, guess_m)
            assert offset <= 720, f"Offset should be <= 720 for {ref_h:02d}:{ref_m:02d} -> {guess_h:02d}:{guess_m:02d}"


class TestGetParsedDatetimeForGuess:
    """Tests for get_parsed_datetime_for_guess helper function."""

    def test_same_day(self):
        """Test when guess is on the same day."""
        from main import get_parsed_datetime_for_guess
        reference_time = datetime(2026, 8, 1, 12, 0, 0)
        parsed_dt = get_parsed_datetime_for_guess(reference_time, 12, 30)
        assert parsed_dt == datetime(2026, 8, 1, 12, 30, 0)

    def test_previous_day(self):
        """Test when guess is on previous day (wrap-around)."""
        from main import get_parsed_datetime_for_guess
        reference_time = datetime(2026, 8, 1, 0, 10, 0)
        parsed_dt = get_parsed_datetime_for_guess(reference_time, 23, 50)
        assert parsed_dt == datetime(2026, 7, 31, 23, 50, 0)

    def test_next_day(self):
        """Test when guess is on next day (wrap-around)."""
        from main import get_parsed_datetime_for_guess
        reference_time = datetime(2026, 8, 1, 23, 50, 0)
        parsed_dt = get_parsed_datetime_for_guess(reference_time, 0, 10)
        assert parsed_dt == datetime(2026, 8, 2, 0, 10, 0)

    def test_timezone_aware_preserved(self):
        """Test that timezone info is preserved."""
        from main import get_parsed_datetime_for_guess
        pst = zoneinfo.ZoneInfo("America/Los_Angeles")
        reference_time = datetime(2026, 8, 1, 12, 0, 0, tzinfo=pst)
        parsed_dt = get_parsed_datetime_for_guess(reference_time, 12, 30)
        assert parsed_dt.tzinfo == pst
        assert parsed_dt == datetime(2026, 8, 1, 12, 30, 0, tzinfo=pst)
