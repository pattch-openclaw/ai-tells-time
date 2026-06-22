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

## Deployment Maintenance Notes

### Critical Workflow Steps for uv

The GitHub Actions workflow requires careful ordering and working directory management:

1. **Working Directory:** All `uv` commands must run from `/Users/sam/Coding/ai-tells-time`
   - Use `defaults.run.working-directory` in the job, or explicitly `cd` before each command
   - The checkout step runs outside the project directory, so subsequent steps need explicit paths

2. **Python Version Pinning:** Must be done from the project directory
   ```yaml
   - name: Set Python version
     working-directory: /Users/sam/Coding/ai-tells-time
     run: |
       uv python pin 3.12
   ```

3. **Cache Clearing:** Run `uv cache clean` before `uv sync` to avoid stale metadata
   ```yaml
   - name: Clear UV cache
     run: |
       uv cache clean
   ```

4. **Clean Sync:** Always run from the project directory
   ```yaml
   - name: Install dependencies
     working-directory: /Users/sam/Coding/ai-tells-time
     run: |
       rm -rf .venv uv.lock
       uv sync
   ```

5. **Git Pull with Stash:** Before pulling new code, stash any local changes
   ```yaml
   - name: Update repository
     working-directory: /Users/sam/Coding/ai-tells-time
     run: |
       git stash
       git pull origin main
       git stash pop || true
   ```

### Dependency Management Checklist

When dependencies break in the future, check:

1. **Package name on PyPI:** `uv pip search <package>` or check https://pypi.org
2. **Version constraints:** `uv pip index versions <package>` to see available versions
3. **Build backend config:** For `src/` layout, add `[tool.hatch.build] packages = ["src"]`
4. **Cache state:** Run `uv cache clean` to clear stale metadata

### Quick Reset Commands (for local debugging)

```bash
cd /Users/sam/Coding/ai-tells-time
git stash && git pull origin main && git stash pop || true
uv cache clean
rm -rf .venv uv.lock
uv python pin 3.12
uv sync
```
