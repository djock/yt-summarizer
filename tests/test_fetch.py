from unittest.mock import MagicMock, patch

import pytest

from pipeline.fetch import (
    _yt_dlp_base_args,
    download_audio_and_metadata,
    get_latest_video_id,
    validate_channel_handle,
)
from utils.subprocess_utils import CommandError, CommandResult


def _make_config():
    cfg = MagicMock()
    cfg.yt_dlp_timeout_s = 60
    return cfg


class TestValidateChannelHandle:
    def test_valid_simple_handle(self):
        validate_channel_handle("@MyChannel")  # should not raise

    def test_valid_with_numbers(self):
        validate_channel_handle("@channel123")

    def test_valid_with_dots(self):
        validate_channel_handle("@my.channel")

    def test_valid_with_hyphens(self):
        validate_channel_handle("@my-channel")

    def test_valid_with_underscores(self):
        validate_channel_handle("@my_channel")

    def test_valid_uppercase(self):
        validate_channel_handle("@MYCHANNEL")

    def test_missing_at_sign_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("MyChannel")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("")

    def test_only_at_sign_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("@")

    def test_spaces_in_handle_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("@my channel")

    def test_url_style_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("https://youtube.com/@channel")

    def test_special_chars_raise(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("@chan!nel")

    def test_error_message_includes_bad_value(self):
        with pytest.raises(ValueError, match="badvalue"):
            validate_channel_handle("badvalue")


class TestGetLatestVideoId:
    def test_returns_stripped_video_id(self):
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="  dQw4w9WgXcQ\n", stderr="")
            result = get_latest_video_id("@TestChannel", timeout_s=30)
        assert result == "dQw4w9WgXcQ"

    def test_falls_back_when_first_command_fails(self):
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.side_effect = [
                CommandError("command failed"),
                CommandResult(stdout="fallback-id\n", stderr=""),
            ]
            result = get_latest_video_id("@TestChannel", timeout_s=30)

        assert result == "fallback-id"
        assert mock_run.call_count == 2

    def test_validates_channel_handle_first(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            get_latest_video_id("no-at-sign", timeout_s=30)


class TestYtDlpBaseArgs:
    def test_prefers_node_when_present(self):
        with patch("pipeline.fetch.shutil.which") as mock_which:
            mock_which.side_effect = ["/usr/bin/node", None]
            assert _yt_dlp_base_args() == ["yt-dlp", "--js-runtimes", "node"]

    def test_uses_nodejs_when_node_missing(self):
        with patch("pipeline.fetch.shutil.which") as mock_which:
            mock_which.side_effect = [None, "/usr/bin/nodejs"]
            assert _yt_dlp_base_args() == ["yt-dlp", "--js-runtimes", "nodejs"]

    def test_omits_js_runtime_when_no_binary_is_available(self):
        with patch("pipeline.fetch.shutil.which", return_value=None):
            assert _yt_dlp_base_args() == ["yt-dlp"]


class TestDownloadAudioAndMetadata:
    def test_parses_metadata_from_stdout(self, tmp_path):
        cfg = _make_config()
        expected_audio = tmp_path / "abc123.wav"
        expected_audio.write_text("")
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(
                stdout="My Channel||My Video Title||10:32\n",
                stderr=""
            )
            job, audio_path, stderr = download_audio_and_metadata("abc123", cfg, str(tmp_path))

        assert job.video_id == "abc123"
        assert job.channel_name == "My Channel"
        assert job.title == "My Video Title"
        assert job.duration == "10:32"
        assert job.url == "https://www.youtube.com/watch?v=abc123"

    def test_audio_path_uses_wav_extension(self, tmp_path):
        cfg = _make_config()
        expected_audio = tmp_path / "vid1.wav"
        expected_audio.write_text("")
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="Chan||Title||5:00\n", stderr="")
            _, audio_path, _ = download_audio_and_metadata("vid1", cfg, str(tmp_path))

        assert audio_path.endswith(".wav")
        assert "vid1" in audio_path
        assert mock_run.call_args[0][0][-2] == str(tmp_path / "vid1.%(ext)s")

    def test_audio_path_falls_back_to_matching_generated_wav(self, tmp_path):
        cfg = _make_config()
        generated_audio = tmp_path / "vid1.f251.wav"
        generated_audio.write_text("")

        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="Chan||Title||5:00\n", stderr="")
            _, audio_path, _ = download_audio_and_metadata("vid1", cfg, str(tmp_path))

        assert audio_path == str(generated_audio)

    def test_audio_path_falls_back_to_single_non_wav_audio_file(self, tmp_path):
        cfg = _make_config()
        generated_audio = tmp_path / "vid1.webm"
        generated_audio.write_text("")

        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="Chan||Title||5:00\n", stderr="")
            _, audio_path, _ = download_audio_and_metadata("vid1", cfg, str(tmp_path))

        assert audio_path == str(generated_audio)

    def test_audio_path_falls_back_to_extensionless_output_base_file(self, tmp_path):
        cfg = _make_config()
        generated_audio = tmp_path / "vid1"
        generated_audio.write_text("")

        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="Chan||Title||5:00\n", stderr="")
            _, audio_path, _ = download_audio_and_metadata("vid1", cfg, str(tmp_path))

        assert audio_path == str(generated_audio)

    def test_audio_path_falls_back_to_single_audio_file_with_unexpected_name(self, tmp_path):
        cfg = _make_config()
        generated_audio = tmp_path / "downloaded-track.m4a"
        generated_audio.write_text("")

        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="Chan||Title||5:00\n", stderr="")
            _, audio_path, _ = download_audio_and_metadata("vid1", cfg, str(tmp_path))

        assert audio_path == str(generated_audio)

    def test_raises_when_no_metadata_returned(self, tmp_path):
        cfg = _make_config()
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="", stderr="")
            with pytest.raises(CommandError, match="metadata"):
                download_audio_and_metadata("vid1", cfg, str(tmp_path))

    def test_raises_when_audio_output_is_missing(self, tmp_path):
        cfg = _make_config()
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="Chan||Title||5:00\n", stderr="")

            with pytest.raises(CommandError, match="did not produce a usable audio output"):
                download_audio_and_metadata("vid1", cfg, str(tmp_path))

    def test_stderr_is_returned(self, tmp_path):
        cfg = _make_config()
        expected_audio = tmp_path / "vid1.wav"
        expected_audio.write_text("")
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="Chan||Title||5:00\n", stderr="some warning")
            _, _, stderr = download_audio_and_metadata("vid1", cfg, str(tmp_path))

        assert stderr == "some warning"

    def test_falls_back_when_android_client_command_fails(self, tmp_path):
        cfg = _make_config()
        expected_audio = tmp_path / "vid1.wav"
        expected_audio.write_text("")
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.side_effect = [
                CommandError("command failed"),
                CommandResult(stdout="Chan||Title||5:00\n", stderr=""),
            ]
            job, _, _ = download_audio_and_metadata("vid1", cfg, str(tmp_path))

        assert job.title == "Title"
        assert mock_run.call_count == 2

    def test_passes_configured_timeout(self, tmp_path):
        cfg = _make_config()
        cfg.yt_dlp_timeout_s = 300
        expected_audio = tmp_path / "vid1.wav"
        expected_audio.write_text("")
        with patch("pipeline.fetch.run_command") as mock_run:
            mock_run.return_value = CommandResult(stdout="Chan||Title||1:00\n", stderr="")
            download_audio_and_metadata("vid1", cfg, str(tmp_path))

        assert mock_run.call_args[1]["timeout_s"] == 300
