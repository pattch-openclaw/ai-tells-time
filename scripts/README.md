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
  --model "test-gemini" \
  --guess "12:34" \
  --actual "12:29" \
  --is-accurate

# Record an inaccurate result
uv run python scripts/record_inference.py \
  --model "test-local" \
  --guess "3:15" \
  --actual "3:45" \
  --not-accurate

# Auto-determine accuracy (within ±5 minutes)
uv run python scripts/record_inference.py \
  --model "test-openai" \
  --guess "10:00" \
  --actual "10:02"
```

### Arguments

- `--model` (required): Model name (use test-friendly names like `test-gemini`, `test-local`, `test-openai`)
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

---

## view_recent.py

View recent inference results from the database. Useful for sanity checking your data and verifying accuracy calculations.

### Usage

```bash
# View the 20 most recent rows
uv run python scripts/view_recent.py

# View 10 rows
uv run python scripts/view_recent.py --limit 10

# Filter by provider
uv run python scripts/view_recent.py --provider local

# Filter by specific model
uv run python scripts/view_recent.py --model "test-model-1"

# Show full row data
uv run python scripts/view_recent.py --verbose
```

### Arguments

- `--limit` (optional): Number of rows to display (default: 20)
- `--provider` (optional): Filter by provider family (gemini, openai, claude, local)
- `--model` (optional): Filter by specific model name
- `--verbose` (optional): Show full row data including all columns

### Output

The script displays a formatted table of recent rows with:
- Row ID
- Reference time
- Model name
- Guess time
- Offset in minutes
- Accuracy indicator (✅/❌)

At the bottom, it shows a summary with the accuracy rate for the displayed rows.

---

## clear_database.py

Clear all rows from the database. This is useful for resetting your test data or starting fresh.

⚠️ **Warning**: This will permanently delete ALL rows from the database!

### Usage

```bash
# Normal mode (asks for confirmation)
uv run python scripts/clear_database.py

# Force mode (no confirmation)
uv run python scripts/clear_database.py --force

# Use production database
uv run python scripts/clear_database.py --prod
```

### Arguments

- `--force` (optional): Skip confirmation prompt (use with caution!)
- `--prod` (optional): Use production database instead of dev

### Behavior

1. Shows the database path and row count
2. Asks you to type `delete` to confirm (twice for safety)
3. Clears all rows from the database
4. Shows the number of rows deleted

---

## clear_models.py

Clear rows for specific model(s) from the database. Useful for cleaning up test data or removing specific models.

### Usage

```bash
# Clear rows for a specific model
uv run python scripts/clear_models.py --model "test-model-1"

# Clear rows for multiple models
uv run python scripts/clear_models.py --model "test-model-1" --model "test-model-2"

# Clear rows for all models from a provider
uv run python scripts/clear_models.py --provider local

# Clear all models (requires --force)
uv run python scripts/clear_models.py --all-models --force
```

### Arguments

- `--model` (optional): Model name to clear (can be specified multiple times)
- `--provider` (optional): Provider family to clear (gemini, openai, claude, local)
- `--all-models` (optional): Clear all models (requires `--force`)
- `--force` (optional): Skip confirmation prompt (use with caution!)
- `--prod` (optional): Use production database instead of dev

### Behavior

1. Shows the count of rows that will be deleted
2. Asks you to type `delete` to confirm (unless `--force` is used)
3. Clears matching rows from the database
4. Shows the number of rows deleted

### Safety Notes

- `--all-models` requires `--force` to prevent accidental deletion
- The script will always ask for confirmation unless `--force` is used
- You can use test-friendly model names like `test-gemini`, `test-local`, etc. to keep test data separate from production data
