import os
from unittest.mock import MagicMock, patch

from core.models import Job, PendingEntry
from core.state import write_pending_entries
from summarizer import ensure_files, process_pending_summaries, summarize_and_send


def _make_job(video_id="vid1", transcript_path=None):
    return Job(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel_name="Test Channel",
        title="Test Title",
        duration="5:00",
        download_time_s=1.0,
        transcription_time_s=10.0,
        transcript_path=transcript_path,
    )


def _make_config(tmp_path):
    cfg = MagicMock()
    cfg.archive_file = str(tmp_path / "data" / "archive.txt")
    cfg.pending_file = str(tmp_path / "data" / "pending.txt")
    cfg.transcripts_dir = str(tmp_path / "data" / "transcripts")
    cfg.temp_dir = str(tmp_path / "data" / "tmp")
    cfg.webhook_url = "https://discord.example/hook"
    cfg.discord_chunk_size = 1900
    cfg.http_timeout_s = 10
    cfg.summary_bullet_limit = 5
    cfg.pending_max_retries = 3
    cfg.discord_retry_policy.return_value = MagicMock()
    return cfg


class TestEnsureFiles:
    def test_creates_directories(self, tmp_path):
        cfg = _make_config(tmp_path)
        ensure_files(cfg)
        assert os.path.isdir(str(tmp_path / "data"))
        assert os.path.isdir(cfg.transcripts_dir)
        assert os.path.isdir(cfg.temp_dir)

    def test_creates_archive_file(self, tmp_path):
        cfg = _make_config(tmp_path)
        ensure_files(cfg)
        assert os.path.exists(cfg.archive_file)

    def test_creates_pending_file(self, tmp_path):
        cfg = _make_config(tmp_path)
        ensure_files(cfg)
        assert os.path.exists(cfg.pending_file)

    def test_does_not_overwrite_existing_archive(self, tmp_path):
        cfg = _make_config(tmp_path)
        ensure_files(cfg)
        with open(cfg.archive_file, "w") as f:
            f.write("existing_id\n")
        ensure_files(cfg)
        assert open(cfg.archive_file).read() == "existing_id\n"


class TestSummarizeAndSend:
    def test_sends_formatted_message(self, tmp_path):
        cfg = _make_config(tmp_path)
        provider = MagicMock()
        provider.generate.return_value = "- bullet one\n- bullet two"
        provider.provider.max_input_chars = 10000

        job = _make_job()
        job.download_time_s = 30.0
        job.transcription_time_s = 120.0

        with patch("summarizer.send_discord") as mock_send, \
             patch("summarizer.summarize_transcript", return_value="- bullet one\n- bullet two"):
            result = summarize_and_send(cfg, provider, job, "transcript text")

        assert result is True
        assert mock_send.called
        sent_content = mock_send.call_args[0][1]
        assert "Test Channel" in sent_content
        assert "Test Title" in sent_content

    def test_strips_non_bullet_lines_from_summary(self, tmp_path):
        cfg = _make_config(tmp_path)
        provider = MagicMock()

        summary = "Here is your summary:\n- point one\n- point two\nSome trailing text"
        with patch("summarizer.send_discord") as mock_send, \
             patch("summarizer.summarize_transcript", return_value=summary):
            summarize_and_send(cfg, provider, _make_job(), "transcript")

        sent_content = mock_send.call_args[0][1]
        assert "Here is your summary:" not in sent_content
        assert "Some trailing text" not in sent_content
        assert "point one" in sent_content


class TestProcessPendingSummaries:
    def test_skips_entries_with_missing_transcript(self, tmp_path):
        cfg = _make_config(tmp_path)
        ensure_files(cfg)
        job = _make_job(transcript_path="/nonexistent/path.txt.gz")
        write_pending_entries(cfg.pending_file, [PendingEntry(job=job, attempts=1)])

        provider = MagicMock()
        with patch("summarizer.summarize_and_send") as mock_send:
            process_pending_summaries(cfg, provider)

        mock_send.assert_not_called()

    def test_retries_entry_with_valid_transcript(self, tmp_path):
        cfg = _make_config(tmp_path)
        ensure_files(cfg)

        transcript_file = tmp_path / "t.txt"
        transcript_file.write_text("transcript content")

        job = _make_job(transcript_path=str(transcript_file))
        write_pending_entries(cfg.pending_file, [PendingEntry(job=job, attempts=1)])

        provider = MagicMock()
        with patch("summarizer.summarize_and_send", return_value=True) as mock_send, \
             patch("summarizer.load_transcript", return_value="transcript content"):
            process_pending_summaries(cfg, provider)

        mock_send.assert_called_once()

    def test_removes_successful_entry_from_pending(self, tmp_path):
        cfg = _make_config(tmp_path)
        ensure_files(cfg)

        transcript_file = tmp_path / "t.txt"
        transcript_file.write_text("text")

        job = _make_job(transcript_path=str(transcript_file))
        write_pending_entries(cfg.pending_file, [PendingEntry(job=job, attempts=1)])

        with patch("summarizer.summarize_and_send", return_value=True), \
             patch("summarizer.load_transcript", return_value="text"):
            process_pending_summaries(cfg, MagicMock())

        from core.state import load_pending_entries
        remaining = load_pending_entries(cfg.pending_file)
        assert remaining == []

    def test_sends_error_after_max_retries(self, tmp_path):
        cfg = _make_config(tmp_path)
        cfg.pending_max_retries = 2
        ensure_files(cfg)

        transcript_file = tmp_path / "t.txt"
        transcript_file.write_text("text")

        job = _make_job(transcript_path=str(transcript_file))
        # attempts=2 equals max_retries=2, so it should send the failure message
        write_pending_entries(cfg.pending_file, [PendingEntry(job=job, attempts=2)])

        with patch("summarizer.summarize_and_send", side_effect=RuntimeError("summary failed")), \
             patch("summarizer.load_transcript", return_value="text"), \
             patch("summarizer.send_discord") as mock_send:
            process_pending_summaries(cfg, MagicMock())

        mock_send.assert_called_once()
        assert "failed" in mock_send.call_args[0][1].lower()
