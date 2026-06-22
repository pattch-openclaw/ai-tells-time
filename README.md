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

## OBS WebSocket Configuration

1. **Enable WebSocket Server:** OBS → Tools → WebSocket Server Settings → Enable
2. **Set port:** Default 4455 (can be changed, update `OBS_WEBSOCKET_PORT` in `.env`)
3. **Set password:** Note this for `~/.config/ai-tells-time/.env`
4. **Create a text source:** Name it `text_gpt` for the script to update

## .env File Location

Create `~/.config/ai-tells-time/.env` on the Mac Mini with:
```env
OBS_WEBSOCKET_HOST=localhost
OBS_WEBSOCKET_PORT=4455
OBS_WEBSOCKET_PASSWORD=your_obs_password_here
```

For testing without API keys, only the OBS variables are required.

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

### Current Status: ✅ OBS WebSocket Working

The basic OBS WebSocket connection is fully functional. The script:
- ✅ Connects to OBS on localhost:4455
- ✅ Authenticates with the WebSocket password
- ✅ Updates text sources in OBS scenes
- ❌ AI API integration (OpenAI, Anthropic, Gemini) - not yet implemented
- ❌ Text-to-Speech (TTS) - not yet implemented

### Next Steps
- Implement AI vision model integration to tell time from clock images
- Add TTS for audio responses
- Set up clock image source (physical webcam or generated image)
- Configure simulcasting to Twitch/YouTube

If you need to re-setup the Mac Mini as a GitHub Actions runner:

```bash
# 1. Download and extract the runner
cd ~
mkdir -p actions-runner && cd actions-runner
curl -o actions-runner.tar.gz -L https://github.com/actions/runner/releases/latest/download/actions-runner-osx-arm64-$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep -oP '"tag_name": "\K[^"]+').tar.gz
tar xzf ./actions-runner.tar.gz

# 2. Configure the runner
./config.sh --url https://github.com/pattch-openclaw/ai-tells-time --token YOUR_PAT_TOKEN
# Enter runner name: mac-mini
# Enter labels (comma-separated): mac-mini, self-hosted

# 3. Install and start as a service
./svc.sh install sam
./svc.sh start
```

**Requirements:**
- GitHub Personal Access Token with `repo` scope
- OBS WebSocket enabled on the Mac Mini
- Python 3.12+ installed

1. **Enable WebSocket Server:** OBS → Tools → WebSocket Server Settings → Enable
2. **Set port:** Default 4455 (can be changed, update `OBS_WEBSOCKET_PORT` in `.env`)
3. **Set password:** Note this for `~/.config/ai-tells-time/.env`
4. **Create a text source:** Name it `text_gpt` for the script to update

## .env File Location

Create `~/.config/ai-tells-time/.env` on the Mac Mini with:
```env
OBS_WEBSOCKET_HOST=localhost
OBS_WEBSOCKET_PORT=4455
OBS_WEBSOCKET_PASSWORD=your_obs_password_here
```

For testing without API keys, only the OBS variables are required.
