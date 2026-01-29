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
CHANNELS = ["@sam_sulek", "@TeamRICHEY", "@NicksStrengthandPower"] 
ARCHIVE_FILE = "/data/processed_videos.txt"
PENDING_FILE = "/data/pending_summaries.txt"
TRANSCRIPTS_DIR = "/data/transcripts"
WHISPER_BIN = "./whisper-cli" 
WHISPER_MODEL = "models/ggml-small.bin"
DISCORD_CHAR_LIMIT = 2000
DISCORD_CHUNK_SIZE = 1900
SUMMARY_BULLET_LIMIT = 8

client = genai.Client(api_key=GEMINI_API_KEY)

def log(message):
    print(f"[LOG] {message}")
    sys.stdout.flush()

def format_minutes(seconds):
    return f"{round(seconds / 60, 2)}m"

def send_discord(content):
    log("Sending summary to Discord...")
    # Discord 2000 character chunking
    chunks = [content[i:i + DISCORD_CHUNK_SIZE] for i in range(0, len(content), DISCORD_CHUNK_SIZE)]
    for chunk in chunks:
        requests.post(WEBHOOK_URL, json={"content": chunk})

def ensure_transcripts_dir():
    if not os.path.exists(TRANSCRIPTS_DIR):
        os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

def save_transcript(video_id, transcript):
    ensure_transcripts_dir()
    transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{video_id}.txt")
    with open(transcript_path, "w") as f:
        f.write(transcript)
    return transcript_path

def load_pending_entries():
    if not os.path.exists(PENDING_FILE):
        return []
    with open(PENDING_FILE, "r") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    entries = []
    for line in lines:
        parts = line.split("||")
        if len(parts) == 8:
            parts.append("0")
        if len(parts) != 9:
            continue
        entries.append(parts)
    return entries

def write_pending_entries(entries):
    with open(PENDING_FILE, "w") as f:
        for entry in entries:
            f.write("||".join(entry) + "\n")

def upsert_pending_entry(entry):
    entries = load_pending_entries()
    entries = [e for e in entries if e[0] != entry[0]]
    entries.append(entry)
    write_pending_entries(entries)

def generate_summary_with_retry(transcript, max_chars, max_attempts=5, delays=(10, 30, 60, 120)):
    attempts = 0
    while True:
        attempts += 1
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite', 
                contents=(
                    "Summarize this YouTube transcript into concise bullet points only. "
                    f"Use at most {SUMMARY_BULLET_LIMIT} bullets and keep the summary under {max_chars} characters. "
                    "Do not include any title or heading; the title is provided separately:\n\n"
                    f"{transcript}"
                )
            )
            return response.text
        except Exception as e:
            error_text = str(e)
            if attempts >= max_attempts:
                raise
            if "503" in error_text or "UNAVAILABLE" in error_text or "overloaded" in error_text.lower():
                delay = delays[min(attempts - 1, len(delays) - 1)]
                log(f"Gemini overloaded, retrying in {delay}s (attempt {attempts}/{max_attempts})...")
                time.sleep(delay)
                continue
            raise

def summarize_and_send(video_id, url, channel_name, video_title, video_length, transcript, dw_time, ts_time):
    try:
        title_line = f"**{channel_name} - {video_title}**"
        stats_footer = (
            f"\n*Processing {video_length} | "
            f"download {format_minutes(float(dw_time))} | "
            f"transcription {format_minutes(float(ts_time))}*"
        )
        reserved_chars = len(title_line) + 2 + len(stats_footer)
        max_summary_chars = max(DISCORD_CHUNK_SIZE - reserved_chars, 200)
        summary_text = generate_summary_with_retry(transcript, max_summary_chars)
        summary_lines = [
            line for line in summary_text.splitlines()
            if line.strip().startswith(("-", "•", "*"))
        ]
        summary_body = "\n".join(summary_lines).strip() if summary_lines else summary_text.strip()
        if len(summary_body) > max_summary_chars:
            cutoff = max(max_summary_chars - 3, 0)
            summary_body = summary_body[:cutoff].rstrip() + ("..." if cutoff > 0 else "")
        full_message = f"{title_line}\n{summary_body}\n{stats_footer}"
        send_discord(full_message)
        log("✅ Summary sent to Discord.")
        return True, None
    except Exception as e:
        log(f"❌ Summary failed for {video_id}: {e}")
        return False, str(e)

def process_pending_summaries():
    entries = load_pending_entries()
    if not entries:
        return
    log(f"Found {len(entries)} pending summaries. Retrying...")
    remaining = []
    for entry in entries:
        video_id, url, channel_name, video_title, video_length, dw_time, ts_time, transcript_path, attempts = entry
        attempts_int = int(attempts)
        if not os.path.exists(transcript_path):
            log(f"Missing transcript for {video_id}, skipping.")
            remaining.append(entry)
            continue
        with open(transcript_path, "r") as f:
            transcript = f.read()
        ok, error_text = summarize_and_send(
            video_id, url, channel_name, video_title, video_length, transcript, dw_time, ts_time
        )
        if not ok:
            attempts_int += 1
            if attempts_int >= 5:
                error_msg = f"❌ Summary failed after 5 attempts for {video_id}: {error_text}"
                send_discord(error_msg)
                continue
            remaining.append([
                video_id,
                url,
                channel_name,
                video_title,
                video_length,
                dw_time,
                ts_time,
                transcript_path,
                str(attempts_int),
            ])
    write_pending_entries(remaining)

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
        dl_attempts = 0
        while True:
            dl_attempts += 1
            try:
                subprocess.run(dl_cmd, shell=True, check=True)
                break
            except subprocess.CalledProcessError as e:
                if dl_attempts >= 3:
                    raise e
                delay = 10 * dl_attempts
                log(f"Download failed, retrying in {delay}s (attempt {dl_attempts}/3)...")
                time.sleep(delay)
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
        transcript_path = save_transcript(video_id, transcript)
        ok, error_text = summarize_and_send(
            video_id, url, channel_name, video_title, video_length, transcript, dw_time, ts_time
        )
        if not ok:
            upsert_pending_entry([
                video_id,
                url,
                channel_name,
                video_title,
                video_length,
                str(dw_time),
                str(ts_time),
                transcript_path,
                "1",
            ])
            return
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
    if not os.path.exists(PENDING_FILE): open(PENDING_FILE, 'a').close()
    process_pending_summaries()
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
