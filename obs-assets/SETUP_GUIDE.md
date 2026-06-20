# OBS Studio Setup Guide for "AI Tells Time"

Because this project relies heavily on Python controlling OBS in real-time, the OBS scene must be configured in a very specific way. 

Follow these steps on the Mac Mini to set up the broadcast environment.

## 1. Enable OBS WebSockets
Modern versions of OBS (v28+) have WebSockets built-in. This is how our Python script will talk to OBS.

1. Open OBS Studio.
2. In the top menu bar, go to **Tools** -> **WebSocket Server Settings**.
3. Check **Enable WebSocket server**.
4. Set the **Server Port** to `4455` (this is the default).
5. Check **Enable Authentication**.
6. Click **Generate Password** (or type a custom one). 
7. **Important:** Copy this password and paste it into your `.env` file for `OBS_WEBSOCKET_PASSWORD`.

## 2. Add the Clock (Webcam)
1. In the **Scenes** box (bottom left), click `+` to create a new scene. Name it `Main View`.
2. In the **Sources** box, click `+` and select **Video Capture Device**.
3. Name it `Clock_Camera`.
4. Select your webcam from the dropdown and position it on the canvas.

*(Note: If you decide to generate the clock via Python instead of a physical camera, you would add an **Image** source here pointing to `current_clock.png` instead).*

## 3. Add the AI Text Sources
The Python script needs to know the exact names of the text sources so it can update them via WebSocket. 

1. In the **Sources** box, click `+` and select **Text (FreeType 2)** (or Text (Mac)).
2. Name the source **exactly**: `text_gpt`
3. Enter placeholder text (e.g., "GPT-4o: Waiting...").
4. Customize the font, color, and drop shadow so it looks good on stream.
5. Repeat this process for the other models, naming them exactly:
   - `text_claude`
   - `text_gemini`
   - `text_ollama`

*Why this matters:* The Python script will look for a source named `text_gpt` and send a command: "Update the text of `text_gpt` to '12:04'". If the names don't match, the script crashes.

## 4. The TTS Audio Source (The Tricky Part)
We need OBS to play a new audio file every minute. If Python tries to overwrite an `.mp3` file while OBS is holding it open, it will fail. Here is how to set it up correctly:

1. In the **Sources** box, click `+` and select **Media Source**.
2. Name it exactly: `tts_audio`.
3. Check the box for **Local File** and point it to a dummy audio file (you can just create a blank `announcement.mp3` in the project folder for now).
4. **CRITICAL SETTING #1:** Check **Restart playback when source becomes active**.
5. **CRITICAL SETTING #2:** Check **Close file when inactive**. (This allows Python to overwrite the `.mp3` file without OBS blocking it).
6. Click OK.
7. Hide the source by clicking the "Eye" icon next to `tts_audio` in the Sources list.

*How Python plays the audio:* Once Python generates the new TTS audio file, it connects to OBS via WebSocket, tells it to un-hide the `tts_audio` source (which triggers the audio to play from the beginning), waits a few seconds, and then hides it again.

## 5. Exporting Your Configuration
Once you have laid everything out and it looks perfect:
1. Go to the top menu: **Scene Collection** -> **Export**.
2. Save the `.json` file into this directory (`ai-tells-time/obs-assets/`).
3. Commit this file to Git! This ensures if your OBS ever crashes or gets wiped, you can import the exact layout in 5 seconds.