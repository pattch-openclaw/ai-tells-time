# Scripts

This folder contains utility scripts for the AI Tells Time project.

## record_inference.py

A standalone script to manually record inference results to the database. Useful for:

- Testing the database integration without running the main loop
- Adding historical data for testing accuracy metrics
- Debugging inference results

### Usage

```bash
# Record an accurate result
uv run python scripts/record_inference.py \
  --model gemini-1.5-flash \
  --guess "12:34" \
  --actual "12:29" \
  --is-accurate

# Record an inaccurate result
uv run python scripts/record_inference.py \
  --model local \
  --guess "3:15" \
  --actual "3:45" \
  --not-accurate

# Auto-determine accuracy (within ±5 minutes)
uv run python scripts/record_inference.py \
  --model openai-gpt4o \
  --guess "10:00" \
  --actual "10:02"
```

### Arguments

- `--model` (required): Model name (e.g., `gemini-1.5-flash`, `local`, `qwen2.5vl:7b`)
- `--guess` (required): Time guess from the model in HH:MM format
- `--actual` (optional): Actual time for comparison in HH:MM format. Defaults to current time.
- `--is-accurate`: Mark as accurate (within ±5 minutes of actual)
- `--not-accurate`: Mark as inaccurate (outside ±5 minutes)
- `--provider` (optional): Provider family (gemini, openai, claude, local). Auto-detects if not provided.
- `--image` (optional): Path to captured image file

### Output

The script saves the inference result to the database and displays:
- Result ID and details
- Offset from actual time
- Current accuracy stats (recent and overall)
