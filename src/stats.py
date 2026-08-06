import json
from pathlib import Path
from datetime import datetime, timezone
import os
from collections import defaultdict
from zoneinfo import ZoneInfo

from src.database import get_prod_database

ASSETS_DIR = Path(__file__).parent.parent / "obs-assets"

# Use PST timezone for consistent display
PST = ZoneInfo("America/Los_Angeles")

def export_stats(db=None):
    """Export current accuracy stats to JSON for the OBS Browser Source."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    # Always use production database - this matches what main.py uses with --prod
    db = db or get_prod_database()
    
    models = db.get_active_models()
    
    # Debug logging
    print(f"DEBUG: get_active_models returned: {models}")
    
    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "accuracy": db.get_overall_accuracy(),
            "total": db.get_total_inferences()
        },
        "models": {}
    }
    
    # Fetch 1h and 24h accuracy for each model
    for model in models:
        accuracy_1h = db.get_recent_accuracy(hours=1, model_name=model)
        accuracy_24h = db.get_recent_accuracy(hours=24, model_name=model)
        total = db.get_total_inferences(model_name=model)
        
        print(f"DEBUG: Model '{model}' - 1h: {accuracy_1h}, 24h: {accuracy_24h}, total: {total}")
        
        stats["models"][model] = {
            "1h": accuracy_1h,
            "24h": accuracy_24h,
            "total": total
        }
        
    # Fetch offset data for the last hour (for line chart)
    offset_data = db.get_offset_over_time(hours=1)
    
    # Group offsets by model with PST timestamps in 12-hour format
    offsets_by_model = defaultdict(list)
    for item in offset_data:
        # Parse the UTC timestamp and convert to PST
        ts = item["timestamp"]
        if isinstance(ts, str):
            # Parse ISO format timestamp (assumes UTC)
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            # Convert to PST
            dt_pst = dt.astimezone(PST)
            # Format as 12-hour time (e.g., "2:30 PM")
            ts = dt_pst.strftime("%I:%M %p")
        offsets_by_model[item["model_name"]].append({
            "timestamp": ts,
            "offset_minutes": item["offset_minutes"]
        })
    
    stats["offsets"] = dict(offsets_by_model)
    
    # Write to file atomically (write to temp, then rename)
    stats_file = ASSETS_DIR / "stats.json"
    temp_file = ASSETS_DIR / "stats.json.tmp"
    
    with open(temp_file, "w") as f:
        json.dump(stats, f, indent=2)
        
    temp_file.replace(stats_file)
    return stats

def export_inference_results(db=None):
    """Export last inference results to JSON for the inference-results.html OBS Browser Source."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    db = db or get_prod_database()
    
    # Get last inference results for each provider
    last_results = db.get_last_inference_per_provider()
    
    # Build provider info mapping (sorted alphabetically for 3rd party providers)
    # Note: "openai" maps to CHATGPT because OpenAI models are used for CHATGPT
    provider_info = {
        "openai": {"name": "CHATGPT", "model": "gpt-4o-mini"},
        "chatgpt": {"name": "CHATGPT", "model": "gpt-4o-mini"},
        "claude": {"name": "CLAUDE", "model": "claude-3-5-haiku"},
        "gemini": {"name": "GEMINI", "model": "gemini-2.5-flash"},
        "local": {"name": "LOCAL", "model": "qwen2.5vl:7b"}
    }
    
    # Get latest inference timestamp
    latest_time = db.get_latest_timestamp()
    
    # Build result entries
    results = []
    for item in last_results:
        provider_family = item.get("provider_family", "local")
        info = provider_info.get(provider_family)
        if info:
            name = info["name"]
            model = info["model"]
        else:
            # Unrecognized provider - use capitalized name, but show "Other" for common unknown values
            name = "Other" if provider_family in ["other", "unknown"] else provider_family.capitalize()
            model = item.get("model_name", provider_family)
        
        # Get the actual time guess from the database
        time_guess = item.get("time_guess", "--:--")
        
        results.append({
            "name": name,
            "accuracy": item.get("accuracy", 0),
            "guess": time_guess,
            "provider_family": provider_family
        })
    
    # Add ACTUAL reference time entry
    pst_time = "--:-- PST"
    if latest_time:
        # Convert UTC to PST
        dt_utc = latest_time.replace(tzinfo=ZoneInfo("UTC")) if latest_time.tzinfo is None else latest_time
        pst_time = dt_utc.astimezone(PST).strftime("%I:%M %p")
    
    results.append({
        "name": "ACTUAL",
        "accuracy": 1.0,  # ACTUAL is always accurate by definition
        "guess": pst_time,
        "provider_family": "actual"
    })
    
    # Sort results: alphabetical for 3rd party (CHATGPT, CLAUDE, GEMINI), then LOCAL, then ACTUAL
    def sort_key(result):
        name = result["name"]
        if name == "ACTUAL":
            return (2, "")  # Last
        elif name in ["CHATGPT", "CLAUDE", "GEMINI", "LOCAL"]:
            return (1, name)  # Alphabetical order among these
        else:
            return (0, name)  # Other providers first (alphabetical)
    
    results.sort(key=sort_key)
    
    # Build provider details - sorted alphabetically (excluding LOCAL and ACTUAL)
    providers = []
    # Add 3rd party providers in alphabetical order (including openai as CHATGPT alias)
    for provider_family in ["openai", "claude", "gemini"]:
        info = provider_info.get(provider_family)
        if info and any(r.get("provider_family") == provider_family for r in last_results):
            providers.append({
                "name": info["name"],
                "model": info["model"]
            })
    # Add LOCAL provider
    if provider_info.get("local") and any(r.get("provider_family") == "local" for r in last_results):
        providers.append({
            "name": provider_info["local"]["name"],
            "model": provider_info["local"]["model"]
        })
    
    # Add ACTUAL reference time entry
    pst_time = None
    if latest_time:
        # Convert UTC to PST
        dt_utc = latest_time.replace(tzinfo=ZoneInfo("UTC")) if latest_time.tzinfo is None else latest_time
        pst_time = dt_utc.astimezone(PST).strftime("%I:%M %p")
    else:
        pst_time = "--:-- PST"
    
    # Build final JSON structure
    output = {
        "timestamp": latest_time.isoformat() if latest_time else None,
        "models": results,
        "providers": providers,
        "actual_time": pst_time
    }
    
    # Write to file atomically
    results_file = ASSETS_DIR / "last-guess.json"
    temp_file = ASSETS_DIR / "last-guess.json.tmp"
    
    with open(temp_file, "w") as f:
        json.dump(output, f, indent=2)
        
    temp_file.replace(results_file)
    
    print(f"📊 Inference results exported to {results_file}")
    return output

def get_stats_text(stats) -> str:
    """Format stats into a readable text string for OBS text sources."""
    overall_pct = stats["overall"]["accuracy"] * 100
    overall_total = stats["overall"]["total"]
    
    text = f"OVERALL ACCURACY: {overall_pct:.1f}% ({overall_total} inferences)\n\n"
    text += "MODELS:\n"
    
    for model, m_stats in stats["models"].items():
        pct = m_stats["24h"] * 100
        total = m_stats["total"]
        pct_1h = m_stats["1h"] * 100
        text += f"• {model}: {pct:.1f}% ({total}) [1h: {pct_1h:.1f}%]\n"
        
    return text
