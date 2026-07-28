# AI Tells Time - Status

## Overview

Live stream where AI vision models tell time from analog clock images. Embrace hallucinations as a feature.

## Current Status

- **Clock Image Capture:** ✅ Implemented (OBS WebSocket integration)
- **AI API Integration:** ✅ Implemented (Gemini, OpenAI, Claude, Local)
- **Structured Output Parsing:** ✅ Implemented (JSON schema enforcement)
- **Broadcasting:** ✅ Implemented (OBS multistream to Twitch + YouTube)
- **Database Integration:** ✅ Implemented (SQLite, manual recording helper script ready)
- **On-stream Accuracy Metrics:** ⏳ Database ready, UI display pending

## What's Next

1. **On-stream Accuracy Metrics:** Display recent/overall accuracy on stream using SQLite queries
2. **TTS Integration:** Add text-to-speech for audio responses (lower priority)
3. **Main Loop Integration:** Integrate database saves into the main broadcast loop

## Recent Updates

- **record_inference.py:** New helper script to manually record inference results
- **Database Tests:** Added test coverage for database and script helper
- **README Updates:** Documented database schema, metrics queries, and scripts

### Previous Updates

- **obsws-python:** Changed to `>=1.8.0` (available version is `<=1.8.0`)
- **src/capture.py:** Recreated actual Python code (was missing from earlier commits)
- **CI/CD:** Updated workflow to do clean sync (`rm -rf .venv uv.lock`) before `uv sync`
- **Python version:** Pinned to 3.12 via `.python-version`
- **UV cache:** Added `uv cache clean` step to clear stale metadata
- **DEPLOY-MAINTENANCE.md:** Added maintenance notes for future deployment troubleshooting
