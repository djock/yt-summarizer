import json
import logging
import os
import tempfile
import types
from contextlib import contextmanager
from typing import Iterable, List

from models import Job, PendingEntry

logger = logging.getLogger(__name__)

fcntl: types.ModuleType | None
try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix platforms (e.g. Windows)
    fcntl = None
    logger.warning(
        "fcntl is not available on this platform; file locking is disabled. "
        "Running multiple instances concurrently may cause data corruption."
    )


@contextmanager
def locked_file(path: str, mode: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as handle:
        if fcntl:
            lock_type = fcntl.LOCK_EX if "w" in mode or "+" in mode or "a" in mode else fcntl.LOCK_SH
            fcntl.flock(handle, lock_type)
        try:
            yield handle
        finally:
            if fcntl:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _atomic_write(path: str, content: str) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=directory)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def read_archive(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    with locked_file(path, "r") as handle:
        return [line.strip() for line in handle.readlines() if line.strip()]


def append_archive(path: str, video_id: str) -> None:
    with locked_file(path, "a") as handle:
        handle.write(video_id + "\n")


def load_pending_entries(path: str) -> List[PendingEntry]:
    if not os.path.exists(path):
        return []
    entries: List[PendingEntry] = []
    with locked_file(path, "r") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if "||" in line:
                # Legacy format fallback
                parts = line.split("||")
                if len(parts) == 8:
                    parts.append("0")
                if len(parts) != 9:
                    continue
                video_id, url, channel_name, title, duration, dw_time, ts_time, transcript_path, attempts = parts
                job = Job(
                    video_id=video_id,
                    url=url,
                    channel_name=channel_name,
                    title=title,
                    duration=duration,
                    download_time_s=float(dw_time),
                    transcription_time_s=float(ts_time),
                    transcript_path=transcript_path,
                )
                entries.append(PendingEntry(job=job, attempts=int(attempts)))
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            job = Job(
                video_id=data["video_id"],
                url=data["url"],
                channel_name=data["channel_name"],
                title=data["title"],
                duration=data["duration"],
                download_time_s=data.get("download_time_s"),
                transcription_time_s=data.get("transcription_time_s"),
                transcript_path=data.get("transcript_path"),
            )
            entries.append(PendingEntry(job=job, attempts=int(data.get("attempts", 0))))
    return entries


def write_pending_entries(path: str, entries: Iterable[PendingEntry]) -> None:
    lines = []
    for entry in entries:
        data = {
            "video_id": entry.job.video_id,
            "url": entry.job.url,
            "channel_name": entry.job.channel_name,
            "title": entry.job.title,
            "duration": entry.job.duration,
            "download_time_s": entry.job.download_time_s,
            "transcription_time_s": entry.job.transcription_time_s,
            "transcript_path": entry.job.transcript_path,
            "attempts": entry.attempts,
        }
        lines.append(json.dumps(data))
    content = "\n".join(lines) + ("\n" if lines else "")
    _atomic_write(path, content)


def upsert_pending_entry(path: str, entry: PendingEntry) -> None:
    entries = load_pending_entries(path)
    entries = [e for e in entries if e.job.video_id != entry.job.video_id]
    entries.append(entry)
    write_pending_entries(path, entries)
