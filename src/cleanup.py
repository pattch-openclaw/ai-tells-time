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

def main():
    print("Starting cleanup routine...")
    
    purge_directory(TEMP_DIR)
    purge_directory(OUTPUT_DIR)
    
    print("Cleanup complete.")

if __name__ == "__main__":
    main()
