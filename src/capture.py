#!/usr/bin/env python3
"""
Clock Image Capture Module

Captures screenshots from OBS WebSocket, manages temp files, and provides
downscaled images for AI analysis.
"""

import argparse
import asyncio
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
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

# Project output directory (outside git repo)
OUTPUT_DIR = Path.home() / "Coding" / "ai-tells-time-output"


def parse_resolution(resolution_str: str) -> Tuple[int, int]:
    """Parse resolution string (e.g., '854x480') into (width, height) tuple."""
    try:
        width, height = resolution_str.lower().split('x')
        return int(width), int(height)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid resolution format: {resolution_str}. Use WIDTHxHEIGHT (e.g., 854x480)")


async def connect_to_obs() -> ReqClient:
    """Establish connection to OBS WebSocket server."""
    ws = ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    return ws


async def trigger_screenshot(
    source_name: str = OBS_SOURCE_NAME,
    output_path: Optional[Path] = None,
    resolution: Tuple[int, int] = (854, 480)
) -> Path:
    """
    Trigger a screenshot capture from OBS and save to the specified path.
    
    Uses the new save_source_screenshot API which saves directly to a file path.
    
    Args:
        source_name: Name of the OBS source to capture
        output_path: Path where the image will be saved. If None, uses temp dir.
        resolution: Tuple of (width, height) for the captured image
        
    Returns:
        Path to the captured image file
    """
    ws = ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    try:
        # Create output directory if provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temp path if no output path provided
        if not output_path:
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            temp_path = TEMP_DIR / f"clock_temp_{timestamp}.png"
            output_path = temp_path
        
        # Save screenshot directly to output path
        ws.save_source_screenshot(
            name=source_name,
            img_format="png",
            file_path=str(output_path),
            width=resolution[0],
            height=resolution[1],
            quality=85
        )
        
        return output_path
    finally:
        ws.disconnect()


def move_to_output(temp_path: Path, output_dir: Path, keep_original: bool = False) -> Path:
    """
    Move a captured image from temp directory to the output directory.
    
    Args:
        temp_path: Path to the source image in temp directory
        output_dir: Destination directory
        keep_original: If True, copy instead of move
        
    Returns:
        Path to the image in output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate new filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    new_name = f"clock_{timestamp}.png"
    new_path = output_dir / new_name
    
    if keep_original:
        shutil.copy2(temp_path, new_path)
        print(f"Copied image to: {new_path}")
    else:
        shutil.move(temp_path, new_path)
        print(f"Moved image to: {new_path}")
    
    return new_path


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


async def capture_clock_image(
    output_dir: Optional[Path] = None,
    resolution: Tuple[int, int] = (854, 480)
) -> Path:
    """
    Main entry point for clock image capture.
    
    Args:
        output_dir: Directory to move the captured image to. If None, keeps in temp dir.
        resolution: Tuple of (width, height) for the captured image
        
    Returns:
        Path to the final image location
    """
    # Trigger screenshot in OBS (saves to temp dir with new API)
    temp_path = await trigger_screenshot(resolution=resolution)
    print(f"Captured from OBS: {temp_path}")
    
    # If output directory specified, move the image there
    if output_dir:
        final_path = move_to_output(temp_path, output_dir)
    else:
        final_path = temp_path
    
    # Cleanup old temp files
    cleanup_temp_dir(hours_old=1)
    
    return final_path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Capture clock images from OBS WebSocket"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory for captured images (default: temp directory)"
    )
    parser.add_argument(
        "--resolution", "-r",
        type=parse_resolution,
        default="854x480",
        help="Target resolution in WIDTHxHEIGHT format (default: 854x480)"
    )
    return parser.parse_args()


def main():
    """Entry point for the CLI command."""
    args = parse_args()
    
    # Convert output to Path if provided
    output_dir = Path(args.output) if args.output else None
    
    asyncio.run(capture_clock_image(
        output_dir=output_dir,
        resolution=args.resolution
    ))


if __name__ == "__main__":
    main()
