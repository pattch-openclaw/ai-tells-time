#!/usr/bin/env python3
"""
Cleanup routine for the AI Tells Time project.
Deletes temporary clock images from known temporary and output folders.
"""

import shutil
from pathlib import Path

# Import folder constants from capture to keep them synced
from src.capture import TEMP_DIR, OUTPUT_DIR

def purge_directory(directory: Path) -> None:
    """Deletes the directory and its contents."""
    if directory.exists() and directory.is_dir():
        print(f"Cleaning up directory: {directory}")
        try:
            shutil.rmtree(directory)
            print(f"✅ Successfully deleted {directory}")
        except Exception as e:
            print(f"❌ Error deleting {directory}: {e}")
    else:
        print(f"Directory does not exist, skipping: {directory}")

def main():
    print("Starting cleanup routine...")
    
    purge_directory(TEMP_DIR)
    purge_directory(OUTPUT_DIR)
    
    print("Cleanup complete.")

if __name__ == "__main__":
    main()
