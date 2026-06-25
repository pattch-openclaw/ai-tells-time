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
*   **Environment & Dependency Management:** `uv` with a standard `pyproject.toml` configuration. This provides blazingly fast resolution and isolated environments without the heavy system footprint of Conda, perfect for an API/Local-driven application.

### 2. Broadcasting & Compositing
*   **Software:** OBS Studio with the `obs-websocket` feature enabled (built into modern OBS).
*   **Python Integration:** `obsws-python` library to allow our script to remotely control OBS (update text sources, trigger TTS audio, swap clock images).
*   **Configuration Management:** OBS "Scene Collections" will be exported as JSON files and tracked in this repository under `obs-assets/` alongside any static stream overlays. Connection credentials (host, port, password) are managed via `~/.config/ai-tells-time/.env` on the Mac Mini.
*   **Simulcasting:** Direct broadcast to both Twitch and YouTube from OBS using a local multistream plugin (e.g., Aitum Multiple Outputs plugin). Restream.io is explicitly excluded to keep operations free and avoid monthly fees.
*   **Status:** ✅ OBS WebSocket connection is working. The script successfully connects to OBS and updates text sources. Gemini API integration is fully implemented and working end-to-end.

### 3. Vision Models
Need to balance cost vs "personality". Since hallucinations are desired, cheaper or smaller models might actually be *better*.
*   **Local/Free:** `local` provider running lightweight vision models (like `moondream`, `llava:7b`, or `llama3.2-vision:11b`). These will run efficiently on the target M4 Mac Mini utilizing Apple Silicon's unified memory, acting as our chaotic baseline.
*   **API (Cheap/Free tiers):** `gemini-2.5-flash`, `gpt-4o-mini`, `claude-haiku-4-5`.
*   **Status:** ✅ Basic integrations are fully implemented for Gemini, Claude, and OpenAI, as well as locally running models.

### 4. Text-to-Speech (TTS)
*   Needs to be free/cheap given the 1-minute interval (1,440 requests/day).
*   **Proposed:** `edge-tts` (hooks into Microsoft Edge's free Azure TTS API) or local open-source options like Piper.
*   **Status:** Lower priority. The current focus is on getting AI integration working and updating the text interfaces. Gemini is fully implemented.

### 5. The Clock Source
*   **Settled:** A physical webcam pointed at a real, cheap analog clock. We already have a working setup in OBS and are actively capturing stills from this camera. (High hallucination potential due to glare, angles, and physical oddities).

### 6. Deployment
*   **Target Machine:** Apple Silicon Mac Mini (M4) serving as both the application runtime and GitHub Actions self-hosted runner.
*   **Deployment Workflow:** Pushing to `main` branch triggers GitHub Actions on the Mac Mini to pull latest changes, sync dependencies with `uv`, and restart the application.
*   **Configuration:** Environment variables (OBS credentials, API keys) are stored in `~/.config/ai-tells-time/.env` on the Mac Mini, NOT in the repository.

## 7. Image Capture Workflow

Since we're already using OBS for compositing, we'll leverage OBS to capture clock images:

1. **Trigger Screenshot:** Use `GetSourceScreenshot` via obs-websocket to capture the `Clock_Camera` source
2. **OBS Output:** Screenshots saved to default OBS folder (`~/Pictures/OBS/` on macOS)
3. **File Management:** Monitor the OBS directory, move latest PNG to project temp folder
4. **Downscale:** Reduce to 360p (640x360) for cost efficiency while maintaining readability
5. **Cost Optimization:** Inference frequency is optimized to reduce API costs:
    - **Local provider runs every minute** - Always runs for real-time updates
    - **External providers (Gemini, OpenAI, Claude) run every 5 minutes** - Skipped on the 4 intermediate minutes
    - **Override:** Use `--every-minute` flag to run all providers every minute (useful for testing or if costs become acceptable)
6. **Cleanup:** Remove old temp files after each loop iteration

### OBS Source Name
- `Clock_Camera` (the camera source we'll capture from)

### Screenshot Settings
- Format: PNG
- Resolution: 640x360 (360p) - balances readability with API token costs
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

## .env File Location

Create `~/.config/ai-tells-time/.env` with required environment variables:
```env
# OBS WebSocket Settings
OBS_WEBSOCKET_HOST=localhost
OBS_WEBSOCKET_PORT=4455
OBS_WEBSOCKET_PASSWORD=your_obs_password_here

# AI API Settings
GEMINI_API_KEY=your-gemini-api-key-here  # Required for Gemini provider
# OPENAI_API_KEY=***  # Optional, for future OpenAI provider
# ANTHROPIC_API_KEY=***  # Optional, for future Claude provider
# LOCAL_MODEL=qwen2.5vl:7b  # Optional, default model for Local
```

For testing without API keys, only the OBS variables are required. Gemini integration requires a valid API key starting with `AIza...`. The local provider runs locally with no API key needed. Use `LOCAL_MODEL` environment variable to specify a different local model (default: `qwen2.5vl:7b`).

**Default Behavior:** When running `uv run main.py` without arguments, ALL implemented providers are run by default (currently: Gemini + Local). This ensures the system works end-to-end with multiple AI models. Use the `--providers` flag to run specific providers only.

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

## Current Status

### ✅ Gemini Provider Integration (Working End-to-End)

The Gemini API integration is now fully functional:
- ✅ Configurable provider selection via `--providers` CLI flag
- ✅ Gemini provider using Google's `genai` SDK with Structured Outputs
- ✅ JSON-formatted responses for reliable time parsing
- ✅ Configurable API key via `GEMINI_API_KEY` environment variable
- ✅ Automatic retries with exponential backoff

**Setup:**
1. Get a server API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
   - The key must start with `AIza...` (not `gen-lang-client-...`)
2. Add to your `.env` file: `GEMINI_API_KEY=your-key-here`
3. Run with: `uv run main.py` (runs all providers by default)

## Default Behavior

When running `uv run main.py` without any arguments, ALL implemented providers are run by default. This ensures the system works end-to-end with multiple AI models.

Currently, this means both **Gemini** and **Local** providers run simultaneously. Use the `--providers` flag to run specific providers only.

**Provider Selection:****
```bash
# Default: run all implemented providers (gemini + local)
uv run main.py

# Run only gemini
uv run main.py --providers gemini

# Run only local
uv run main.py --providers local

# Run multiple providers
uv run main.py --providers gemini local
```

### ✅ Image Capture Pipeline (v2 - Updated)

The image capture system has been enhanced with configurable resolution and output location:

**Features:**
- ✅ Configurable output resolution (e.g., `640x360`, `1920x1080`)
- ✅ Configurable output directory for captured images
- ✅ Automatic file management with timestamps
- ✅ Main loop for periodic captures with `--single` mode for one-off captures

**New Commands:**
```bash
# Capture a single image with custom resolution
uv run capture --resolution 1920x1080

# Capture and save to a specific directory
uv run capture --output ~/Pictures/ai-tells-time

# Run the cleanup routine to purge temporary and output folders
uv run cleanup

# Run the application (captures every minute, updates OBS)
uv run main.py

# Single capture with custom settings
uv run capture --resolution 640x360 --output ~/Coding/ai-tells-time-output
```

### ✅ OBS WebSocket + Image Capture Working (Legacy)

The OBS WebSocket connection and image capture are fully functional:
- ✅ Connects to OBS on localhost:4455
- ✅ Authenticates with the WebSocket password
- ✅ Updates text sources in OBS scenes (via `main.py`)
- ✅ Captures clock images using `save_source_screenshot` (via `capture`)
  - Images saved to configurable location (default: temp directory)
- ✅ AI API integration (OpenAI, Anthropic, Gemini) - implemented
- ❌ Text-to-Speech (TTS) - not yet implemented

### Image Capture Workflow (Verified)

The capture script successfully:
1. Connects to OBS WebSocket
2. Calls `save_source_screenshot` on the `Clock_Camera` source
3. Saves the image directly to the specified output directory
4. Image is captured at configurable resolution (default: 640x360) in PNG format with 85% quality

**Output Location:**
- By default: OS temp directory (`/var/folders/.../ai-tells-time/clock_temp_*.png`)
- With `--output`: Configurable location (e.g., `~/Coding/ai-tells-time-output/`)

**Note:** Images are saved to a directory outside the git repository (`Coding/ai-tells-time-output/`) to avoid cluttering git status. The directory is tracked in `.gitignore`.

Run with: `uv run capture`

### Next Steps
- Configure direct OBS simulcasting to Twitch and YouTube via a local plugin (avoiding paid services like Restream)
- (Lower Priority) Add TTS for audio responses

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
- GEMINI_API_KEY set in `.env` for Gemini provider
