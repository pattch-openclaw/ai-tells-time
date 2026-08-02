import asyncio
import time
import argparse
from datetime import datetime
import obsws_python as obs
import os
from pathlib import Path
from dotenv import load_dotenv
from src.capture import capture_clock_image
from src.inference import get_provider, BaseInferenceProvider
from src.database import cleanup_database, get_dev_database, get_prod_database

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


def record_inference_results(results, reference_time, db, image_path):
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
            parsed_time = provider.parse_response_sync(time_result)
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
                    # Parse the time string to a datetime object
                    guess_parts = parsed_time.split(":")
                    guess_hour = int(guess_parts[0])
                    guess_minute = int(guess_parts[1])
                    parsed_dt = reference_time.replace(hour=guess_hour, minute=guess_minute, second=0, microsecond=0)

                    # Calculate offset in minutes (absolute value)
                    offset_seconds = abs((parsed_dt - reference_time).total_seconds())
                    offset_minutes = int(offset_seconds / 60)

                    # Consider accurate if within +/- 5 minutes
                    is_accurate = offset_minutes <= 5
                except Exception as e:
                    print(f"⚠️ Could not calculate offset for {provider.name}: {e}")

            # Determine provider_family from provider name
            provider_family = provider.name if provider.name in KNOWN_PROVIDER_FAMILIES else "other"

            # Save to database
            db.save_inference_result(
                reference_system_time=reference_time,
                model_name=provider.name,
                provider_family=provider_family,
                time_guess=time_result,
                inference_failure=inference_failure,
                captured_image_filename=str(image_path),
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
        now = datetime.now()
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
                record_inference_results(results, now, db, image_path)

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

        # 3. Calculate sleep time to align exactly with the top of the next minute
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
