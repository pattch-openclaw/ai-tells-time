import json
from pathlib import Path
from datetime import datetime, timezone
import os
from collections import defaultdict

from src.database import get_database

ASSETS_DIR = Path(__file__).parent.parent / "obs-assets"

def export_stats(db=None):
    """Export current accuracy stats to JSON for the OBS Browser Source."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    db = db or get_database()
    
    models = db.get_active_models()
    
    stats = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "accuracy": db.get_overall_accuracy(),
            "total": db.get_total_inferences()
        },
        "models": {}
    }
    
    # Fetch 24h accuracy for each model (consolidated from 1h/24h/all)
    for model in models:
        stats["models"][model] = {
            "24h": db.get_recent_accuracy(hours=24, model_name=model),
            "total": db.get_total_inferences(model_name=model)
        }
        
    # Fetch offset data for the last hour (for line chart)
    offset_data = db.get_offset_over_time(hours=1)
    
    # Group offsets by model
    offsets_by_model = defaultdict(list)
    for item in offset_data:
        # Convert ISO format timestamp to something JSON can handle
        ts = item["timestamp"]
        if isinstance(ts, str):
            ts = ts
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

def get_stats_text(stats) -> str:
    """Format stats into a readable text string for OBS text sources."""
    overall_pct = stats["overall"]["accuracy"] * 100
    overall_total = stats["overall"]["total"]
    
    text = f"OVERALL ACCURACY: {overall_pct:.1f}% ({overall_total} inferences)\n\n"
    text += "MODELS:\n"
    
    for model, m_stats in stats["models"].items():
        pct = m_stats["overall"] * 100
        total = m_stats["total"]
        pct_1h = m_stats["1h"] * 100
        text += f"• {model}: {pct:.1f}% ({total}) [1h: {pct_1h:.1f}%]\n"
        
    return text
