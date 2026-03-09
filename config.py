import argparse
import os
from dataclasses import dataclass
from typing import List


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Config:
    webhook_url: str
    summary_provider: str
    gemini_api_key: str | None
    gemini_model: str
    openai_api_key: str | None
    openai_model: str
    channels: List[str]
    data_dir: str
    archive_file: str
    pending_file: str
    transcripts_dir: str
    temp_dir: str
    whisper_bin: str
    whisper_model: str
    discord_char_limit: int
    discord_chunk_size: int
    summary_bullet_limit: int
    yt_dlp_timeout_s: int
    whisper_timeout_s: int
    http_timeout_s: int

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
            whisper_model=os.getenv("WHISPER_MODEL", "models/ggml-small.bin"),
            discord_char_limit=int(os.getenv("DISCORD_CHAR_LIMIT", "2000")),
            discord_chunk_size=int(os.getenv("DISCORD_CHUNK_SIZE", "1900")),
            summary_bullet_limit=int(os.getenv("SUMMARY_BULLET_LIMIT", "8")),
            yt_dlp_timeout_s=int(os.getenv("YT_DLP_TIMEOUT_S", "600")),
            whisper_timeout_s=int(os.getenv("WHISPER_TIMEOUT_S", "1800")),
            http_timeout_s=int(os.getenv("HTTP_TIMEOUT_S", "60")),
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
