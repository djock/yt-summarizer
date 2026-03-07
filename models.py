from dataclasses import dataclass


@dataclass
class Job:
    video_id: str
    url: str
    channel_name: str
    title: str
    duration: str
    download_time_s: float | None = None
    transcription_time_s: float | None = None
    transcript_path: str | None = None


@dataclass
class PendingEntry:
    job: Job
    attempts: int
