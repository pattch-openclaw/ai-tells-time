#!/usr/bin/env python3
"""
Clear rows for specific model(s) from the database.

Usage:
    uv run python scripts/clear_models.py --model test-model-1
    uv run python scripts/clear_models.py --model test-model-1 --model test-model-2
    uv run python scripts/clear_models.py --provider local
    uv run python scripts/clear_models.py --all-models --force
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_database, cleanup_database, get_dev_database, get_prod_database


def main():
    parser = argparse.ArgumentParser(
        description="Clear rows for specific model(s) from the database"
    )
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        help="Model name to clear (can be specified multiple times)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Provider family to clear (gemini, openai, claude, local)"
    )
    parser.add_argument(
        "--all-models",
        action="store_true",
        help="Clear all models (requires --force)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Use production database instead of dev"
    )

    args = parser.parse_args()

    db = get_prod_database() if args.prod else get_dev_database()

    # Validate arguments
    if not any([args.model, args.provider, args.all_models]):
        print("❌ Must specify --model, --provider, or --all-models")
        return 1

    if args.all_models and not args.force:
        print("❌ --all-models requires --force to prevent accidental deletion")
        return 1

    # Build query
    query = "DELETE FROM inference_results WHERE 1=1"
    params = []
    
    if args.model:
        # Create placeholders for IN clause
        placeholders = ",".join("?" * len(args.model))
        query += f" AND model_name IN ({placeholders})"
        params.extend(args.model)
    
    if args.provider:
        query += " AND provider_family = ?"
        params.append(args.provider)

    # Show what will be deleted
    cursor = db._conn.cursor()
    
    # Count rows that will be deleted
    count_query = query.replace("DELETE FROM inference_results", "SELECT COUNT(*) FROM inference_results")
    cursor.execute(count_query, params)
    count = cursor.fetchone()[0]

    if count == 0:
        print("✅ No rows match the criteria")
        return 0

    # Build criteria string for display
    criteria_parts = []
    if args.model:
        criteria_parts.append(f"model: {', '.join(args.model)}")
    if args.provider:
        criteria_parts.append(f"provider: {args.provider}")
    criteria = ", ".join(criteria_parts)

    print("=" * 60)
    print(f"⚠️  WARNING: This will delete {count} row(s)")
    print("=" * 60)
    print(f"Criteria: {criteria}")
    print()

    if not args.force:
        print("To confirm deletion, type 'delete' and press Enter:")
        print("> ", end="", flush=True)
        
        try:
            response = input().strip().lower()
        except EOFError:
            print("\n❌ No input received, aborting")
            return 1

        if response != "delete":
            print(f"❌ Invalid response: '{response}'. Expected 'delete'. Aborting.")
            return 1

    # Execute deletion
    cursor.execute(query, params)
    db._conn.commit()

    print()
    print("✅ Rows cleared successfully!")
    print(f"   Rows deleted: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
