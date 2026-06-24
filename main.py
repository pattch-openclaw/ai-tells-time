import asyncio
import time
import argparse
from datetime import datetime
import obsws_python as obs
import os
from pathlib import Path
from dotenv import load_dotenv
from src.capture import capture_clock_image
from src.inference import get_provider

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

# Image capture settings
CAPTURE_RESOLUTION = (854, 480)  # (width, height)

# Available providers (all implemented providers)
ALL_PROVIDERS = ["gemini", "ollama", "openai"]  # Future: ["openai", "claude"]


def ensure_ollama_running():
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


# Debug: print loaded values (password hidden)
print(f"Config loaded from {config_path}:")
print(f"  HOST: {OBS_HOST}")
print(f"  PORT: {OBS_PORT}")
print(f"  PASSWORD: {'***' if OBS_PASSWORD else '(empty)'}")
print(f"  RESOLUTION: {CAPTURE_RESOLUTION[0]}x{CAPTURE_RESOLUTION[1]}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments for provider selection."""
    parser = argparse.ArgumentParser(description="AI Tells Time - Broadcast system")
    
    # Provider selection flags
    parser.add_argument(
        "--providers",
        type=str,
        nargs="*",
        default=None,
        help="List of providers to enable. Options: gemini, ollama, openai. Defaults to all implemented (gemini + ollama + openai)."
    )
    
    # Ollama model selection
    parser.add_argument(
        "--ollama-model",
        type=str,
        default="qwen2.5vl:7b",
        help="Ollama model to use (default: qwen2.5vl:7b)"
    )
    
    args = parser.parse_args()
    
    # If no providers specified, use all implemented
    if args.providers is None:
        return args
    
    # Validate and filter providers
    valid_providers = set(ALL_PROVIDERS)
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


async def run_inference_for_provider(provider, image_path: Path) -> tuple[str, str]:
    """Run inference for a single provider and return (provider_name, time_str)."""
    try:
        print(f"Asking {provider.name} for the time...")
        raw_response = await provider.tell_time(image_path)
        parsed_time = await provider.parse_response(raw_response)
        
        if parsed_time:
            print(f"🤖 {provider.name} thinks the time is: {parsed_time}")
            return provider.name, parsed_time
        else:
            print(f"⚠️ Failed to parse {provider.name} response. Raw: {raw_response}")
            return provider.name, "Error parsing time"
    except Exception as e:
        print(f"❌ Error running inference for {provider.name}: {e}")
        return provider.name, "Error"


async def main_loop():
    print(f"Starting AI Tells Time...")
    
    # Parse command line arguments for provider selection
    args = parse_args()
    
    # Check Ollama status if ollama provider is enabled
    providers_to_check = args.providers if args.providers else ALL_PROVIDERS
    if "ollama" in providers_to_check:
        ensure_ollama_running()
    
    # Initialize AI Providers
    providers = []
    providers_to_use = args.providers if args.providers else ALL_PROVIDERS
    
    print(f"Initializing providers: {providers_to_use}")
    
    for provider_name in providers_to_use:
        try:
            if provider_name == "ollama":
                provider = get_provider(provider_name, model=args.ollama_model)
            else:
                provider = get_provider(provider_name)
            providers.append(provider)
            print(f"✅ Initialized AI provider: {provider.name}")
            if provider_name == "ollama":
                print(f"   Using model: {args.ollama_model}")
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
    except Exception as e:
        print(f"⚠️ Failed to connect to OBS. Is it running? Error: {e}")
        print("We will run the loop anyway, but OBS text updates will be skipped.")
        client = None

    print("\nStarting the 60-second broadcast loop...")
    
    while True:
        # 1. Capture an image from OBS
        now = datetime.now()
        current_time_str = now.strftime("%H:%M:%S")  # Default fallback time
        
        try:
            image_path = await capture_clock_image(resolution=CAPTURE_RESOLUTION)
            print(f"Image saved to: {image_path}")
            
            # Run all AI providers concurrently, updating OBS as each completes
            if providers:
                # First, update OBS with "Provider: ..." for all providers
                for provider in providers:
                    obs_text = f"{provider.name.upper()}: ..."
                    try:
                        client.set_input_settings(f"text_{provider.name}", {"text": obs_text}, True)
                        print(f"🔄 OBS text_{provider.name} set to: '{obs_text}'")
                    except Exception as e:
                        print(f"⚠️ Could not update OBS text_{provider.name}: {e}")
                
                # Run inference tasks concurrently, update OBS as each completes
                tasks = [run_inference_for_provider(p, image_path) for p in providers]
                for completed_task in asyncio.as_completed(tasks):
                    provider_name, time_result = await completed_task
                    obs_text = f"{provider_name.upper()}: {time_result}"
                    try:
                        client.set_input_settings(f"text_{provider_name}", {"text": obs_text}, True)
                        print(f"✅ OBS text_{provider_name} updated to: '{obs_text}'")
                    except Exception as e:
                        print(f"❌ Error updating OBS text_{provider_name}: {e}")
                
                # Use the first result as primary time
                current_time_str = time_result
                    
        except Exception as e:
            print(f"❌ Error capturing image or running inference: {e}")
            current_time_str = "Error"
            # Continue anyway if capture fails
            pass
        
        # 2. Update primary provider's OBS source (if connected)
        if client and providers and results:
            primary_provider = results[0][0]
            try:
                obs_text = f"{primary_provider.upper()}: {current_time_str}"
                client.set_input_settings(f"text_{primary_provider}", {"text": obs_text}, True)
                print(f"✅ OBS text_{primary_provider} updated to: '{obs_text}'")
            except Exception as e:
                print(f"❌ Error updating OBS text_{primary_provider}: {e}")

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
