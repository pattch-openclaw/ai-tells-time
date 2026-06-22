# AI Tells Time

## Concept
A delightfully absurd live stream acting as an automated Turing test focused entirely on visual temporal hallucinations. 

The stream broadcasts a clock. Once per minute, a still image of the clock is fed to several different Vision AI models, asking them to tell the time. The responses are collected and presented on the stream both visually and through Text-to-Speech (TTS).

A key design philosophy of this project is that **AI hallucinations are a feature, not a bug.** The more they struggle to read a simple analog clock, the funnier the stream.

## Goals
*   Stream simultaneously to Twitch and YouTube.
*   Keep operating costs as close to $0 as possible (or completely free).
*   Embrace the chaos of AI vision inaccuracies.

## Architecture & Decisions to Make

### 1. Orchestration
*   **Language:** Python using `asyncio` to manage concurrent API calls and enforce strict timeouts (e.g., fast-failing local models after 20 seconds to keep the 1-minute loop alive).
*   **Environment & Dependency Management:** `uv` with a standard `pyproject.toml` configuration. This provides blazingly fast resolution and isolated environments without the heavy system footprint of Conda, perfect for an API/Ollama-driven application.

### 2. Broadcasting & Compositing
*   **Software:** OBS Studio with the `obs-websocket` feature enabled (built into modern OBS).
*   **Python Integration:** `obsws-python` library to allow our script to remotely control OBS (update text sources, trigger TTS audio, swap clock images).
*   **Configuration Management:** OBS "Scene Collections" will be exported as JSON files and tracked in this repository under `obs-assets/` alongside any static stream overlays. Connection credentials (host, port, password) are managed via `~/.config/ai-tells-time/.env` on the Mac Mini.
*   **Simulcasting:** Restream.io vs local OBS Multistream plugin (Aitum).
*   **Status:** ✅ OBS WebSocket connection is working. The script successfully connects to OBS and updates text sources. API integrations (OpenAI, Anthropic, Gemini) are not yet implemented.

### 3. Vision Models
Need to balance cost vs "personality". Since hallucinations are desired, cheaper or smaller models might actually be *better*.
*   **Local/Free:** `ollama` running lightweight vision models (like `moondream`, `llava:7b`, or `llama3.2-vision:11b`). These will run efficiently on the target M4 Mac Mini utilizing Apple Silicon's unified memory, acting as our chaotic baseline.
*   **API (Cheap/Free tiers):** `gemini-2.0-flash` (or 1.5), `gpt-4o-mini`, `claude-3-haiku`. 

### 4. Text-to-Speech (TTS)
*   Needs to be free/cheap given the 1-minute interval (1,440 requests/day).
*   **Proposed:** `edge-tts` (hooks into Microsoft Edge's free Azure TTS API) or local open-source options like Piper.

### 5. The Clock Source
*   **Option A:** A physical webcam pointed at a real, cheap analog clock. (High hallucination potential due to glare, angles, and physical oddities).
*   **Option B:** A programmatically generated image of a clock using Python `Pillow`. (Cleaner, but maybe too easy for the AIs?).

### 6. Deployment
*   **Target Machine:** Apple Silicon Mac Mini (M4) serving as both the application runtime and GitHub Actions self-hosted runner.
*   **Deployment Workflow:** Pushing to `main` branch triggers GitHub Actions on the Mac Mini to pull latest changes, sync dependencies with `uv`, and restart the application.
*   **Configuration:** Environment variables (OBS credentials, API keys) are stored in `~/.config/ai-tells-time/.env` on the Mac Mini, NOT in the repository.

## 7. Image Capture Workflow

Since we're already using OBS for compositing, we'll leverage OBS to capture clock images:

1. **Trigger Screenshot:** Use `GetSourceScreenshot` via obs-websocket to capture the `Clock_Camera` source
2. **OBS Output:** Screenshots saved to default OBS folder (`~/Pictures/OBS/` on macOS)
3. **File Management:** Monitor the OBS directory, move latest PNG to project temp folder
4. **Downscale:** Reduce to 480p (854x480) for cost efficiency while maintaining readability
5. **Cleanup:** Remove old temp files after each loop iteration

### OBS Source Name
- `Clock_Camera` (the camera source we'll capture from)

### Screenshot Settings
- Format: PNG
- Resolution: 854x480 (480p) - balances readability with API token costs
- Compression: 85% quality (smaller files, still high quality)

### Example OBS WebSocket Screenshot Call

```python
await ws.call(requests.GetSourceScreenshot(
    sourceName="Clock_Camera",
    imageFormat="png",
    imageWidth=854,
    imageHeight=480,
    imageCompressionQuality=85
))
```

This captures directly from the camera source at reduced resolution, avoiding the need for post-capture downscaling.

## OBS WebSocket Configuration

1. **Enable WebSocket Server:** OBS → Tools → WebSocket Server Settings → Enable
2. **Set port:** Default 4455 (can be changed, update `OBS_WEBSOCKET_PORT` in `.env`)
3. **Set password:** Note this for `~/.config/ai-tells-time/.env`
4. **Create a text source:** Name it `text_gpt` for the script to update

## .env File Location (Mac Mini)

Create `~/.config/ai-tells-time/.env` **on the Mac Mini** with:
```env
OBS_WEBSOCKET_HOST=localhost
OBS_WEBSOCKET_PORT=4455
OBS_WEBSOCKET_PASSWORD=your_obs_password_here
```

For testing without API keys, only the OBS variables are required.

## Deployment Architecture

**Important:** OBS and this application run on a separate Mac Mini (not this development machine). The Mac Mini serves as both the application runtime and GitHub Actions self-hosted runner.

### Development Workflow
- **This machine (your Mac):** Code development, git commits, running tests
- **Mac Mini:** OBS running with WebSocket, application execution, streaming to Twitch/YouTube

## Mac Mini Setup (Self-Hosted GitHub Actions Runner)

If you need to re-setup the Mac Mini as a GitHub Actions runner:

```bash
# 1. Download and extract the runner
cd ~
mkdir -p actions-runner && cd actions-runner
curl -o actions-runner.tar.gz -L https://github.com/actions/runner/releases/latest/download/actions-runner-osx-arm64-$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep -oP '"tag_name": "\K[^"]+').tar.gz
tar xzf ./actions-runner.tar.gz

# 2. Configure the runner
./config.sh --url https://github.com/pattch-openclaw/ai-tells-time --token YOUR_PAT_TOKEN

# 3. Install and start as a service
./svc.sh install sam
./svc.sh start
```

### Current Status: ✅ OBS WebSocket + Image Capture Working

The OBS WebSocket connection and image capture are fully functional:
- ✅ Connects to OBS on localhost:4455
- ✅ Authenticates with the WebSocket password
- ✅ Updates text sources in OBS scenes (via `main.py`)
- ✅ Captures clock images using `save_source_screenshot` (via `ai-tells-time-capture`)
- ❌ AI API integration (OpenAI, Anthropic, Gemini) - not yet implemented
- ❌ Text-to-Speech (TTS) - not yet implemented

### Image Capture Workflow (Verified)

The capture script successfully:
1. Connects to OBS WebSocket
2. Calls `save_source_screenshot` on the `Clock_Camera` source
3. Saves the image directly to `~/Library/Caches/ai-tells-time/clock_temp_*.png`
4. Image is captured at 854x480 (480p) in PNG format with 85% quality

Run with: `uv run ai-tells-time-capture`

### Next Steps
- Implement AI vision model integration to tell time from clock images
- Add TTS for audio responses
- Set up clock image source (physical webcam or generated image)
- Configure simulcasting to Twitch/YouTube
- Implement AI vision model to tell time from captured clock images

## Development Practices

### Dependency Management with `uv`
When changing dependencies in `pyproject.toml`, always run `uv sync` to update `uv.lock` and commit both files together:

```bash
# After editing pyproject.toml
uv sync
git add pyproject.toml uv.lock
git commit -m "Update dependencies"
```

### Pre-commit Hook Setup
A pre-commit hook is included in `hooks/pre-commit` to ensure `uv.lock` is always updated when `pyproject.toml` changes.

To install it:
```bash
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Deployment on Mac Mini
The GitHub Actions workflow on the Mac Mini automatically:
1. Pulls the latest code from `main`
2. Runs `uv sync` to install dependencies
3. Restarts the application

If you need to manually deploy, run:
```bash
cd ~/Coding/ai-tells-time
git pull origin main
uv sync
# Restart your application as needed
```

If `uv.lock` shows merge conflicts, resolve them by using the version from `main`:
```bash
git checkout --theirs uv.lock
git add uv.lock
git commit -m "Resolve uv.lock merge conflict"
```

**Requirements:**
- GitHub Personal Access Token with `repo` scope
- OBS WebSocket enabled on the Mac Mini
- Python 3.12+ installed
