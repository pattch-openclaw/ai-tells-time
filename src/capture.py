#!/usr/bin/env python3
"""
Clock Image Capture Module

Captures screenshots from OBS WebSocket, manages temp files, and provides
downscaled images for AI analysis.
"""

import asyncio
import os
import shutil
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

# OBS default screenshot directory (macOS)
OBS_SCREENSHOT_DIR = Path.home() / "Pictures" / "OBS"

# Project temp directory for processed images
TEMP_DIR = Path(tempfile.gettempdir()) / "ai-tells-time"


async def connect_to_obs() -> ReqClient:
    """Establish connection to OBS WebSocket server."""
    ws = ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    return ws


async def trigger_screenshot(source_name: str = OBS_SOURCE_NAME) -> Path:
    """
    Trigger a screenshot capture from OBS and return the path to the captured file.
    
    OBS saves screenshots to its default directory. We'll monitor and move the latest one.
    """
    ws = ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    try:
        ws.call(
            "GetSourceScreenshot",
            sourceName=source_name,
            imageFormat="png",
            imageWidth=854,  # 480p
            imageHeight=480,
            imageCompressionQuality=85
        )
        # OBS takes a moment to save the file
        await asyncio.sleep(0.5)
        
        # Find the most recent PNG in OBS screenshot directory
        return get_latest_screenshot()
    finally:
        ws.close()


def get_latest_screenshot() -> Path:
    """
    Find the most recent PNG file in the OBS screenshot directory.
    
    Returns the path to the latest screenshot file.
    """
    if not OBS_SCREENSHOT_DIR.exists():
        raise FileNotFoundError(f"OBS screenshot directory not found: {OBS_SCREENSHOT_DIR}")
    
    png_files = list(OBS_SCREENSHOT_DIR.glob("*.png"))
    if not png_files:
        raise FileNotFoundError(f"No PNG files found in {OBS_SCREENSHOT_DIR}")
    
    # Return the most recently modified file
    return max(png_files, key=lambda p: p.stat().st_mtime)


def move_to_temp_dir(source_path: Path) -> Path:
    """
    Move a screenshot to the project temp directory with a timestamped name.
    
    Returns the new path in the temp directory.
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    new_name = f"clock_{timestamp}.png"
    dest_path = TEMP_DIR / new_name
    
    # Move the file
    shutil.move(str(source_path), str(dest_path))
    
    return dest_path


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
    
    Returns the path to the processed image in the temp directory.
    """
    # Trigger screenshot in OBS
    obs_path = await trigger_screenshot()
    print(f"Captured from OBS: {obs_path}")
    
    # Move to temp directory with timestamp
    temp_path = move_to_temp_dir(obs_path)
    print(f"Moved to temp: {temp_path}")
    
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
