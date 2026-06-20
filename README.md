# AI Clock Stream

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
*   **Proposed:** Python. Excellent asynchronous support (`asyncio`) is crucial for hitting multiple APIs concurrently, and the ecosystem for AI SDKs is top-tier.

### 2. Broadcasting & Compositing
*   **Option A:** OBS Studio + `obs-websocket` (via `obsws-python`). Visually easy to design, script can update text sources and play media.
*   **Option B:** Headless FFmpeg pipeline. Harder to design, lower overhead.
*   **Simulcasting:** Restream.io vs local OBS Multistream plugin (Aitum).

### 3. Vision Models
Need to balance cost vs "personality". Since hallucinations are desired, cheaper or smaller models might actually be *better*.
*   **Local/Free:** `llava`, `qwen2-vl` via Ollama (requires local GPU overhead).
*   **API (Cheap/Free tiers):** `gemini-2.0-flash` (or 1.5), `gpt-4o-mini`, `claude-3-haiku`. 

### 4. Text-to-Speech (TTS)
*   Needs to be free/cheap given the 1-minute interval (1,440 requests/day).
*   **Proposed:** `edge-tts` (hooks into Microsoft Edge's free Azure TTS API) or local open-source options like Piper.

### 5. The Clock Source
*   **Option A:** A physical webcam pointed at a real, cheap analog clock. (High hallucination potential due to glare, angles, and physical oddities).
*   **Option B:** A programmatically generated image of a clock using Python `Pillow`. (Cleaner, but maybe too easy for the AIs?).
