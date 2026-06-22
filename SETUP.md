# AI Tells Time - Project Setup

## Prerequisites

- Python 3.12+ (project pins to 3.12 via `.python-version`)
- OBS Studio with WebSocket plugin enabled
- OBS source named `Clock_Camera`

## Installation

```bash
# Clone the repository
cd /Users/sam/Coding/ai-tells-time

# uv will automatically use the pinned Python version (3.12)
# Clean slate: remove old venv and lockfile
rm -rf .venv uv.lock

# Install dependencies with uv
uv sync
```

If you need to regenerate the lockfile:

```bash
uv lock
uv sync
```

## Configuration

Create `~/.config/ai-tells-time/.env` with:

```env
OBS_WEBSOCKET_HOST=localhost
OBS_WEBSOCKET_PORT=4455
OBS_WEBSOCKET_PASSWORD=***
```

## OBS Setup

1. Enable WebSocket Server: OBS → Tools → WebSocket Server Settings → Enable
2. Set port: Default 4455 (update if different)
3. Create source named `Clock_Camera` (your camera source)
4. Create text source named `text_gpt` (for AI responses)

## Usage

### Capture a single clock image

```bash
uv run ai-tells-time-capture
```

This will:
1. Trigger screenshot from `Clock_Camera`
2. Save to temp directory with timestamp
3. Return the path to the captured image

## Deployment

The project is automatically deployed to the Mac Mini via GitHub Actions when pushing to `main`. The workflow ensures Python 3.12 is used via `uv python pin 3.12`.
