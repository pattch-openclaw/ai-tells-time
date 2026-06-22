# AI Tells Time - Environment

Environment variables for configuration:

```env
# OBS WebSocket Settings
OBS_WEBSOCKET_HOST=localhost
OBS_WEBSOCKET_PORT=4455
OBS_WEBSOCKET_PASSWORD=your_password

# AI API Settings (later)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-...
# GEMINI_API_KEY=...
```

## Configuration File Location

- macOS/Linux: `~/.config/ai-tells-time/.env`
- Windows: `%APPDATA%\ai-tells-time\.env`

The `.env` file is gitignored and should NOT be committed to the repository.
