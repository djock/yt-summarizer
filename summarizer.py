import logging
import os
import sys
import tempfile
import time

from core.config import Config, parse_args
from core.models import Job, PendingEntry
from core.state import append_archive, load_pending_entries, read_archive, upsert_pending_entry, write_pending_entries
from pipeline.fetch import download_audio_and_metadata, get_latest_video_id
from pipeline.notify import send_discord
from pipeline.summarize import build_provider, summarize_transcript
from pipeline.transcribe import load_transcript, save_transcript, transcribe_audio
from utils.retry import run_with_retry
from utils.subprocess_utils import CommandError

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def format_minutes(seconds: float) -> str:
    return f"{round(seconds / 60, 2)}m"


def ensure_files(config: Config) -> None:
    os.makedirs(os.path.dirname(config.archive_file), exist_ok=True)
    os.makedirs(os.path.dirname(config.pending_file), exist_ok=True)
    os.makedirs(config.transcripts_dir, exist_ok=True)
    os.makedirs(config.temp_dir, exist_ok=True)
    if not os.path.exists(config.archive_file):
        with open(config.archive_file, "a"):
            pass
    if not os.path.exists(config.pending_file):
        with open(config.pending_file, "a"):
            pass


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
    send_discord(config.webhook_url, full_message, config.discord_chunk_size, config.http_timeout_s, config.discord_retry_policy())
    logger.info("Summary sent to Discord.")
    return True


def process_pending_summaries(config: Config, provider) -> None:
    entries = load_pending_entries(config.pending_file)
    if not entries:
        return
    logger.info("Found %d pending summaries. Retrying...", len(entries))
    remaining: list[PendingEntry] = []
    for entry in entries:
        job = entry.job
        if not job.transcript_path or not os.path.exists(job.transcript_path):
            logger.warning("Missing transcript for %s, skipping.", job.video_id)
            remaining.append(entry)
            continue
        transcript = load_transcript(job.transcript_path)
        try:
            summarize_and_send(config, provider, job, transcript)
        except Exception as exc:
            entry.attempts += 1
            if entry.attempts >= config.pending_max_retries:
                error_msg = f"❌ Summary failed after {config.pending_max_retries} attempts for {job.video_id}: {exc}"
                send_discord(config.webhook_url, error_msg, config.discord_chunk_size, config.http_timeout_s, config.discord_retry_policy())
                continue
            remaining.append(entry)
    write_pending_entries(config.pending_file, remaining)


def process_video(config: Config, provider, video_id: str) -> bool:
    logger.info("Starting: https://www.youtube.com/watch?v=%s", video_id)

    with tempfile.TemporaryDirectory(dir=config.temp_dir) as tmp_dir:
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
                config.download_retry_policy(),
                lambda exc: isinstance(exc, CommandError),
            )
            download_time = round(time.time() - start_dw, 2)
            job.download_time_s = download_time

            logger.info("Transcribing audio with Whisper...")
            start_ts = time.time()
            transcript = transcribe_audio(audio_path, config)
            transcription_time = round(time.time() - start_ts, 2)
            job.transcription_time_s = transcription_time

            transcript_path = save_transcript(job.video_id, transcript, config)
            job.transcript_path = transcript_path

            logger.info("Requesting summary from provider...")
            summarize_and_send(config, provider, job, transcript)
            logger.info("Finished. DW: %ss, TS: %ss", download_time, transcription_time)
            return True

        except Exception as exc:
            error_msg = f"❌ Error processing {video_id}: {exc}"
            if isinstance(exc, CommandError) and exc.result:
                details = []
                if exc.result.stderr:
                    details.append(f"stderr:\n{exc.result.stderr.strip()}")
                if exc.result.stdout:
                    details.append(f"stdout:\n{exc.result.stdout.strip()}")
                if details:
                    error_msg = f"{error_msg}\n\n" + "\n\n".join(details)
            logger.error(error_msg)
            send_discord(config.webhook_url, error_msg, config.discord_chunk_size, config.http_timeout_s, config.discord_retry_policy())
            if job and job.transcript_path:
                pending = PendingEntry(job=job, attempts=1)
                upsert_pending_entry(config.pending_file, pending)
            return False


def process_video_list(config: Config, provider) -> None:
    assert config.video_ids_file is not None
    with open(config.video_ids_file) as f:
        video_ids = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if not video_ids:
        logger.warning("No video IDs found in %s", config.video_ids_file)
        return

    logger.info("Processing %d video(s) from %s", len(video_ids), config.video_ids_file)
    processed = set(read_archive(config.archive_file))

    for video_id in video_ids:
        if not config.force and video_id in processed:
            logger.info("Video %s already in archive, skipping (use --force to reprocess).", video_id)
            continue
        processed_ok = process_video(config, provider, video_id)
        if processed_ok:
            append_archive(config.archive_file, video_id)
            processed.add(video_id)
        else:
            logger.warning("Not adding %s to archive because processing failed.", video_id)


def main() -> None:
    args = parse_args()
    config = Config.from_env(args)
    _configure_logging(config.log_level)
    config.validate()

    provider = build_provider(config)
    ensure_files(config)

    logger.info("Checking for pending summaries...")
    process_pending_summaries(config, provider)

    if config.video_ids_file:
        process_video_list(config, provider)
        return

    processed = set(read_archive(config.archive_file))

    for channel in config.channels:
        try:
            logger.info("Checking channel: %s", channel)
            latest_id = get_latest_video_id(channel, config.yt_dlp_timeout_s)
            if latest_id not in processed:
                processed_ok = process_video(config, provider, latest_id)
                if processed_ok:
                    append_archive(config.archive_file, latest_id)
                else:
                    logger.warning("Not adding %s to archive because processing failed.", latest_id)
            else:
                logger.info("Video %s is already in the archive. Skipping.", latest_id)
        except Exception as exc:
            if isinstance(exc, CommandError) and exc.result:
                details = []
                if exc.result.stderr:
                    details.append(f"stderr: {exc.result.stderr.strip()}")
                if exc.result.stdout:
                    details.append(f"stdout: {exc.result.stdout.strip()}")
                detail_suffix = f" ({' | '.join(details)})" if details else ""
                logger.error("Critical error for channel %s: %s%s", channel, exc, detail_suffix)
            else:
                logger.error("Critical error for channel %s: %s", channel, exc)


if __name__ == "__main__":
    main()
