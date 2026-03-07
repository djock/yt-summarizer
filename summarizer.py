import os
import tempfile
import time
import sys

from config import Config, parse_args
from fetch import download_audio_and_metadata, get_latest_video_id
from models import Job, PendingEntry
from notify import send_discord
from retry import RetryPolicy, run_with_retry
from state import append_archive, load_pending_entries, read_archive, upsert_pending_entry, write_pending_entries
from subprocess_utils import CommandError
from summarize import build_provider, summarize_transcript
from transcribe import load_transcript, save_transcript, transcribe_audio


def log(message: str) -> None:
    print(f"[LOG] {message}")
    sys.stdout.flush()


def format_minutes(seconds: float) -> str:
    return f"{round(seconds / 60, 2)}m"


def ensure_files(config: Config) -> None:
    os.makedirs(os.path.dirname(config.archive_file), exist_ok=True)
    os.makedirs(os.path.dirname(config.pending_file), exist_ok=True)
    os.makedirs(config.transcripts_dir, exist_ok=True)
    os.makedirs(config.temp_dir, exist_ok=True)
    if not os.path.exists(config.archive_file):
        open(config.archive_file, "a").close()
    if not os.path.exists(config.pending_file):
        open(config.pending_file, "a").close()


def summarize_and_send(config: Config, provider, job: Job, transcript: str) -> bool:
    title_line = f"**{job.channel_name} - {job.title}**"
    stats_footer = (
        f"\n*Processing {job.duration} | "
        f"download {format_minutes(float(job.download_time_s or 0))} | "
        f"transcription {format_minutes(float(job.transcription_time_s or 0))}*"
    )
    reserved_chars = len(title_line) + 2 + len(stats_footer)
    max_summary_chars = max(config.discord_chunk_size - reserved_chars, 200)

    summary_text = summarize_transcript(
        provider,
        transcript=transcript,
        max_summary_chars=max_summary_chars,
        channel_name=job.channel_name,
        bullet_limit=config.summary_bullet_limit,
    )
    summary_lines = [
        line for line in summary_text.splitlines()
        if line.strip().startswith(("-", "•", "*"))
    ]
    summary_body = "\n".join(summary_lines).strip() if summary_lines else summary_text.strip()
    if len(summary_body) > max_summary_chars:
        cutoff = max(max_summary_chars - 3, 0)
        summary_body = summary_body[:cutoff].rstrip() + ("..." if cutoff > 0 else "")
    full_message = f"{title_line}\n{summary_body}\n{stats_footer}"
    send_discord(config.webhook_url, full_message, config.discord_chunk_size, config.http_timeout_s)
    log("✅ Summary sent to Discord.")
    return True


def process_pending_summaries(config: Config, provider) -> None:
    entries = load_pending_entries(config.pending_file)
    if not entries:
        return
    log(f"Found {len(entries)} pending summaries. Retrying...")
    remaining: list[PendingEntry] = []
    for entry in entries:
        job = entry.job
        if not job.transcript_path or not os.path.exists(job.transcript_path):
            log(f"Missing transcript for {job.video_id}, skipping.")
            remaining.append(entry)
            continue
        transcript = load_transcript(job.transcript_path)
        try:
            summarize_and_send(config, provider, job, transcript)
        except Exception as exc:
            entry.attempts += 1
            if entry.attempts >= 5:
                error_msg = f"❌ Summary failed after 5 attempts for {job.video_id}: {exc}"
                send_discord(config.webhook_url, error_msg, config.discord_chunk_size, config.http_timeout_s)
                continue
            remaining.append(entry)
    write_pending_entries(config.pending_file, remaining)


def process_video(config: Config, provider, video_id: str) -> bool:
    log(f"🚀 STARTING PROCESS: https://www.youtube.com/watch?v={video_id}")
    download_policy = RetryPolicy(max_attempts=3, delays_s=[10, 20])

    with tempfile.TemporaryDirectory(dir=config.temp_dir) as tmp_dir:
        audio_path = None
        job = None
        download_time = None
        transcription_time = None
        try:
            start_dw = time.time()

            def download() -> tuple[Job, str]:
                job_local, audio_path_local, _ = download_audio_and_metadata(video_id, config, tmp_dir)
                return job_local, audio_path_local

            job, audio_path = run_with_retry(
                download,
                download_policy,
                lambda exc: isinstance(exc, CommandError),
            )
            download_time = round(time.time() - start_dw, 2)
            job.download_time_s = download_time

            log("Transcribing audio with Whisper...")
            start_ts = time.time()
            transcript = transcribe_audio(audio_path, config)
            transcription_time = round(time.time() - start_ts, 2)
            job.transcription_time_s = transcription_time

            transcript_path = save_transcript(job.video_id, transcript, config)
            job.transcript_path = transcript_path

            log("Requesting summary from provider...")
            summarize_and_send(config, provider, job, transcript)
            log(f"✅ Finished. DW: {download_time}s, TS: {transcription_time}s")
            return True

        except Exception as exc:
            error_msg = f"❌ Error processing {video_id}: {exc}"
            if isinstance(exc, CommandError) and exc.result:
                details = []
                if exc.result.stderr:
                    details.append(f"stderr:\\n{exc.result.stderr.strip()}")
                if exc.result.stdout:
                    details.append(f"stdout:\\n{exc.result.stdout.strip()}")
                if details:
                    error_msg = f"{error_msg}\\n\\n" + "\\n\\n".join(details)
            log(error_msg)
            send_discord(config.webhook_url, error_msg, config.discord_chunk_size, config.http_timeout_s)
            if job and job.transcript_path:
                pending = PendingEntry(job=job, attempts=1)
                upsert_pending_entry(config.pending_file, pending)
            return False


def main() -> None:
    args = parse_args()
    config = Config.from_env(args)
    if not config.webhook_url:
        raise RuntimeError("Missing required environment variable: DISCORD_WEBHOOK_URL")

    provider = build_provider(config)
    ensure_files(config)

    log("Checking for pending summaries...")
    process_pending_summaries(config, provider)

    processed = set(read_archive(config.archive_file))

    for channel in config.channels:
        try:
            log(f"Checking channel: {channel}")
            latest_id = get_latest_video_id(channel, config.yt_dlp_timeout_s)
            if latest_id not in processed:
                processed_ok = process_video(config, provider, latest_id)
                if processed_ok:
                    append_archive(config.archive_file, latest_id)
                else:
                    log(f"Not adding {latest_id} to archive because processing failed.")
            else:
                log(f"Video {latest_id} is already in the archive. Skipping.")
        except Exception as exc:
            log(f"Critical error: {exc}")


if __name__ == "__main__":
    main()
