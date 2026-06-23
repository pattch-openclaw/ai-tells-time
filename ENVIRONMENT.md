# AI Tells Time - Environment

Environment variables for configuration:

```env
# OBS WebSocket Settings
OBS_WEBSOCKET_HOST=localhost
OBS_WEBSOCKET_PORT=4455
OBS_WEBSOCKET_PASSWORD=your_password

# AI API Settings
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
GEMINI_API_KEY=AIza...  # Gemini API key (starts with 'AIza')
```

## Gemini API Key

For the Gemini provider to work, you need a **server API key** (not a client API key):

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. The key should start with `AIza...` (22 characters, starting with AIza)
4. Copy the key and add it to your `.env` file as `GEMINI_API_KEY=AIza...`

**Important**: The key must start with `AIza`. Keys starting with `gen-lang-client-` are client-side keys and won't work with the server API.

## Configuration File Location

- macOS/Linux: `~/.config/ai-tells-time/.env`
- Windows: `%APPDATA%\ai-tells-time\.env`

The `.env` file is gitignored and should NOT be committed to the repository.
