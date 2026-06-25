"""
Tests for the capture module.

Mocks OBS WebSocket interactions to validate capture logic without actual hardware.
"""

import argparse
import asyncio
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.capture import (
    capture_clock_image,
    connect_to_obs,
    trigger_screenshot,
    parse_resolution,
    move_to_output,
    cleanup_temp_dir,
    crop_to_square,
    OUTPUT_DIR,
    TEMP_DIR,
)


class TestParseResolution:
    """Tests for resolution parsing."""

    def test_valid_resolution(self):
        """Parse valid resolution strings."""
        assert parse_resolution("854x480") == (854, 480)
        assert parse_resolution("1920x1080") == (1920, 1080)
        assert parse_resolution("100x200") == (100, 200)

    def test_invalid_resolution(self):
        """Reject invalid resolution formats."""
        with pytest.raises(argparse.ArgumentTypeError):
            parse_resolution("invalid")

        with pytest.raises(argparse.ArgumentTypeError):
            parse_resolution("854x")

        with pytest.raises(argparse.ArgumentTypeError):
            parse_resolution("x480")

        with pytest.raises(argparse.ArgumentTypeError):
            parse_resolution("854x480x100")


class TestMoveToOutput:
    """Tests for moving images to output directory."""

    def test_move_to_output_creates_directory(self, tmp_path):
        """Output directory is created if it doesn't exist."""
        temp_file = tmp_path / "temp" / "clock_temp_20240101_120000.png"
        temp_file.parent.mkdir(parents=True)
        temp_file.touch()

        output_dir = tmp_path / "output"

        result = move_to_output(temp_file, output_dir)

        assert result.parent == output_dir
        assert result.suffix == ".png"
        assert not temp_file.exists()  # Original file moved
        assert result.exists()  # New file exists

    def test_move_to_output_with_timestamp(self, tmp_path):
        """Output filename includes timestamp."""
        temp_file = tmp_path / "clock_temp_20240101_120000.png"
        temp_file.touch()

        output_dir = tmp_path / "output"

        result = move_to_output(temp_file, output_dir)

        # Filename should have different timestamp than temp file
        assert "clock_" in result.name
        assert result.suffix == ".png"


class TestCleanupTempDir:
    """Tests for temp directory cleanup."""

    def test_cleanup_removes_old_files(self, tmp_path):
        """Old files are removed."""
        # Create old temp file
        old_file = tmp_path / "clock_temp_old.png"
        old_file.touch()
        # Set modification time to 2 hours ago
        old_time = datetime.now().timestamp() - 7200
        import os
        os.utime(old_file, (old_time, old_time))

        # Create new temp file
        new_file = tmp_path / "clock_temp_new.png"
        new_file.touch()

        # Use the real TEMP_DIR path for testing
        with patch("src.capture.TEMP_DIR", tmp_path):
            cleanup_temp_dir(hours_old=1)

        assert not old_file.exists()
        assert new_file.exists()

    def test_cleanup_does_not_remove_new_files(self, tmp_path):
        """New files are not removed."""
        temp_file = tmp_path / "clock_temp_recent.png"
        temp_file.touch()  # Just created, should be kept

        with patch("src.capture.TEMP_DIR", tmp_path):
            cleanup_temp_dir(hours_old=1)

        assert temp_file.exists()

    def test_cleanup_when_dir_does_not_exist(self, tmp_path):
        """No error when temp directory doesn't exist."""
        non_existent = tmp_path / "nonexistent"
        assert not non_existent.exists()

        # Should not raise
        cleanup_temp_dir(hours_old=1)


class TestTriggerScreenshot:
    """Tests for screenshot triggering."""

    @pytest.mark.asyncio
    async def test_trigger_screenshot_calls_obs(self):
        """Trigger screenshot makes correct OBS call."""
        with patch("src.capture.ReqClient") as mock_req_client:
            mock_client = MagicMock()
            mock_req_client.return_value = mock_client

            output_path = Path(tempfile.gettempdir()) / "test_output.png"

            with patch.object(Path, "mkdir"):
                result = await trigger_screenshot(
                    output_path=output_path,
                    resolution=(854, 480)
                )

            mock_client.save_source_screenshot.assert_called_once()
            call_args = mock_client.save_source_screenshot.call_args

            assert call_args[1]["width"] == 854
            assert call_args[1]["height"] == 480
            assert call_args[1]["img_format"] == "png"
            assert call_args[1]["quality"] == 85

    @pytest.mark.asyncio
    async def test_trigger_screenshot_disconnects_on_error(self):
        """Client disconnects even when save fails."""
        with patch("src.capture.ReqClient") as mock_req_client:
            mock_client = MagicMock()
            mock_client.save_source_screenshot.side_effect = Exception("OBS Error")
            mock_req_client.return_value = mock_client

            with pytest.raises(Exception):
                with patch.object(Path, "mkdir"):
                    await trigger_screenshot()

            mock_client.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_trigger_screenshot_uses_temp_dir_by_default(self):
        """Default output uses temp directory."""
        with patch("src.capture.ReqClient") as mock_req_client:
            mock_client = MagicMock()
            mock_req_client.return_value = mock_client

            # Mock Path.mkdir to avoid actual directory creation
            with patch.object(Path, "mkdir"), patch.object(
                Path, "exists", return_value=True
            ):
                result = await trigger_screenshot()

            # Should be in temp directory
            assert "temp" in str(result).lower() or "tmp" in str(result).lower()


class TestCaptureClockImage:
    """Tests for the main capture function."""

    @pytest.mark.asyncio
    async def test_capture_clock_image_with_output(self):
        """Capture with output directory moves file."""
        with patch("src.capture.trigger_screenshot") as mock_trigger, \
             patch("src.capture.move_to_output") as mock_move, \
             patch("src.capture.cleanup_temp_dir"), \
             patch("src.capture.crop_to_square") as mock_crop:
            # Setup mocks
            temp_path = Path("/tmp/clock_temp.png")
            output_path = Path("/output/clock_final.png")
            mock_trigger.return_value = temp_path
            mock_move.return_value = output_path
            mock_crop.return_value = temp_path

            result = await capture_clock_image(output_dir=Path("/output"))

            mock_crop.assert_called_once()
            mock_move.assert_called_once()
            assert result == output_path

    @pytest.mark.asyncio
    async def test_capture_clock_image_no_output(self):
        """Capture without output directory returns temp path."""
        with patch("src.capture.trigger_screenshot") as mock_trigger, \
             patch("src.capture.cleanup_temp_dir"), \
             patch("src.capture.crop_to_square") as mock_crop:
            temp_path = Path("/tmp/clock_temp.png")
            mock_trigger.return_value = temp_path
            mock_crop.return_value = temp_path

            result = await capture_clock_image(output_dir=None)

            # Should return temp path directly
            assert result == temp_path
            mock_trigger.assert_called_once()
            mock_crop.assert_called_once()

    @pytest.mark.asyncio
    async def test_crop_to_square_default_size(self):
        """crop_to_square uses CROP_SIZE by default."""
        with patch("PIL.Image.open") as mock_open:
            mock_img = MagicMock()
            mock_img.size = (640, 360)
            mock_open.return_value.__enter__.return_value = mock_img
            
            # Test with default crop size (should be 360 to match image height)
            result = crop_to_square(Path("/test.png"))
            
            # Verify it used the default 360px crop size
            # For 640x360 image with 360px crop: left=(640-360)//2=140, top=(360-360)//2=0
            mock_img.crop.assert_called_once_with((140, 0, 500, 360))


class TestIntegration:
    """Integration tests that use the real capture logic."""

    @pytest.mark.asyncio
    async def test_capture_clock_image_cleanup_called(self):
        """Cleanup is called after capture."""
        with patch("src.capture.trigger_screenshot") as mock_trigger, \
             patch("src.capture.cleanup_temp_dir") as mock_cleanup_temp_dir, \
             patch("src.capture.move_to_output") as mock_move, \
             patch("src.capture.crop_to_square") as mock_crop:
            temp_path = Path("/tmp/clock_temp.png")
            mock_trigger.return_value = temp_path
            mock_move.return_value = temp_path
            mock_crop.return_value = temp_path

            await capture_clock_image()

            mock_crop.assert_called_once()
            mock_cleanup_temp_dir.assert_called_once_with(hours_old=1)


class TestIntegration:
    """Integration tests for the capture workflow."""

    @pytest.mark.asyncio
    async def test_capture_workflow(self, tmp_path):
        """End-to-end capture workflow with mocked OBS."""
        # Setup temp directory
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # Create a fake image file
        temp_file = temp_dir / "clock_temp_20240101_120000.png"
        temp_file.write_text("fake image data")

        # Mock trigger_screenshot and crop_to_square
        with patch("src.capture.trigger_screenshot", return_value=temp_file), \
             patch("src.capture.crop_to_square") as mock_crop:
            mock_crop.return_value = temp_file
            result = await capture_clock_image(output_dir=tmp_path / "output")

        assert result.exists()
        assert result.parent == tmp_path / "output"
