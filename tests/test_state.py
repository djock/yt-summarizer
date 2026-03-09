import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import Job, PendingEntry
from state import (
    read_archive,
    append_archive,
    load_pending_entries,
    write_pending_entries,
    upsert_pending_entry,
)


def _make_job(video_id="abc123", channel_name="TestChannel", title="Test Title") -> Job:
    return Job(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_name=channel_name,
        title=title,
        duration="10:00",
        download_time_s=5.0,
        transcription_time_s=30.0,
        transcript_path="/data/transcripts/abc123.txt.gz",
    )


class TestReadArchive:
    def test_returns_empty_list_when_file_missing(self, tmp_path):
        result = read_archive(str(tmp_path / "nonexistent.txt"))
        assert result == []

    def test_reads_video_ids(self, tmp_path):
        archive = tmp_path / "archive.txt"
        archive.write_text("id1\nid2\nid3\n")
        result = read_archive(str(archive))
        assert result == ["id1", "id2", "id3"]

    def test_skips_blank_lines(self, tmp_path):
        archive = tmp_path / "archive.txt"
        archive.write_text("id1\n\nid2\n\n")
        result = read_archive(str(archive))
        assert result == ["id1", "id2"]

    def test_strips_whitespace(self, tmp_path):
        archive = tmp_path / "archive.txt"
        archive.write_text("  id1  \n  id2  \n")
        result = read_archive(str(archive))
        assert result == ["id1", "id2"]


class TestAppendArchive:
    def test_creates_file_and_appends(self, tmp_path):
        archive = tmp_path / "sub" / "archive.txt"
        append_archive(str(archive), "vid1")
        assert read_archive(str(archive)) == ["vid1"]

    def test_appends_to_existing_file(self, tmp_path):
        archive = tmp_path / "archive.txt"
        archive.write_text("vid1\n")
        append_archive(str(archive), "vid2")
        assert read_archive(str(archive)) == ["vid1", "vid2"]

    def test_multiple_appends(self, tmp_path):
        archive = tmp_path / "archive.txt"
        for i in range(5):
            append_archive(str(archive), f"vid{i}")
        result = read_archive(str(archive))
        assert result == [f"vid{i}" for i in range(5)]


class TestLoadPendingEntries:
    def test_returns_empty_list_when_file_missing(self, tmp_path):
        result = load_pending_entries(str(tmp_path / "nonexistent.txt"))
        assert result == []

    def test_loads_jsonl_entries(self, tmp_path):
        pending = tmp_path / "pending.txt"
        job = _make_job()
        entry = PendingEntry(job=job, attempts=2)
        write_pending_entries(str(pending), [entry])
        entries = load_pending_entries(str(pending))
        assert len(entries) == 1
        assert entries[0].job.video_id == "abc123"
        assert entries[0].attempts == 2

    def test_skips_invalid_json_lines(self, tmp_path):
        pending = tmp_path / "pending.txt"
        valid_entry = json.dumps({
            "video_id": "vid1",
            "url": "https://youtube.com/watch?v=vid1",
            "channel_name": "Chan",
            "title": "Title",
            "duration": "5:00",
            "download_time_s": 1.0,
            "transcription_time_s": 10.0,
            "transcript_path": "/data/vid1.txt.gz",
            "attempts": 1,
        })
        pending.write_text(f"not-json\n{valid_entry}\n")
        entries = load_pending_entries(str(pending))
        assert len(entries) == 1
        assert entries[0].job.video_id == "vid1"

    def test_loads_legacy_pipe_format(self, tmp_path):
        pending = tmp_path / "pending.txt"
        line = "vid1||https://yt.com/v=vid1||Chan||Title||5:00||1.5||10.0||/data/vid1.txt.gz||3"
        pending.write_text(line + "\n")
        entries = load_pending_entries(str(pending))
        assert len(entries) == 1
        assert entries[0].job.video_id == "vid1"
        assert entries[0].attempts == 3

    def test_skips_empty_lines(self, tmp_path):
        pending = tmp_path / "pending.txt"
        pending.write_text("\n\n\n")
        entries = load_pending_entries(str(pending))
        assert entries == []


class TestWritePendingEntries:
    def test_writes_entries_as_jsonl(self, tmp_path):
        pending = tmp_path / "pending.txt"
        job = _make_job()
        write_pending_entries(str(pending), [PendingEntry(job=job, attempts=1)])
        content = pending.read_text()
        data = json.loads(content.strip())
        assert data["video_id"] == "abc123"
        assert data["attempts"] == 1

    def test_writes_empty_file_for_empty_list(self, tmp_path):
        pending = tmp_path / "pending.txt"
        write_pending_entries(str(pending), [])
        assert pending.read_text() == ""

    def test_round_trip(self, tmp_path):
        pending = tmp_path / "pending.txt"
        jobs = [_make_job(f"vid{i}") for i in range(3)]
        entries = [PendingEntry(job=j, attempts=i) for i, j in enumerate(jobs)]
        write_pending_entries(str(pending), entries)
        loaded = load_pending_entries(str(pending))
        assert len(loaded) == 3
        assert [e.job.video_id for e in loaded] == ["vid0", "vid1", "vid2"]
        assert [e.attempts for e in loaded] == [0, 1, 2]


class TestUpsertPendingEntry:
    def test_adds_new_entry(self, tmp_path):
        pending = tmp_path / "pending.txt"
        entry = PendingEntry(job=_make_job("new1"), attempts=1)
        upsert_pending_entry(str(pending), entry)
        entries = load_pending_entries(str(pending))
        assert len(entries) == 1
        assert entries[0].job.video_id == "new1"

    def test_updates_existing_entry(self, tmp_path):
        pending = tmp_path / "pending.txt"
        job = _make_job("vid1")
        write_pending_entries(str(pending), [PendingEntry(job=job, attempts=1)])
        updated = PendingEntry(job=job, attempts=3)
        upsert_pending_entry(str(pending), updated)
        entries = load_pending_entries(str(pending))
        assert len(entries) == 1
        assert entries[0].attempts == 3

    def test_preserves_other_entries_on_update(self, tmp_path):
        pending = tmp_path / "pending.txt"
        job_a = _make_job("vid_a")
        job_b = _make_job("vid_b")
        write_pending_entries(str(pending), [
            PendingEntry(job=job_a, attempts=1),
            PendingEntry(job=job_b, attempts=2),
        ])
        updated_a = PendingEntry(job=job_a, attempts=5)
        upsert_pending_entry(str(pending), updated_a)
        entries = load_pending_entries(str(pending))
        assert len(entries) == 2
        vid_map = {e.job.video_id: e for e in entries}
        assert vid_map["vid_a"].attempts == 5
        assert vid_map["vid_b"].attempts == 2
