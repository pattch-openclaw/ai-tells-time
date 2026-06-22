# AI Tells Time - Capture Module

The `capture.py` module handles image capture from OBS and prepares images for AI analysis.

## Features

- **OBS WebSocket Integration:** Trigger screenshots from `Clock_Camera` source
- **Resolution:** 480p (854x480) for optimal cost vs quality
- **File Management:** Monitors OBS default screenshot dir, moves to temp folder with timestamps
- **Cleanup:** Removes files older than 1 hour to prevent accumulation

## Usage

```python
from src.capture import capture_clock_image
import asyncio

async def main():
    image_path = await capture_clock_image()
    print(f"Image captured: {image_path}")

asyncio.run(main())
```

## Command Line

```bash
uv run ai-tells-time-capture
```

## Requirements

- OBS WebSocket enabled (Tools → WebSocket Server Settings)
- OBS source named `Clock_Camera` must exist
- Environment variables (optional, defaults shown):
  - `OBS_WEBSOCKET_HOST=localhost`
  - `OBS_WEBSOCKET_PORT=4455`
  - `OBS_WEBSOCKET_PASSWORD=` (empty by default)

## Output

- Image saved to `~/Pictures/OBS/` by OBS
- Moved to `/tmp/ai-tells-time/clock_YYYYMMDD_HHMMSS.png`
- Original OBS screenshot is removed (moved, not copied)
