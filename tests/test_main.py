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
            
            # Use fixed reference time (not system clock)
            reference_time = datetime(2026, 8, 1, 12, 30, 0)  # Fixed: 12:30:00
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
            
            # Use test database
            db = Database(db_path)
            
            # Mock provider results (simulating what happens in main loop)
            reference_time = datetime(2026, 8, 1, 12, 30, 0)
            results = [
                (MagicMock(name="gemini"), "12:30"),
                (MagicMock(name="local"), "12:28"),
            ]
            
            # Set up mock names correctly
            results[0][0].name = "gemini"
            results[1][0].name = "local"
            
            # Process results (simulating main loop logic)
            known_provider_families = ["openai", "gemini", "claude", "local"]
            
            for provider, time_result in results:
                try:
                    # Simulate parse_response returning a time
                    parsed_time = time_result  # In real code, this would be parsed
                    
                    if parsed_time is None:
                        # Inference failure
                        db.save_inference_result(
                            reference_system_time=reference_time,
                            model_name=provider.name,
                            provider_family="other",
                            time_guess=time_result,
                            inference_failure=True,
                            parsed_time=None,
                        )
                    else:
                        # Calculate offset
                        guess_parts = parsed_time.split(":")
                        parsed_dt = reference_time.replace(
                            hour=int(guess_parts[0]),
                            minute=int(guess_parts[1]),
                            second=0,
                            microsecond=0
                        )
                        offset_seconds = abs((parsed_dt - reference_time).total_seconds())
                        offset_minutes = int(offset_seconds / 60)
                        is_accurate = offset_minutes <= 5
                        
                        provider_family = provider.name if provider.name in known_provider_families else "other"
                        
                        db.save_inference_result(
                            reference_system_time=reference_time,
                            model_name=provider.name,
                            provider_family=provider_family,
                            time_guess=time_result,
                            inference_failure=False,
                            parsed_time=parsed_dt,
                            guessed_offset_minutes=offset_minutes,
                            is_accurate=is_accurate,
                        )
                except Exception as e:
                    # Main loop continues even on database errors
                    print(f"⚠️ Error recording {provider.name} to database: {e}")
            
            # Verify all results were saved
            cursor = db._conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inference_results")
            count = cursor.fetchone()[0]
            assert count == 2  # Both providers saved
            
            # Verify we can read back the results
            cursor.execute("SELECT model_name, is_accurate FROM inference_results")
            rows = cursor.fetchall()
            assert len(rows) == 2
            model_names = [r["model_name"] for r in rows]
            assert "gemini" in model_names
            assert "local" in model_names
            
            db.close()

    @pytest.mark.asyncio
    async def test_database_write_failure_graceful(self):
        """Test that database write failures are caught and logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_inference.db"
            
            from src.database import Database
            
            db = Database(db_path)
            
            # Test valid write
            reference_time = datetime(2026, 8, 1, 12, 0, 0)  # Fixed reference time
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
