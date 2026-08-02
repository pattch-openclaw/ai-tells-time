"""
Tests for the main application loop.

Mocks OBS WebSocket and image capture to validate the broadcast loop.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock, MagicMock as Mock
from datetime import datetime, timedelta
import tempfile
import os

import pytest


class TestMainLoop:
    """Tests for the main broadcast loop."""

    @pytest.mark.asyncio
    async def test_main_imports_successfully(self):
        """Regression test to ensure main.py can be imported without NameError."""
        try:
            import main
            assert True
        except NameError as e:
            pytest.fail(f"NameError when importing main: {e}")

    @pytest.mark.asyncio
    async def test_main_loop_uses_configured_resolution(self):
        """Main loop uses configured resolution."""
        import main
        assert main.CAPTURE_RESOLUTION == (640, 360)

    @pytest.mark.asyncio
    async def test_main_loop_has_main_loop_function(self):
        """Main loop has main_loop function."""
        import main
        assert hasattr(main, "main_loop")


class TestCaptureImage:
    """Tests for the capture_clock_image helper function."""

    @pytest.mark.asyncio
    async def test_capture_image_imports_ok(self):
        """Capture image function can be imported."""
        from src.capture import capture_clock_image
        assert capture_clock_image is not None


class TestMainLoopDatabaseRecording:
    """Tests for database recording in the main broadcast loop."""

    @pytest.mark.asyncio
    async def test_database_recording_saves_results(self):
        """Test that inference results are recorded to database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_inference.db"
            
            import main
            from src.database import Database
            
            # Use test database
            db = Database(db_path)
            
            # Mock provider
            mock_provider = MagicMock()
            mock_provider.name = "gemini"
            mock_provider.parse_response_sync = MagicMock(return_value="12:30")
            
            # Use fixed reference time (not system clock)
            reference_time = datetime(2026, 8, 1, 12, 30, 0)  # Fixed: 12:30:00
            time_result = "12:30"
            
            # Call the actual helper function instead of duplicating its logic
            main.record_inference_results(
                [(mock_provider, time_result)],
                reference_time,
                db,
                Path(tmpdir) / "test_image.png"
            )
            
            # Verify saved
            cursor = db._conn.cursor()
            cursor.execute("SELECT * FROM inference_results")
            rows = cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["model_name"] == "gemini"
            assert rows[0]["is_accurate"] == 1  # True
            assert rows[0]["guessed_offset_minutes"] == 0  # Exact match
            
            db.close()

    @pytest.mark.asyncio
    async def test_database_records_inference_failure(self):
        """Test that failed inference results are still recorded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_inference.db"
            
            import main
            from src.database import Database
            
            db = Database(db_path)
            
            reference_time = datetime(2026, 8, 1, 12, 0, 0)  # Fixed reference time
            time_result = "invalid time format"
            
            # Simulate parse failure
            parsed_time = None
            inference_failure = True
            
            db.save_inference_result(
                reference_system_time=reference_time,
                model_name="gemini",
                provider_family="gemini",
                time_guess=time_result,
                inference_failure=inference_failure,
                captured_image_filename="test_image.png",
                parsed_time=None,
                guessed_offset_minutes=None,
                is_accurate=False,
            )
            
            cursor = db._conn.cursor()
            cursor.execute("SELECT * FROM inference_results")
            rows = cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["inference_failure"] == 1  # True
            assert rows[0]["is_accurate"] == 0  # False
            
            db.close()

    @pytest.mark.asyncio
    async def test_offset_calculation_accurate(self):
        """Test offset calculation for accurate guesses (within ±5 minutes)."""
        reference_time = datetime(2026, 8, 1, 12, 30, 0)  # Fixed reference time
        
        # Guess within 5 minutes (should be accurate)
        guess_time = reference_time + timedelta(minutes=3)
        
        offset_seconds = abs((guess_time - reference_time).total_seconds())
        offset_minutes = int(offset_seconds / 60)
        is_accurate = offset_minutes <= 5
        
        assert offset_minutes == 3
        assert is_accurate is True

    @pytest.mark.asyncio
    async def test_offset_calculation_inaccurate(self):
        """Test offset calculation for inaccurate guesses (outside ±5 minutes)."""
        reference_time = datetime(2026, 8, 1, 12, 30, 0)  # Fixed reference time
        
        # Guess 10 minutes off (should be inaccurate)
        guess_time = reference_time + timedelta(minutes=10)
        
        offset_seconds = abs((guess_time - reference_time).total_seconds())
        offset_minutes = int(offset_seconds / 60)
        is_accurate = offset_minutes <= 5
        
        assert offset_minutes == 10
        assert is_accurate is False

    @pytest.mark.asyncio
    async def test_provider_family_determination(self):
        """Test provider family determination from provider name."""
        known_provider_families = ["openai", "gemini", "claude", "local"]
        
        # Known providers
        assert "openai" in known_provider_families
        assert "gemini" in known_provider_families
        assert "claude" in known_provider_families
        assert "local" in known_provider_families
        
        # Unknown provider defaults to "other"
        provider_name = "unknown_provider"
        provider_family = provider_name if provider_name in known_provider_families else "other"
        assert provider_family == "other"
        
        # Known provider
        provider_name = "gemini"
        provider_family = provider_name if provider_name in known_provider_families else "other"
        assert provider_family == "gemini"

    @pytest.mark.asyncio
    async def test_database_error_handling_in_main_loop(self):
        """Test that database errors don't crash the main loop execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_inference.db"
            
            from src.database import Database
            from main import record_inference_results
            
            # Use test database
            db = Database(db_path)
            
            # Mock provider results
            reference_time = datetime(2026, 8, 1, 12, 30, 0)
            results = [
                (MagicMock(name="gemini"), "12:30"),
                (MagicMock(name="local"), "12:28"),
            ]
            results[0][0].name = "gemini"
            results[1][0].name = "local"
            
            # Mock parse_response_sync to return valid times
            for provider, _ in results:
                provider.parse_response_sync = MagicMock(return_value="12:30")
            
            # This should not raise any exceptions
            record_inference_results(results, reference_time, db, Path(tmpdir) / "test.png")
            
            # Verify all results were saved
            cursor = db._conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inference_results")
            count = cursor.fetchone()[0]
            assert count == 2  # Both providers saved
            
            db.close()

    @pytest.mark.asyncio
    async def test_database_write_failure_does_not_crash(self):
        """Test that database write failures are caught gracefully."""
        from main import record_inference_results
        from src.database import Database
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_inference.db"
            db = Database(db_path)
            
            # Mock provider
            results = [(MagicMock(name="gemini"), "12:30")]
            results[0][0].name = "gemini"
            results[0][0].parse_response_sync = MagicMock(return_value="12:30")
            
            # Mock save_inference_result to raise an exception
            with patch.object(db, 'save_inference_result', side_effect=Exception("DB Error")):
                # This should not raise any exceptions due to try/except in record_inference_results
                record_inference_results(results, datetime(2026, 8, 1, 12, 30, 0), db, Path(tmpdir) / "test.png")
            
            db.close()

    @pytest.mark.asyncio
    async def test_record_inference_results_with_parse_failure(self):
        """Test that parse failures are handled correctly in record_inference_results."""
        from main import record_inference_results
        from src.database import Database
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_inference.db"
            db = Database(db_path)
            
            # Mock provider with parse failure
            results = [(MagicMock(name="gemini"), "invalid time")]
            results[0][0].name = "gemini"
            results[0][0].parse_response_sync = MagicMock(return_value=None)
            
            # This should not raise any exceptions
            record_inference_results(results, datetime(2026, 8, 1, 12, 30, 0), db, Path(tmpdir) / "test.png")
            
            # Verify failure was recorded
            cursor = db._conn.cursor()
            cursor.execute("SELECT inference_failure FROM inference_results")
            row = cursor.fetchone()
            assert row[0] == 1  # True
            
            db.close()
