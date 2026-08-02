# AI Tells Time - Status

## Overview

Live stream where AI vision models tell time from analog clock images. Embrace hallucinations as a feature.

## Current Status

- **Clock Image Capture:** ✅ Implemented (OBS WebSocket integration)
- **AI API Integration:** ✅ Implemented (Gemini, OpenAI, Claude, Local)
- **Structured Output Parsing:** ✅ Implemented (JSON schema enforcement)
- **Broadcasting:** ✅ Implemented (OBS multistream to Twitch + YouTube)
- **Database Integration:** ✅ Implemented (SQLite, manual recording helper script ready)
- **Main Loop Integration:** ⏳ In progress - saving inference results to DB during broadcast loop
- **On-stream Accuracy Metrics:** ⏳ Database ready, UI display pending (requires main loop integration)

## What's Next

### Priority 1: Main Loop Integration (Highest Priority)
1. Connect inference results to the SQLite database during the broadcast loop
2. Calculate and store accuracy for each model's guess (+/- 5 minutes threshold)
3. Once data is flowing, build on-screen display for:
   - Recent accuracy (last hour)
   - Overall accuracy per model
   - Average time offset

### Future (Lower Priority)
- **TTS Integration:** Audio responses for guesses. Not essential to core experience, can be added later if desired.

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
