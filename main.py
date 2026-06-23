import asyncio
import time
from datetime import datetime
import obsws_python as obs
import os
from pathlib import Path
from dotenv import load_dotenv
from src.capture import capture_clock_image

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

# Debug: print loaded values (password hidden)
print(f"Config loaded from {config_path}:")
print(f"  HOST: {OBS_HOST}")
print(f"  PORT: {OBS_PORT}")
print(f"  PASSWORD: {'***' if OBS_PASSWORD else '(empty)'}")
print(f"  RESOLUTION: {CAPTURE_RESOLUTION[0]}x{CAPTURE_RESOLUTION[1]}")


async def main_loop():
    print(f"Starting AI Tells Time...")
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
        current_time_str = now.strftime("%H:%M:%S")
        
        try:
            image_path = await capture_clock_image(resolution=CAPTURE_RESOLUTION)
            print(f"Image saved to: {image_path}")
        except Exception as e:
            print(f"❌ Error capturing image: {e}")
            # Continue anyway if capture fails
            pass
        
        # 2. Update OBS (if connected)
        if client:
            try:
                # Update the 'text_gpt' source
                new_text = f"Time: {current_time_str}"
                client.set_input_settings("text_gpt", {"text": new_text}, True)
                print(f"✅ OBS text_gpt updated to: '{new_text}'")
            except Exception as e:
                print(f"❌ Error updating OBS text: {e}")

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
