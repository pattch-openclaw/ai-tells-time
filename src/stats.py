import json
from pathlib import Path
from datetime import datetime, timezone
import os

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
    
    # Optional: fetch 1h, 24h, overall for each model
    for model in models:
        stats["models"][model] = {
            "1h": db.get_recent_accuracy(hours=1, model_name=model),
            "24h": db.get_recent_accuracy(hours=24, model_name=model),
            "overall": db.get_overall_accuracy(model_name=model),
            "total": db.get_total_inferences(model_name=model)
        }
        
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
