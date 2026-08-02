#!/usr/bin/env python3
"""
Cleanup routine for the AI Tells Time project.
Deletes temporary clock images from known temporary and output folders.
Can also clear the database when --clear-db is specified.
"""

import shutil
import argparse
from pathlib import Path

# Import folder constants from capture to keep them synced
from src.capture import TEMP_DIR, OUTPUT_DIR

# Import database utilities
from src.database import get_dev_database, get_prod_database, get_database, cleanup_database


def purge_directory(directory: Path) -> None:
    """Deletes the contents of the directory without deleting the directory itself."""
    if directory.exists() and directory.is_dir():
        print(f"Emptying directory: {directory}")
        try:
            for item in directory.iterdir():
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            print(f"✅ Successfully emptied {directory}")
        except Exception as e:
            print(f"❌ Error emptying {directory}: {e}")
    else:
        print(f"Directory does not exist, skipping: {directory}")


def clear_database(use_prod: bool = False) -> None:
    """Clears all data from the database without deleting the database file."""
    try:
        db = get_prod_database() if use_prod else get_dev_database()
        cursor = db._conn.cursor()
        
        # Delete all rows from inference_results
        cursor.execute("DELETE FROM inference_results")
        deleted_count = cursor.rowcount
        db._conn.commit()
        
        print(f"✅ Cleared {deleted_count} rows from {'production' if use_prod else 'development'} database")
        
        # Reset the auto-increment counter
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='inference_results'")
        db._conn.commit()
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cleanup routine for AI Tells Time project"
    )
    parser.add_argument(
        "--clear-db",
        action="store_true",
        help="Clear all data from the database (development database by default)"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Use production database with --clear-db flag"
    )
    
    args = parser.parse_args()
    
    print("Starting cleanup routine...")
    
    purge_directory(TEMP_DIR)
    purge_directory(OUTPUT_DIR)
    
    if args.clear_db:
        clear_database(use_prod=args.prod)
    
    print("Cleanup complete.")


if __name__ == "__main__":
    main()
