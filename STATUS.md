# AI Tells Time - Status

## Overview

Live stream where AI vision models tell time from analog clock images. Embrace hallucinations as a feature.

## Current Status

- **Clock Image Capture:** ✅ Implemented (OBS WebSocket integration)
- **AI API Integration:** 🔄 Not yet implemented
- **Structured Output Parsing:** 🔄 Not yet implemented
- **Broadcasting:** 🔄 Not yet implemented

## What's Next

1. **Clock Image Capture:** ✅ Done - captures from OBS `Clock_Camera` source at 480p
2. **AI API Integration:** Integrate OpenAI, Anthropic, and Gemini vision APIs
3. **Structured Output Parsing:** Systematic prompts + JSON parsing for time extraction
4. **OBS WebSocket Updates:** Update text sources with AI responses (basic OBS integration already working)

## Recent Updates

- **obsws-python:** Changed to `>=1.8.0` (available version is `<=1.8.0`)
- **src/capture.py:** Recreated actual Python code (was missing from earlier commits)
- **CI/CD:** Updated workflow to do clean sync (`rm -rf .venv uv.lock`) before `uv sync`
- **Python version:** Pinned to 3.12 via `.python-version`
- **UV cache:** Added `uv cache clean` step to clear stale metadata
- **DEPLOY-MAINTENANCE.md:** Added maintenance notes for future deployment troubleshooting
