import gzip
import os

from config import Config
from subprocess_utils import run_command


def transcribe_audio(audio_path: str, config: Config) -> str:
    args = [
        config.whisper_bin,
        "-m",
        config.whisper_model,
        "-f",
        audio_path,
        "-otxt",
    ]
    run_command(args, timeout_s=config.whisper_timeout_s)
    transcript_path = f"{audio_path}.txt"
    with open(transcript_path, "r") as handle:
        transcript = handle.read()
    return transcript


def save_transcript(video_id: str, transcript: str, config: Config) -> str:
    os.makedirs(config.transcripts_dir, exist_ok=True)
    transcript_path = os.path.join(config.transcripts_dir, f"{video_id}.txt.gz")
    with gzip.open(transcript_path, "wt") as handle:
        handle.write(transcript)
    return transcript_path


def load_transcript(path: str) -> str:
    if path.endswith(".gz"):
        with gzip.open(path, "rt") as handle:
            return handle.read()
    with open(path, "r") as handle:
        return handle.read()
