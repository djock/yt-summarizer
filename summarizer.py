import os
import subprocess
import requests
import time
from google import genai
import sys

# --- CONFIGURATION ---
def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

WEBHOOK_URL = require_env("DISCORD_WEBHOOK_URL")
GEMINI_API_KEY = require_env("GEMINI_API_KEY")
CHANNELS = ["@sam_sulek", "@TeamRICHEY"] 
ARCHIVE_FILE = "/data/processed_videos.txt"
WHISPER_BIN = "./whisper-cli" 
WHISPER_MODEL = "models/ggml-small.bin"

client = genai.Client(api_key=GEMINI_API_KEY)

def log(message):
    print(f"[LOG] {message}")
    sys.stdout.flush()

def send_discord(content):
    log("Sending summary to Discord...")
    # Discord 2000 character chunking
    chunks = [content[i:i + 1900] for i in range(0, len(content), 1900)]
    for chunk in chunks:
        requests.post(WEBHOOK_URL, json={"content": chunk})

def process_video(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    log(f"🚀 STARTING PROCESS: {url}")
    
    try:
        # Fetch metadata for formatting
        log("Fetching video metadata...")
        meta_cmd = (
            "yt-dlp --skip-download "
            "--print '%(channel)s||%(title)s||%(duration_string)s' "
            f"{url}"
        )
        channel_name, video_title, video_length = (
            subprocess.check_output(meta_cmd, shell=True).decode().strip().split("||", 2)
        )

        # 1. Download Audio + Timer
        log("Downloading audio via yt-dlp...")
        start_dw = time.time()
        
        # User-Agent added to bypass 403 Forbidden errors
        dl_cmd = (
            f"yt-dlp -x --audio-format wav "
            f"--user-agent 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' "
            f"--postprocessor-args 'ffmpeg:-ar 16000 -ac 1' "
            f"-o 'tmp.wav' {url}"
        )
        subprocess.run(dl_cmd, shell=True, check=True)
        dw_time = round(time.time() - start_dw, 2)
        
        # 2. Transcribe + Timer
        log("Transcribing audio with Whisper...")
        start_ts = time.time()
        subprocess.run(f"{WHISPER_BIN} -m {WHISPER_MODEL} -f tmp.wav -otxt", shell=True, check=True)
        ts_time = round(time.time() - start_ts, 2)
        
        with open("tmp.wav.txt", "r") as f:
            transcript = f.read()

        # 3. Summarize with Gemini
        log("Requesting summary from Gemini AI...")
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite', 
            contents=(
                "Summarize this YouTube transcript into concise bullet points only. "
                "Do not include any title or heading; the title is provided separately:\n\n"
                f"{transcript}"
            )
        )
        
        # 4. Prepare Final Message (Link wrapped in < > to hide thumbnail)
        summary_lines = [
            line for line in response.text.splitlines()
            if line.strip().startswith(("-", "•", "*"))
        ]
        summary_text = "\n".join(summary_lines).strip() if summary_lines else response.text.strip()
        stats_footer = f"\n*Processing {video_length} | download {dw_time} | transcription {ts_time}*"
        full_message = f"**{channel_name} - {video_title}**\n{summary_text}\n{stats_footer}"
        
        send_discord(full_message)
        log(f"✅ Finished. DW: {dw_time}s, TS: {ts_time}s")

    except Exception as e:
        error_msg = f"❌ Error processing {video_id}: {str(e)}"
        log(error_msg)
        send_discord(error_msg)
    finally:
        log("Cleaning up temporary files...")
        if os.path.exists("tmp.wav"): os.remove("tmp.wav")
        if os.path.exists("tmp.wav.txt"): os.remove("tmp.wav.txt")

if __name__ == "__main__":
    log("Checking for new videos...")
    if not os.path.exists(ARCHIVE_FILE): open(ARCHIVE_FILE, 'a').close()
    with open(ARCHIVE_FILE, "r") as f:
        processed = f.read().splitlines()

    for channel in CHANNELS:
        try:
            log(f"Checking channel: {channel}")
            cmd = f"yt-dlp --get-id --playlist-items 1 https://www.youtube.com/{channel}/videos"
            latest_id = subprocess.check_output(cmd, shell=True).decode().strip()
            
            if latest_id not in processed:
                process_video(latest_id)
                with open(ARCHIVE_FILE, "a") as f:
                    f.write(latest_id + "\n")
            else:
                log(f"Video {latest_id} is already in the archive. Skipping.")
        except Exception as e:
            log(f"Critical error: {e}")
