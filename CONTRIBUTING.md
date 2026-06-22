# Local development for ai-tells-time

## Directory Structure

```
ai-tells-time/
├── src/
│   ├── capture.py          # Image capture from OBS
│   ├── ai/                 # AI API integration (to be implemented)
│   └── main.py             # Main orchestration loop
├── obs-assets/             # OBS scene collections and overlays
├── pyproject.toml          # Project dependencies
├── .env.example            # Example environment config
├── SETUP.md                # Setup instructions
├── ENVIRONMENT.md          # Environment variables reference
├── README.md               # Project overview
└── .gitignore
```

## Development

```bash
# Sync dependencies
uv sync

# Run tests (when implemented)
uv run pytest

# Run the capture test
uv run ai-tells-time-capture
```

## Testing Without OBS

For now, you can test the capture workflow logic by manually placing a test PNG in `~/Pictures/OBS/` and running the script - it will find and process that file.
