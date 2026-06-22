#!/usr/bin/env python3
"""
Clock Image Capture Module

Captures screenshots from OBS WebSocket, manages temp files, and provides
downscaled images for AI analysis.
"""

import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from obsws_python import ReqClient

# Load environment variables from ~/.config/ai-tells-time/.env
config_path = Path.home() / ".config" / "ai-tells-time" / ".env"
if config_path.exists():
    load_dotenv(config_path)
else:
    # Fallback to project directory for local testing
    load_dotenv()

# Configuration
OBS_SOURCE_NAME = "Clock_Camera"
OBS_HOST = os.environ.get("OBS_WEBSOCKET_HOST", "localhost")
OBS_PORT = int(os.environ.get("OBS_WEBSOCKET_PORT", 4455))
OBS_PASSWORD = os.environ.get("OBS_WEBSOCKET_PASSWORD", "")

# OBS default screenshot directory (macOS) - kept for reference but not used with new API
# OBS_SCREENSHOT_DIR = Path.home() / "Pictures" / "OBS"

# Project temp directory for processed images
TEMP_DIR = Path(tempfile.gettempdir()) / "ai-tells-time"


async def connect_to_obs() -> ReqClient:
    """Establish connection to OBS WebSocket server."""
    ws = ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    return ws


async def trigger_screenshot(source_name: str = OBS_SOURCE_NAME) -> Path:
    """
    Trigger a screenshot capture from OBS and return the path to the captured file.
    
    Uses the new save_source_screenshot API which saves directly to a file path.
    """
    ws = ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    try:
        # Create a temp file path for the screenshot
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        temp_path = TEMP_DIR / f"clock_temp_{timestamp}.png"
        
        # Save screenshot directly to temp path
        ws.save_source_screenshot(
            name=source_name,
            img_format="png",
            file_path=str(temp_path),
            width=854,  # 480p
            height=480,
            quality=85
        )
        
        return temp_path
    finally:
        ws.disconnect()


def cleanup_temp_dir(hours_old: int = 1) -> None:
    """
    Remove temp files older than specified hours.
    
    This prevents accumulation of old screenshots.
    """
    if not TEMP_DIR.exists():
        return
    
    now = datetime.now()
    for png_file in TEMP_DIR.glob("*.png"):
        file_time = datetime.fromtimestamp(png_file.stat().st_mtime)
        age_hours = (now - file_time).total_seconds() / 3600
        if age_hours > hours_old:
            png_file.unlink()
            print(f"Cleaned up old screenshot: {png_file}")


async def capture_clock_image() -> Path:
    """
    Main entry point for clock image capture.
    
    Returns the path to the captured image in the temp directory.
    """
    # Trigger screenshot in OBS (saves directly to temp dir with new API)
    temp_path = await trigger_screenshot()
    print(f"Captured from OBS: {temp_path}")
    
    # Optional: cleanup old files
    cleanup_temp_dir(hours_old=1)
    
    return temp_path


if __name__ == "__main__":
    # Test the capture workflow
    import sys
    try:
        import asyncio
        image_path = asyncio.run(capture_clock_image())
        print(f"Final image ready: {image_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    """Entry point for the CLI command."""
    asyncio.run(capture_clock_image())
