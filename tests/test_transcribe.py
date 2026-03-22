import gzip
import os
from unittest.mock import MagicMock, patch

from pipeline.transcribe import _build_whisper_env, load_transcript, save_transcript, transcribe_audio


def _make_config(tmp_path):
    cfg = MagicMock()
    cfg.whisper_bin = "./whisper-cli"
    cfg.whisper_model = "models/ggml-tiny.bin"
    cfg.whisper_threads = 4
    cfg.whisper_timeout_s = 60
    cfg.transcripts_dir = str(tmp_path / "transcripts")
    return cfg


class TestLoadTranscript:
    def test_loads_plain_text_file(self, tmp_path):
        f = tmp_path / "transcript.txt"
        f.write_text("hello world")
        assert load_transcript(str(f)) == "hello world"

    def test_loads_gzipped_file(self, tmp_path):
        f = tmp_path / "transcript.txt.gz"
        with gzip.open(str(f), "wt") as handle:
            handle.write("compressed transcript")
        assert load_transcript(str(f)) == "compressed transcript"

    def test_gzip_detected_by_extension(self, tmp_path):
        gz = tmp_path / "t.txt.gz"
        plain = tmp_path / "t.txt"
        with gzip.open(str(gz), "wt") as h:
            h.write("gz content")
        plain.write_text("plain content")
        assert load_transcript(str(gz)) == "gz content"
        assert load_transcript(str(plain)) == "plain content"


class TestSaveTranscript:
    def test_creates_transcripts_dir(self, tmp_path):
        cfg = _make_config(tmp_path)
        path = save_transcript("vid1", "text", cfg)
        assert os.path.exists(path)

    def test_saves_as_gzip(self, tmp_path):
        cfg = _make_config(tmp_path)
        path = save_transcript("vid1", "my transcript", cfg)
        assert path.endswith(".txt.gz")
        with gzip.open(path, "rt") as h:
            assert h.read() == "my transcript"

    def test_filename_uses_video_id(self, tmp_path):
        cfg = _make_config(tmp_path)
        path = save_transcript("abc123", "text", cfg)
        assert "abc123" in path

    def test_round_trip(self, tmp_path):
        cfg = _make_config(tmp_path)
        original = "line one\nline two\nline three"
        path = save_transcript("roundtrip", original, cfg)
        assert load_transcript(path) == original


class TestTranscribeAudio:
    def test_builds_ld_library_path_from_binary_dir(self, monkeypatch):
        monkeypatch.setenv("LD_LIBRARY_PATH", "/existing/lib")

        env = _build_whisper_env("./bin/whisper-cli")

        assert env["LD_LIBRARY_PATH"].endswith("bin:/existing/lib")

    def test_sets_ld_library_path_when_running_whisper(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_text("")
        (tmp_path / "audio.wav.txt").write_text("text")
        whisper_dir = tmp_path / "whisper"
        whisper_dir.mkdir()

        cfg = _make_config(tmp_path)
        cfg.whisper_bin = str(whisper_dir / "whisper-cli")

        with patch("pipeline.transcribe.run_command") as mock_run:
            mock_run.return_value = MagicMock()
            transcribe_audio(str(audio), cfg)

        env = mock_run.call_args[1]["env"]
        assert env["LD_LIBRARY_PATH"].split(":")[0] == str(whisper_dir.resolve())

    def test_reads_output_txt_file(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_text("")
        txt = tmp_path / "audio.wav.txt"
        txt.write_text("transcribed text")

        cfg = _make_config(tmp_path)
        with patch("pipeline.transcribe.run_command") as mock_run:
            mock_run.return_value = MagicMock()
            result = transcribe_audio(str(audio), cfg)

        assert result == "transcribed text"

    def test_passes_correct_args_to_whisper(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_text("")
        (tmp_path / "audio.wav.txt").write_text("text")

        cfg = _make_config(tmp_path)
        with patch("pipeline.transcribe.run_command") as mock_run:
            mock_run.return_value = MagicMock()
            transcribe_audio(str(audio), cfg)

        args = mock_run.call_args[0][0]
        assert cfg.whisper_bin in args
        assert cfg.whisper_model in args
        assert str(audio) in args
        assert "-t" in args
        assert str(cfg.whisper_threads) in args
        assert mock_run.call_args[1]["timeout_s"] == cfg.whisper_timeout_s
