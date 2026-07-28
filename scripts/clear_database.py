#!/usr/bin/env python3
"""
Clear all rows from the database.

Usage:
    uv run python scripts/clear_database.py
    uv run python scripts/clear_database.py --force

The script will ask for confirmation by typing 'delete' before proceeding.
Use --force to skip confirmation (use with caution!).
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_database, cleanup_database, get_dev_database, get_prod_database


def main():
    parser = argparse.ArgumentParser(
        description="Clear all rows from the database"
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
    db_path = db.db_path

    print("=" * 60)
    print("⚠️  WARNING: This will delete ALL rows from the database!")
    print("=" * 60)
    print(f"Database path: {db_path}")
    print()

    if not args.force:
        # Ask for confirmation
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

    print()

    # Show row counts before clearing
    cursor = db._conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM inference_results")
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("✅ Database is already empty")
        return 0

    print(f"⚠️  About to delete {count} row(s)")
    print()

    if not args.force:
        print("To confirm, type 'delete' again:")
        print("> ", end="", flush=True)
        
        try:
            response = input().strip().lower()
        except EOFError:
            print("\n❌ No input received, aborting")
            return 1

        if response != "delete":
            print(f"❌ Invalid response: '{response}'. Expected 'delete'. Aborting.")
            return 1

    # Clear the database
    cursor.execute("DELETE FROM inference_results")
    db._conn.commit()

    print()
    print("✅ Database cleared successfully!")
    print(f"   Rows deleted: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
