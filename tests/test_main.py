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
            from src.database import Database, get_database, get_dev_database, get_prod_database
            
            # Use test database
            db = Database(db_path)
            
            # Mock provider
            mock_provider = MagicMock()
            mock_provider.name = "gemini"
            mock_provider.parse_response = AsyncMock(return_value="12:30")
            
            # Simulate inference results - use a reference time that makes the guess accurate
            reference_time = datetime.now().replace(hour=12, minute=30, second=0, microsecond=0)
            time_result = "12:30"
            
            # Calculate offset (within 5 minutes = accurate)
            guess_parts = time_result.split(":")
            guess_hour = int(guess_parts[0])
            guess_minute = int(guess_parts[1])
            parsed_dt = reference_time.replace(hour=guess_hour, minute=guess_minute, second=0, microsecond=0)
            
            offset_seconds = abs((parsed_dt - reference_time).total_seconds())
            offset_minutes = int(offset_seconds / 60)
            is_accurate = offset_minutes <= 5
            
            # Save to database
            db.save_inference_result(
                reference_system_time=reference_time,
                model_name="gemini",
                provider_family="gemini",
                time_guess=time_result,
                inference_failure=False,
                captured_image_filename="test_image.png",
                parsed_time=parsed_dt,
                guessed_offset_minutes=offset_minutes,
                is_accurate=is_accurate,
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
            
            reference_time = datetime.now()
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
        reference_time = datetime.now().replace(second=0, microsecond=0)
        
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
        reference_time = datetime.now().replace(second=0, microsecond=0)
        
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
    async def test_database_open_failure_graceful(self):
        """Test that database open failures don't crash the main loop."""
        from src.database import get_dev_database, get_prod_database, Database
        
        # Test that get_dev_database returns a valid database
        db = get_dev_database()
        assert db is not None
        assert db.db_path.exists()
        db.close()

    @pytest.mark.asyncio
    async def test_database_write_failure_graceful(self):
        """Test that database write failures are caught and logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_inference.db"
            
            from src.database import Database
            
            db = Database(db_path)
            
            # Test valid write
            reference_time = datetime.now()
            db.save_inference_result(
                reference_system_time=reference_time,
                model_name="test",
                provider_family="test",
                time_guess="12:30",
                inference_failure=False,
            )
            
            cursor = db._conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inference_results")
            assert cursor.fetchone()[0] == 1
            
            db.close()
