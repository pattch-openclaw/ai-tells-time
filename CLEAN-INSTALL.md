# AI Tells Time - Clean Installation

## Quick Start

```bash
cd /Users/sam/Coding/ai-tells-time

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
