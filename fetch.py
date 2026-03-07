import os
from typing import Tuple

from config import Config
from models import Job
from subprocess_utils import CommandError, run_command


def get_latest_video_id(channel: str, timeout_s: int) -> str:
    args = [
        "yt-dlp",
        "--js-runtimes",
        "node",
        "--extractor-args",
        "youtube:player_client=android",
        "--get-id",
        "--playlist-items",
        "1",
        f"https://www.youtube.com/{channel}/videos",
    ]
    result = run_command(args, timeout_s=timeout_s)
    return result.stdout.strip()


def download_audio_and_metadata(video_id: str, config: Config, output_dir: str) -> Tuple[Job, str, str]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_base = os.path.join(output_dir, video_id)
    args = [
        "yt-dlp",
        "--js-runtimes",
        "node",
        "--extractor-args",
        "youtube:player_client=android",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "-f",
        "bestaudio[ext=webm]/bestaudio/best",
        "-x",
        "--audio-format",
        "wav",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--postprocessor-args",
        "ffmpeg:-ar 16000 -ac 1",
        "--print",
        "%(channel)s||%(title)s||%(duration_string)s",
        "-o",
        output_base,
        url,
    ]
    result = run_command(args, timeout_s=config.yt_dlp_timeout_s)
    meta_lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not meta_lines:
        raise CommandError("yt-dlp did not return metadata")
    meta_line = meta_lines[0]
    channel_name, title, duration = meta_line.split("||", 2)
    job = Job(video_id=video_id, url=url, channel_name=channel_name, title=title, duration=duration)
    return job, f"{output_base}.wav", result.stderr
