import asyncio
import time
import argparse
from datetime import datetime, timedelta
import zoneinfo
import obsws_python as obs
import os
from pathlib import Path
from dotenv import load_dotenv
from src.capture import capture_clock_image
from src.inference import get_provider, BaseInferenceProvider
from src.database import cleanup_database, get_dev_database, get_prod_database, get_database
from src.stats import export_stats, get_stats_text

# Load environment variables from ~/.config/ai-tells-time/.env (secure location)
config_path = Path.home() / ".config" / "ai-tells-time" / ".env"
if config_path.exists():
    print(f"Loading config from {config_path}...")
    load_dotenv(config_path)
else:
    print(f"Config file not found at {config_path}, falling back to project directory...")
    load_dotenv()

OBS_HOST = os.getenv("OBS_WEBSOCKET_HOST", "localhost")
OBS_PORT = os.getenv("OBS_WEBSOCKET_PORT", "4455")
OBS_PASSWORD = os.getenv("OBS_WEBSOCKET_PASSWORD", "")

# Helper functions for time offset calculation
def calculate_time_offset_minutes(ref_hour: int, ref_minute: int, guess_hour: int, guess_minute: int) -> int:
    """
    Calculate the minimum absolute time offset in minutes between two times of day.
    
    This function handles cases where the guess might be in 12-hour format (0-11)
    without AM/PM indicator. It tries both AM and PM interpretations and picks the
    one with the smaller offset.
    
    Args:
        ref_hour: Reference hour (0-23, 24-hour format)
        ref_minute: Reference minute (0-59)
        guess_hour: Guess hour (0-11 for 12-hour without AM/PM, or 0-23 for 24-hour)
        guess_minute: Guess minute (0-59)
    
    Returns:
        Minimum absolute offset in minutes (always >= 0 and <= 720)
    """
    # Convert reference to minutes from midnight
    ref_total = ref_hour * 60 + ref_minute
    
    # Try both AM (0-11) and PM (12-23) interpretations of the guess
    def calc_offset_for_guess_hour(h):
        guess_total = h * 60 + guess_minute
        diff = guess_total - ref_total
        diff_abs = abs(diff)
        return min(diff_abs, 1440 - diff_abs)  # Wrap around midnight
    
    # For guesses 0-11, try both AM and PM interpretations
    if guess_hour < 12:
        offset_am = calc_offset_for_guess_hour(guess_hour)  # Keep as AM (0-11)
        offset_pm = calc_offset_for_guess_hour(guess_hour + 12)  # Try PM (12-23)
        offset = min(offset_am, offset_pm)
    else:
        # For guesses 12-23, use as-is (already in 24-hour format)
        offset = calc_offset_for_guess_hour(guess_hour)
    
    # Defensive assertion: offset should always be in [0, 720]
    # (max offset is 720 minutes = 12 hours for times 12 hours apart)
    assert 0 <= offset <= 720, f"Offset {offset} is outside expected range [0, 720]"
    
    return offset


def get_parsed_datetime_for_guess(
    reference_time: datetime,
    guess_hour: int,
    guess_minute: int
) -> datetime:
    """
    Create a datetime for the guessed time that minimizes the offset from reference.
    
    Args:
        reference_time: The reference datetime (timezone-aware or naive)
        guess_hour: Guess hour (0-23)
        guess_minute: Guess minute (0-59)
    
    Returns:
        A datetime object representing the guessed time on the appropriate day
        (previous, same, or next day) to minimize the offset
    """
    ref_total = reference_time.hour * 60 + reference_time.minute
    guess_total = guess_hour * 60 + guess_minute
    diff = guess_total - ref_total
    
    if abs(diff) <= 720:
        # Direct path is shorter (or equal), use same day
        parsed_dt = reference_time.replace(
            hour=guess_hour, minute=guess_minute, second=0, microsecond=0
        )
    elif diff > 0:
        # Wrap-around is shorter and guess is ahead, so use previous day
        parsed_dt = reference_time.replace(
            hour=guess_hour, minute=guess_minute, second=0, microsecond=0
        )
        parsed_dt = parsed_dt - timedelta(days=1)
    else:
        # Wrap-around is shorter and guess is behind, so use next day
        parsed_dt = reference_time.replace(
            hour=guess_hour, minute=guess_minute, second=0, microsecond=0
        )
        parsed_dt = parsed_dt + timedelta(days=1)
    
    return parsed_dt


# Provider families for classification
KNOWN_PROVIDER_FAMILIES = ["openai", "gemini", "claude", "local"]

# Image capture settings
CAPTURE_RESOLUTION = (640, 360)  # (width, height) - 360p for reduced AI costs

# Add asyncio Lock for OBS to prevent overlapping writes and avoid blocking the event loop
obs_lock = asyncio.Lock()

# Global database instance for the main loop
_main_db_instance = None

async def update_obs_text(client, source, text):
    """Update OBS text source safely in a background thread to prevent blocking the async loop."""
    if not client: return
    async with obs_lock:
        try:
            await asyncio.to_thread(client.set_input_settings, source, {"text": text}, True)
        except Exception as e:
            print(f"⚠️ Could not update OBS {source}: {e}")

# Available providers (all implemented providers)
ALL_PROVIDERS = ["gemini", "local", "openai", "claude"]

# External providers (non-local, more expensive)
EXTERNAL_PROVIDERS = ["gemini", "openai", "claude"]


def ensure_local_running():
    """Ensure Ollama server is running before starting the app."""
    try:
        import subprocess
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            print("⚠️  Ollama appears to not be running. Please start Ollama with: ollama serve &")
        else:
            print("✅ Ollama is running")
    except FileNotFoundError:
        print("⚠️  Ollama not found in PATH. Install with: curl -fsSL https://ollama.com/install.sh | sh")
    except Exception as e:
        print(f"⚠️  Could not check Ollama status: {e}")


async def record_inference_results(results, reference_time, db, image_path):
    """
    Record inference results to the database.
    
    This helper method is called from the main loop to record results for each provider.
    It handles all database errors gracefully to prevent crashes.
    
    Args:
        results: List of (provider, time_result) tuples from inference
        reference_time: The time when the image was captured
        db: Database instance
        image_path: Path to the captured image
    """
    
    for provider, time_result in results:
        try:
            # Parse the time guess to calculate offset
            parsed_time = await provider.parse_response(time_result)
            offset_minutes = None
            is_accurate = False
            inference_failure = False

            if parsed_time is None:
                # Failed to parse - this is an inference failure
                inference_failure = True
                print(f"⚠️ Could not parse {provider.name} response: '{time_result}'")
            else:
                # Calculate offset from actual reference time
                try:
                    # Parse the time string to get hour and minute
                    guess_parts = parsed_time.split(":")
                    guess_hour = int(guess_parts[0])
                    guess_minute = int(guess_parts[1])
                    
                    # Calculate offset using the helper function
                    offset_minutes = calculate_time_offset_minutes(
                        reference_time.hour, reference_time.minute,
                        guess_hour, guess_minute
                    )
                    
                    # Create the parsed datetime for the guessed time
                    parsed_dt = get_parsed_datetime_for_guess(
                        reference_time, guess_hour, guess_minute
                    )

                    # Consider accurate if within +/- 5 minutes
                    is_accurate = offset_minutes <= 5
                except Exception as e:
                    print(f"⚠️ Could not calculate offset for {provider.name}: {e}")

            # Determine provider_family from provider name
            provider_family = provider.name if provider.name in KNOWN_PROVIDER_FAMILIES else "other"

            # Extract just the filename from the path for database storage
            image_filename = image_path.name if image_path else None

            # Save to database
            db.save_inference_result(
                reference_system_time=reference_time,
                model_name=provider.name,
                provider_family=provider_family,
                time_guess=time_result,
                inference_failure=inference_failure,
                captured_image_filename=image_filename,
                parsed_time=parsed_dt if parsed_time else None,
                guessed_offset_minutes=offset_minutes,
                is_accurate=is_accurate,
                webcam_model="Logitech C920",
                clock_model="Analog Wall Clock",
            )

            if not inference_failure:
                print(f"📊 {provider.name}: offset={offset_minutes}min, accurate={is_accurate}")
            else:
                print(f"❌ {provider.name}: inference failure (could not parse response)")

        except Exception as e:
            print(f"⚠️ Error recording {provider.name} to database: {e}")
            # Don't fail the entire run if database recording fails


# Debug: print loaded values (password hidden)
print(f"Config loaded from {config_path}:")
print(f"  HOST: {OBS_HOST}")
print(f"  PORT: {OBS_PORT}")
print(f"  PASSWORD: {'***' if OBS_PASSWORD else '(empty)'}")
print(f"  RESOLUTION: {CAPTURE_RESOLUTION[0]}x{CAPTURE_RESOLUTION[1]}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for provider selection and database environment."""
    parser = argparse.ArgumentParser(description="AI Tells Time - Broadcast system")

    # Provider selection flags
    parser.add_argument(
        "--providers",
        type=str,
        nargs="*",
        default=None,
        help="List of providers to enable. Options: gemini, local, openai, claude. Defaults to all implemented (gemini + local + openai + claude)."
    )

    # Local model selection
    parser.add_argument(
        "--local-model",
        type=str,
        default="qwen2.5vl:7b",
        help="Local model to use (default: qwen2.5vl:7b)"
    )

    # Inference frequency mode
    parser.add_argument(
        "--every-minute",
        action="store_true",
        help="Run all providers every minute (default: only external providers every 5 min, local every min)"
    )

    # Database environment selection
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Use production database instead of dev"
    )

    args = parser.parse_args()

    # If no providers specified, use all implemented
    if args.providers is None:
        return args

    # Validate and filter providers
    valid_providers = {"gemini", "local", "openai", "claude"}
    selected = set(p.lower() for p in args.providers)
    invalid = selected - valid_providers

    if invalid:
        print(f"⚠️  Unknown providers: {invalid}")
        print(f"   Valid options: {valid_providers}")
        print(f"   Using all implemented providers: {ALL_PROVIDERS}")
        args.providers = ALL_PROVIDERS
    else:
        args.providers = list(selected)

    return args


async def run_inference_for_provider(provider: BaseInferenceProvider, image_path: Path) -> tuple[BaseInferenceProvider, str]:
    """Run inference for a single provider and return (provider, time_str)."""
    try:
        # Yield briefly so all tasks hit this point roughly at the same time
        await asyncio.sleep(0)
        print(f"Asking {provider.name} for the time...")
        raw_response = await provider.tell_time(image_path)
        parsed_time = await provider.parse_response(raw_response)

        if parsed_time:
            print(f"🤖 {provider.name} thinks the time is: {parsed_time}")
            return provider, parsed_time
        else:
            print(f"⚠️ Failed to parse {provider.name} response. Raw: {raw_response}")
            return provider, "Error parsing time"
    except Exception as e:
        print(f"❌ Error running inference for {provider.name}: {e}")
        return provider, "Error"


async def main_loop():
    print(f"Starting AI Tells Time...")

    # Parse command line arguments for provider selection
    args = parse_args()

    # Check Local status if local provider is enabled
    providers_to_check = args.providers if args.providers else ALL_PROVIDERS
    if "local" in providers_to_check:
        ensure_local_running()

    # Initialize AI Providers
    providers = []
    providers_to_use = args.providers.copy() if args.providers else ALL_PROVIDERS.copy()
    
    # Always ensure reference provider runs
    if "reference" not in providers_to_use:
        providers_to_use.append("reference")

    print(f"Initializing providers: {providers_to_use}")

    for provider_name in providers_to_use:
        try:
            if provider_name == "local":
                provider = get_provider(provider_name, model=args.local_model)
            else:
                provider = get_provider(provider_name)
            providers.append(provider)
            print(f"✅ Initialized AI provider: {provider.name}")
            if provider_name == "local":
                print(f"   Using model: {args.local_model}")
        except Exception as e:
            print(f"❌ Failed to initialize AI provider {provider_name}: {e}")

    if not providers:
        print("⚠️ No AI providers initialized. Will fall back to system time.")
    else:
        print(f"✅ Total providers ready: {len(providers)}")

    print(f"Attempting to connect to OBS at {OBS_HOST}:{OBS_PORT}...")

    try:
        # Connect to the OBS WebSocket
        client = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
        print("✅ Connected to OBS successfully!")
        
        # Update text_details source with initialized models
        if providers:
            details_text = "Model Details:\n"
            for provider in providers:
                details_text += f"{provider.get_model_detail_string()}\n"
                
            try:
                client.set_input_settings("text_details", {"text": details_text.strip()}, True)
                print("✅ OBS text_details updated with model information")
            except Exception as e:
                print(f"⚠️ Could not update OBS text_details: {e}")
                
    except Exception as e:
        print(f"⚠️ Failed to connect to OBS. Is it running? Error: {e}")
        print("We will run the loop anyway, but OBS text updates will be skipped.")
        client = None

    # Initialize database
    db = get_prod_database() if args.prod else get_dev_database()
    db_path = db.db_path
    db_env = "PROD" if args.prod else "DEV"
    print(f"✅ Database connection initialized ({db_env}): {db_path}")

    print("\nStarting the 60-second broadcast loop...")
    print(f"Inference mode: {'All providers every minute' if args.every_minute else 'Local every minute, external every 5 minutes'}")

    # Store db for use in record_inference_results
    global _main_db_instance
    _main_db_instance = db

    run_count = 0
    while True:
        run_count += 1
        # 1. Capture an image from OBS
        # Use PST timezone (America/Los_Angeles) to match the ReferenceProvider
        now = datetime.now(zoneinfo.ZoneInfo("America/Los_Angeles"))
        current_time_str = now.strftime("%H:%M:%S")  # Default fallback time

        try:
            image_path = await capture_clock_image(resolution=CAPTURE_RESOLUTION, crop_center=True)
            print(f"Image saved to: {image_path}")

            # Determine which providers to run this iteration
            if args.every_minute or run_count % 5 == 1:  # Run all providers on first run and every 5th run
                providers_to_run = providers
                print(f"🔄 Running all {len(providers)} providers (run #{run_count})...")
            else:
                # Only run local and reference providers on intermediate minutes
                providers_to_run = [p for p in providers if p.name in ["local", "reference"]]
                if providers_to_run:
                    print(f"🔄 Running local and reference providers (run #{run_count})...")
                else:
                    print(f"⚠️ No intermediate providers available for run #{run_count}")

            # Run all AI providers concurrently, updating OBS as each completes
            if providers_to_run:
                # Sort providers so reference is always first
                providers_to_run.sort(key=lambda p: 0 if p.name == "reference" else 1)

                # First, update OBS with "Provider: ..." for all providers
                async def set_waiting(provider):
                    # Determine OBS source name
                    if provider.name == "openai":
                        obs_source = "text_gpt"
                    elif provider.name == "reference":
                        obs_source = "text_actual"
                    else:
                        obs_source = f"text_{provider.name}"
                        
                    obs_text = provider.get_time_string(provider.get_placeholder_text())
                    print(f"🔄 OBS {obs_source} queueing: '{obs_text}'")
                    await update_obs_text(client, obs_source, obs_text)

                # Wait for all "..." to be queued to OBS concurrently
                await asyncio.gather(*(set_waiting(p) for p in providers_to_run))

                # Run inference tasks concurrently by scheduling them all at once
                tasks = [asyncio.create_task(run_inference_for_provider(p, image_path)) for p in providers_to_run]
                
                results = []
                for completed_task in asyncio.as_completed(tasks):
                    provider, time_result = await completed_task
                    results.append((provider, time_result))
                    
                    # Determine OBS source name
                    if provider.name == "openai":
                        obs_source = "text_gpt"
                    elif provider.name == "reference":
                        obs_source = "text_actual"
                    else:
                        obs_source = f"text_{provider.name}"
                        
                    obs_text = provider.get_time_string(time_result)
                    print(f"✅ OBS {obs_source} queueing: '{obs_text}'")
                    # Fire and forget the OBS update to not block the next provider result
                    asyncio.create_task(update_obs_text(client, obs_source, obs_text))

                # Use the first non-reference result as primary time
                if results:
                    non_ref_results = [r for r in results if r[0].name != "reference"]
                    if non_ref_results:
                        _, time_result = non_ref_results[0]
                        current_time_str = time_result

                # Record inference results to database
                await record_inference_results(results, now, db, image_path)

        except Exception as e:
            print(f"❌ Error capturing image or running inference: {e}")
            current_time_str = "Error"
            # Continue anyway if capture fails
            pass

        # 2. Update primary provider's OBS source (if connected)
        if client and results:
            non_ref_results = [r for r in results if r[0].name != "reference"]
            if non_ref_results:
                primary_provider, time_result = non_ref_results[0]
                obs_source = "text_gpt" if primary_provider.name == "openai" else f"text_{primary_provider.name}"
                obs_text = primary_provider.get_time_string(time_result)
                print(f"✅ OBS primary {obs_source} queueing: '{obs_text}'")
                await update_obs_text(client, obs_source, obs_text)

        
        # 3. Export stats for OBS Browser Source and update text
        try:
            stats = export_stats()
            stats_text = get_stats_text(stats)
            print(f"📊 Stats updated. Overall accuracy: {stats['overall']['accuracy']*100:.1f}%")
            
            if client:
                await update_obs_text(client, "text_stats", stats_text)
        except Exception as e:
            print(f"⚠️ Failed to export stats: {e}")

        # 4. Calculate sleep time to align exactly with the top of the next minute
        current_seconds = time.time() % 60
        sleep_time = 60 - current_seconds

        print(f"Sleeping for {sleep_time:.2f} seconds until the next minute (the :00 mark)...")
        await asyncio.sleep(sleep_time)


if __name__ == "__main__":
    try:
        # Run the asynchronous loop
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nShutting down AI Tells Time loop. Goodbye!")
    finally:
        cleanup_database()  # Ensure database connection is closed cleanly
