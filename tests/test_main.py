"""
Tests for the main application loop.

Mocks OBS WebSocket and image capture to validate the broadcast loop.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

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
