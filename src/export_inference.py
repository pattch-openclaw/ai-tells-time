#!/usr/bin/env -S uv run
"""Export inference results to JSON for OBS Browser Source."""

import asyncio
from pathlib import Path
from dotenv import load_dotenv
from src.database import get_prod_database, get_dev_database
from src.stats import export_inference_results


def parse_args():
    """Parse command line arguments."""
    import argparse
    parser = argparse.ArgumentParser(description="Export inference results to JSON")
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Use production database instead of dev"
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    
    # Load config
    config_path = Path.home() / ".config" / "ai-tells-time" / ".env"
    if config_path.exists():
        print(f"Loading config from {config_path}...")
        load_dotenv(config_path)
    
    # Get database
    db = get_prod_database() if args.prod else get_dev_database()
    
    print(f"Using {'PROD' if args.prod else 'DEV'} database: {db.db_path}")
    
    # Export inference results
    data = export_inference_results(db)
    
    print(f"\\nExported {len(data['models'])} model results:")
    for model in data['models']:
        accuracy = model['accuracy'] * 100
        status = "✅" if accuracy >= 50 else "❌"
        print(f"  {status} {model['name']}: {accuracy:.1f}% ({model['guess']})")
    
    if data['providers']:
        print(f"\\nProviders configured: {len(data['providers'])}")
        for p in data['providers']:
            print(f"  - {p['name']}: {p['model']}")


if __name__ == "__main__":
    asyncio.run(main())
