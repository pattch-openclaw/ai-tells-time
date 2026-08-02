#!/usr/bin/env python3
"""
Record inference results to the database for testing and debugging.

Usage:
    uv run python scripts/record_inference.py --model gemini-1.5-flash --guess "12:34" --actual "12:29" --is-accurate
    uv run python scripts/record_inference.py --model local --guess "3:15" --actual "3:45" --not-accurate
"""

import argparse
import sys
from datetime import datetime, timedelta
import zoneinfo
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_database, cleanup_database, get_dev_database, get_prod_database


def parse_time(time_str: str, reference_time: datetime = None) -> datetime:
    """Parse time string in HH:MM format."""
    if reference_time is None:
        # Use PST timezone (America/Los_Angeles) for consistency
        reference_time = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
    
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        return reference_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (ValueError, IndexError):
        raise ValueError(f"Invalid time format: {time_str}. Use HH:MM")


def main():
    parser = argparse.ArgumentParser(
        description="Record inference results to the database"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model name (e.g., gemini-1.5-flash, local, qwen2.5vl:7b)"
    )
    parser.add_argument(
        "--guess",
        type=str,
        required=True,
        help="Time guess from the model (HH:MM format)"
    )
    parser.add_argument(
        "--actual",
        type=str,
        default=None,
        help="Actual time for comparison (HH:MM format). Defaults to current time."
    )
    parser.add_argument(
        "--is-accurate",
        action="store_true",
        help="Mark as accurate (within ±5 minutes)"
    )
    parser.add_argument(
        "--not-accurate",
        action="store_true",
        help="Mark as inaccurate (outside ±5 minutes)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Provider family (gemini, openai, claude, local). Defaults to auto-detect."
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Path to captured image file"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Use production database instead of dev"
    )

    args = parser.parse_args()

    # Validate accuracy flag
    if args.is_accurate and args.not_accurate:
        print("❌ Cannot mark as both accurate and inaccurate")
        return 1

    # Parse times
    try:
        now = datetime.now()
        guess_dt = parse_time(args.guess, now)
        actual_dt = parse_time(args.actual, now) if args.actual else now
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    # Calculate offset and accuracy
    # Convert both times to minutes from midnight (0-1439 range)
    actual_total_minutes = actual_dt.hour * 60 + actual_dt.minute
    guess_total_minutes = guess_dt.hour * 60 + guess_dt.minute
    
    # Calculate raw difference
    diff = guess_total_minutes - actual_total_minutes
    
    # The minimum offset is the minimum of the direct difference
    # and the wrap-around difference (going through midnight).
    # Since there are 1440 minutes in a day, the wrap-around distance is 1440 - |diff|
    offset_minutes = min(abs(diff), 1440 - abs(diff))
    
    is_accurate = args.is_accurate or (offset_minutes <= 5 and not args.not_accurate)

    # Determine provider family from model name
    provider = args.provider
    if not provider:
        if "gemini" in args.model.lower():
            provider = "gemini"
        elif "openai" in args.model.lower() or "gpt" in args.model.lower():
            provider = "openai"
        elif "claude" in args.model.lower():
            provider = "claude"
        elif "local" in args.model.lower() or "ollama" in args.model.lower():
            provider = "local"
        else:
            provider = "unknown"

    # Determine database
    db = get_prod_database() if args.prod else get_dev_database()

    try:
        # Save the inference result
        result_id = db.save_inference_result(
            reference_system_time=actual_dt,
            model_name=args.model,
            provider_family=provider,
            time_guess=args.guess,
            inference_failure=False,
            captured_image_filename=args.image,
            parsed_time=guess_dt,
            guessed_offset_minutes=offset_minutes,
            is_accurate=is_accurate,
            webcam_model="Logitech C920",
            clock_model="Analog Wall Clock",
        )

        print(f"✅ Saved inference result (ID: {result_id})")
        print(f"   Model: {args.model}")
        print(f"   Provider: {provider}")
        print(f"   Guess: {args.guess}")
        print(f"   Actual: {actual_dt.strftime('%H:%M')}")
        print(f"   Offset: {offset_minutes} minutes")
        print(f"   Accurate: {is_accurate}")

        # Show current accuracy stats
        recent = db.get_recent_accuracy(hours=1)
        overall = db.get_overall_accuracy()

        print(f"\n📊 Current Accuracy Stats:")
        print(f"   Recent (last hour): {recent:.1%}")
        print(f"   Overall: {overall:.1%}")

    finally:
        cleanup_database()

    return 0


if __name__ == "__main__":
    sys.exit(main())
