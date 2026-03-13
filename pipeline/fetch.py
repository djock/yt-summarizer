import logging
import os
import re
import shutil
from glob import glob
from typing import Tuple

from core.config import Config
from core.models import Job
from utils.subprocess_utils import CommandError, run_command

logger = logging.getLogger(__name__)

_CHANNEL_RE = re.compile(r'^@[\w.-]+$')
_AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mka",
    ".ogg",
    ".opus",
    ".wav",
    ".weba",
    ".webm",
}


def _yt_dlp_base_args() -> list[str]:
    args = ["yt-dlp"]
    js_runtime = shutil.which("node") or shutil.which("nodejs")
    if js_runtime:
        args.extend(["--js-runtimes", os.path.basename(js_runtime)])
    return args


def _run_with_fallback(arg_sets: list[list[str]], timeout_s: int) -> str:
    last_error: CommandError | None = None
    for args in arg_sets:
        try:
            return run_command(args, timeout_s=timeout_s).stdout
        except CommandError as exc:
            last_error = exc
            details = []
            if exc.result and exc.result.stderr:
                details.append(f"stderr: {exc.result.stderr.strip()}")
            if exc.result and exc.result.stdout:
                details.append(f"stdout: {exc.result.stdout.strip()}")
            detail_suffix = f" ({' | '.join(details)})" if details else ""
            logger.warning("yt-dlp invocation failed, trying fallback: %s%s", exc, detail_suffix)
    if last_error is None:
        raise CommandError("no yt-dlp command variants were provided")
    raise last_error


def validate_channel_handle(channel: str) -> None:
    if not _CHANNEL_RE.match(channel):
        raise ValueError(
            f"Invalid channel handle: {channel!r}. "
            "Expected format: @handle (e.g. @MyChannel)"
        )


def _resolve_audio_path(output_base: str, output_dir: str, video_id: str) -> str:
    exact_path = f"{output_base}.wav"
    if os.path.exists(exact_path):
        return exact_path
    if os.path.exists(output_base) and os.path.isfile(output_base):
        logger.warning(
            "Resolved yt-dlp audio output without extension: expected %s.wav but found %s",
            output_base,
            output_base,
        )
        return output_base

    wav_matches = sorted(glob(os.path.join(output_dir, f"{video_id}*.wav")))
    if len(wav_matches) == 1:
        return wav_matches[0]
    if wav_matches:
        raise CommandError(
            "yt-dlp produced multiple wav files; cannot determine transcription input: "
            + ", ".join(wav_matches)
        )

    audio_candidates: list[str] = []
    for name in sorted(os.listdir(output_dir)):
        path = os.path.join(output_dir, name)
        if not os.path.isfile(path):
            continue
        if name.endswith((".part", ".txt", ".json", ".description")):
            continue
        if os.path.splitext(name)[1].lower() in _AUDIO_EXTENSIONS:
            audio_candidates.append(path)

    if len(audio_candidates) == 1:
        logger.warning(
            "Resolved yt-dlp audio output via directory scan: expected %s.wav but found %s",
            output_base,
            audio_candidates[0],
        )
        return audio_candidates[0]
    if audio_candidates:
        raise CommandError(
            "yt-dlp produced multiple audio files; cannot determine transcription input: "
            + ", ".join(audio_candidates)
        )

    raise CommandError(
        f"yt-dlp did not produce a usable audio output under {output_dir!r} for video {video_id}"
    )


def get_latest_video_id(channel: str, timeout_s: int) -> str:
    validate_channel_handle(channel)
    base_args = _yt_dlp_base_args()
    url = f"https://www.youtube.com/{channel}/videos"
    stdout = _run_with_fallback([
        [
            *base_args,
            "--extractor-args",
            "youtube:player_client=android",
            "--get-id",
            "--playlist-items",
            "1",
            url,
        ],
        [
            *base_args,
            "--get-id",
            "--playlist-items",
            "1",
            url,
        ],
        [
            "yt-dlp",
            "--get-id",
            "--playlist-items",
            "1",
            url,
        ],
    ], timeout_s=timeout_s)
    return stdout.strip()


def download_audio_and_metadata(video_id: str, config: Config, output_dir: str) -> Tuple[Job, str, str]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_base = os.path.join(output_dir, video_id)
    common_args = [
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
        "--no-simulate",
        "--print",
        "%(channel)s||%(title)s||%(duration_string)s",
        "-o",
        f"{output_base}.%(ext)s",
        url,
    ]
    base_args = _yt_dlp_base_args()
    last_error: CommandError | None = None
    result = None
    audio_path = None
    for args in [
        [*base_args, "--extractor-args", "youtube:player_client=android", *common_args],
        [*base_args, *common_args],
        ["yt-dlp", *common_args],
    ]:
        try:
            run_result = run_command(args, timeout_s=config.yt_dlp_timeout_s)
        except CommandError as exc:
            last_error = exc
            details = []
            if exc.result and exc.result.stderr:
                details.append(f"stderr: {exc.result.stderr.strip()}")
            if exc.result and exc.result.stdout:
                details.append(f"stdout: {exc.result.stdout.strip()}")
            detail_suffix = f" ({' | '.join(details)})" if details else ""
            logger.warning("yt-dlp invocation failed, trying fallback: %s%s", exc, detail_suffix)
            continue
        try:
            audio_path = _resolve_audio_path(output_base, output_dir, video_id)
        except CommandError as exc:
            last_error = exc
            logger.warning("yt-dlp ran but produced no audio file, trying fallback: %s", exc)
            continue
        result = run_result
        break
    if result is None or audio_path is None:
        if last_error is None:
            raise CommandError("no yt-dlp command variants were provided")
        raise last_error
    meta_lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not meta_lines:
        raise CommandError("yt-dlp did not return metadata")
    meta_line = meta_lines[0]
    channel_name, title, duration = meta_line.split("||", 2)
    job = Job(video_id=video_id, url=url, channel_name=channel_name, title=title, duration=duration)
    if result.stderr:
        logger.warning("yt-dlp stderr for %s: %s", video_id, result.stderr.strip())
    return job, audio_path, result.stderr
