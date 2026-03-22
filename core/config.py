import argparse
import os
from dataclasses import dataclass, field
from typing import List

from utils.retry import RetryPolicy


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _split_ints(value: str) -> List[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _getenv_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(f"Configuration error: {name}={raw!r} is not a valid integer")


def _getenv_ints(name: str, default: str) -> List[int]:
    raw = os.getenv(name, default)
    try:
        return _split_ints(raw)
    except ValueError:
        raise RuntimeError(f"Configuration error: {name}={raw!r} must be a comma-separated list of integers")


@dataclass
class Config:
    webhook_url: str
    summary_provider: str
    gemini_api_key: str | None = field(repr=False)
    gemini_model: str
    openai_api_key: str | None = field(repr=False)
    openai_model: str
    channels: List[str]
    data_dir: str
    archive_file: str
    pending_file: str
    transcripts_dir: str
    temp_dir: str
    whisper_bin: str
    whisper_model: str
    whisper_threads: int
    discord_chunk_size: int
    summary_bullet_limit: int
    yt_dlp_timeout_s: int
    whisper_timeout_s: int
    http_timeout_s: int
    log_level: str
    download_max_retries: int
    download_retry_delays: List[int]
    summary_max_retries: int
    summary_retry_delays: List[int]
    discord_max_retries: int
    discord_retry_delays: List[int]
    pending_max_retries: int

    def download_retry_policy(self) -> RetryPolicy:
        return RetryPolicy(max_attempts=self.download_max_retries, delays_s=self.download_retry_delays)

    def summary_retry_policy(self) -> RetryPolicy:
        return RetryPolicy(max_attempts=self.summary_max_retries, delays_s=self.summary_retry_delays)

    def discord_retry_policy(self) -> RetryPolicy:
        return RetryPolicy(max_attempts=self.discord_max_retries, delays_s=self.discord_retry_delays)

    def validate(self) -> None:
        errors = []
        if not self.webhook_url:
            errors.append("DISCORD_WEBHOOK_URL is required")
        if self.summary_provider not in ("gemini", "openai"):
            errors.append(f"SUMMARY_PROVIDER must be 'gemini' or 'openai', got: {self.summary_provider!r}")
        elif self.summary_provider == "gemini" and not self.gemini_api_key:
            errors.append("GEMINI_API_KEY is required when SUMMARY_PROVIDER=gemini")
        elif self.summary_provider == "openai" and not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required when SUMMARY_PROVIDER=openai")
        if not self.channels:
            errors.append("CHANNELS must be set to at least one channel handle (e.g. CHANNELS=@MyChannel)")
        if errors:
            raise RuntimeError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    @staticmethod
    def from_env(args: argparse.Namespace) -> "Config":
        data_dir = args.data_dir or os.getenv("DATA_DIR", "/data")
        archive_file = args.archive_file or os.getenv("ARCHIVE_FILE", os.path.join(data_dir, "processed_videos.txt"))
        pending_file = args.pending_file or os.getenv("PENDING_FILE", os.path.join(data_dir, "pending_summaries.txt"))
        transcripts_dir = args.transcripts_dir or os.getenv("TRANSCRIPTS_DIR", os.path.join(data_dir, "transcripts"))
        temp_dir = args.temp_dir or os.getenv("TEMP_DIR", os.path.join(data_dir, "tmp"))

        channels_env = os.getenv("CHANNELS", "")
        channels = args.channels or _split_csv(channels_env)

        return Config(
            webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            summary_provider=(args.provider or os.getenv("SUMMARY_PROVIDER", "gemini")).strip().lower(),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            channels=channels,
            data_dir=data_dir,
            archive_file=archive_file,
            pending_file=pending_file,
            transcripts_dir=transcripts_dir,
            temp_dir=temp_dir,
            whisper_bin=os.getenv("WHISPER_BIN", "./whisper-cli"),
            whisper_model=os.getenv("WHISPER_MODEL", "models/ggml-tiny.bin"),
            whisper_threads=_getenv_int("WHISPER_THREADS", "4"),
            discord_chunk_size=_getenv_int("DISCORD_CHUNK_SIZE", "1900"),
            summary_bullet_limit=_getenv_int("SUMMARY_BULLET_LIMIT", "8"),
            yt_dlp_timeout_s=_getenv_int("YT_DLP_TIMEOUT_S", "600"),
            whisper_timeout_s=_getenv_int("WHISPER_TIMEOUT_S", "1800"),
            http_timeout_s=_getenv_int("HTTP_TIMEOUT_S", "60"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            download_max_retries=_getenv_int("DOWNLOAD_MAX_RETRIES", "3"),
            download_retry_delays=_getenv_ints("DOWNLOAD_RETRY_DELAYS", "10,20"),
            summary_max_retries=_getenv_int("SUMMARY_MAX_RETRIES", "5"),
            summary_retry_delays=_getenv_ints("SUMMARY_RETRY_DELAYS", "10,30,60,120"),
            discord_max_retries=_getenv_int("DISCORD_MAX_RETRIES", "5"),
            discord_retry_delays=_getenv_ints("DISCORD_RETRY_DELAYS", "2,5,10,20"),
            pending_max_retries=_getenv_int("PENDING_MAX_RETRIES", "5"),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YouTube summarizer")
    parser.add_argument("--provider", help="Summary provider (gemini|openai)")
    parser.add_argument("--channels", nargs="+", help="List of channel handles")
    parser.add_argument("--data-dir", help="Base data directory")
    parser.add_argument("--archive-file", help="Path to processed_videos.txt")
    parser.add_argument("--pending-file", help="Path to pending summaries file")
    parser.add_argument("--transcripts-dir", help="Path to transcripts directory")
    parser.add_argument("--temp-dir", help="Path to temp directory")
    return parser.parse_args()
