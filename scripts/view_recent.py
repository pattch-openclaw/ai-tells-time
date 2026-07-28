#!/usr/bin/env python3
"""
View recent inference results from the database.

Usage:
    uv run python scripts/view_recent.py
    uv run python scripts/view_recent.py --limit 10
    uv run python scripts/view_recent.py --provider local
    uv run python scripts/view_recent.py --model test-model-1
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_database, cleanup_database


def format_time(dt_str: str) -> str:
    """Format datetime string for display."""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, AttributeError):
        return dt_str


def main():
    parser = argparse.ArgumentParser(
        description="View recent inference results from the database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of rows to display (default: 20)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Filter by provider family (gemini, openai, claude, local)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Filter by specific model name"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full row data"
    )

    args = parser.parse_args()

    db = get_database()

    try:
        cursor = db._conn.cursor()
        
        query = """
            SELECT id, reference_system_time, model_name, provider_family,
                   time_guess, parsed_time, guessed_offset_minutes, is_accurate,
                   inference_failure, created_at
            FROM inference_results
            WHERE 1=1
        """
        params = []
        
        if args.provider:
            query += " AND provider_family = ?"
            params.append(args.provider)
        
        if args.model:
            query += " AND model_name = ?"
            params.append(args.model)
        
        query += " ORDER BY reference_system_time DESC LIMIT ?"
        params.append(args.limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            print("❌ No rows found matching criteria")
            return 0

        print(f"✅ Found {len(rows)} row(s)\n")

        # Print header
        if args.verbose:
            print(f"{'ID':<6} {'Time':<8} {'Model':<30} {'Provider':<10} {'Guess':<8} {'Parsed':<8} {'Offset':<8} {'Accurate':<10} {'Failed':<8}")
            print("-" * 110)
        else:
            print(f"{'ID':<6} {'Time':<8} {'Model':<30} {'Guess':<8} {'Offset':<8} {'Accurate':<10}")
            print("-" * 80)

        # Print rows
        for row in rows:
            id_ = row["id"]
            ref_time = format_time(row["reference_system_time"])
            model = row["model_name"]
            provider = row["provider_family"]
            guess = row["time_guess"]
            parsed = format_time(row["parsed_time"])
            offset = row["guessed_offset_minutes"]
            accurate = "✅" if row["is_accurate"] else "❌"
            failed = "💥" if row["inference_failure"] else "✓"
            
            if args.verbose:
                print(f"{id_:<6} {ref_time:<8} {model:<30} {provider:<10} {guess:<8} {parsed:<8} {offset:<8} {accurate:<10} {failed:<8}")
            else:
                print(f"{id_:<6} {ref_time:<8} {model[:28]:<28} {guess:<8} {offset:<8} {accurate:<10}")

        # Print summary
        print("\n" + "=" * 80)
        print("📊 Summary")
        print("=" * 80)

        # Calculate accuracy for displayed rows
        accurate_count = sum(1 for row in rows if row["is_accurate"] and not row["inference_failure"])
        total = len([r for r in rows if not r["inference_failure"]])
        
        if total > 0:
            accuracy = accurate_count / total
            print(f"   Displayed rows accuracy: {accuracy:.1%} ({accurate_count}/{total})")
        else:
            print(f"   Displayed rows accuracy: N/A (all rows failed)")

    finally:
        cleanup_database()

    return 0


if __name__ == "__main__":
    sys.exit(main())
