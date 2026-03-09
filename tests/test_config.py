import argparse
import os
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Config, _split_csv, parse_args


def _empty_args(**kwargs) -> argparse.Namespace:
    defaults = dict(
        provider=None,
        channels=None,
        data_dir=None,
        archive_file=None,
        pending_file=None,
        transcripts_dir=None,
        temp_dir=None,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestSplitCsv:
    def test_basic(self):
        assert _split_csv("a,b,c") == ["a", "b", "c"]

    def test_strips_whitespace(self):
        assert _split_csv("  a , b , c  ") == ["a", "b", "c"]

    def test_skips_empty_entries(self):
        assert _split_csv("a,,b") == ["a", "b"]

    def test_single_item(self):
        assert _split_csv("@channel") == ["@channel"]

    def test_empty_string(self):
        assert _split_csv("") == []


class TestConfigFromEnv:
    def test_webhook_from_env(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/hook")
        monkeypatch.setenv("CHANNELS", "@test")
        cfg = Config.from_env(_empty_args())
        assert cfg.webhook_url == "https://discord.example/hook"

    def test_missing_webhook_defaults_to_empty_string(self, monkeypatch):
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("CHANNELS", "@test")
        cfg = Config.from_env(_empty_args())
        assert cfg.webhook_url == ""

    def test_channels_from_env(self, monkeypatch):
        monkeypatch.setenv("CHANNELS", "@chan1,@chan2")
        cfg = Config.from_env(_empty_args())
        assert cfg.channels == ["@chan1", "@chan2"]

    def test_channels_from_args_override_env(self, monkeypatch):
        monkeypatch.setenv("CHANNELS", "@env_chan")
        args = _empty_args(channels=["@arg_chan"])
        cfg = Config.from_env(args)
        assert cfg.channels == ["@arg_chan"]

    def test_empty_channels_when_env_not_set(self, monkeypatch):
        monkeypatch.delenv("CHANNELS", raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.channels == []

    def test_provider_default_is_gemini(self, monkeypatch):
        monkeypatch.delenv("SUMMARY_PROVIDER", raising=False)
        monkeypatch.setenv("CHANNELS", "@test")
        cfg = Config.from_env(_empty_args())
        assert cfg.summary_provider == "gemini"

    def test_provider_from_env(self, monkeypatch):
        monkeypatch.setenv("SUMMARY_PROVIDER", "openai")
        monkeypatch.setenv("CHANNELS", "@test")
        cfg = Config.from_env(_empty_args())
        assert cfg.summary_provider == "openai"

    def test_provider_from_args_overrides_env(self, monkeypatch):
        monkeypatch.setenv("SUMMARY_PROVIDER", "gemini")
        args = _empty_args(provider="openai")
        cfg = Config.from_env(args)
        assert cfg.summary_provider == "openai"

    def test_provider_lowercased(self, monkeypatch):
        monkeypatch.setenv("SUMMARY_PROVIDER", "  GEMINI  ")
        cfg = Config.from_env(_empty_args())
        assert cfg.summary_provider == "gemini"

    def test_data_dir_default(self, monkeypatch):
        monkeypatch.delenv("DATA_DIR", raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.data_dir == "/data"

    def test_data_dir_from_env(self, monkeypatch):
        monkeypatch.setenv("DATA_DIR", "/my/data")
        cfg = Config.from_env(_empty_args())
        assert cfg.data_dir == "/my/data"

    def test_data_dir_from_args_overrides_env(self, monkeypatch):
        monkeypatch.setenv("DATA_DIR", "/env/data")
        args = _empty_args(data_dir="/arg/data")
        cfg = Config.from_env(args)
        assert cfg.data_dir == "/arg/data"

    def test_archive_file_derived_from_data_dir(self, monkeypatch):
        monkeypatch.setenv("DATA_DIR", "/custom")
        monkeypatch.delenv("ARCHIVE_FILE", raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.archive_file == "/custom/processed_videos.txt"

    def test_timeout_defaults(self, monkeypatch):
        monkeypatch.delenv("YT_DLP_TIMEOUT_S", raising=False)
        monkeypatch.delenv("WHISPER_TIMEOUT_S", raising=False)
        monkeypatch.delenv("HTTP_TIMEOUT_S", raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.yt_dlp_timeout_s == 600
        assert cfg.whisper_timeout_s == 1800
        assert cfg.http_timeout_s == 60

    def test_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("YT_DLP_TIMEOUT_S", "300")
        monkeypatch.setenv("WHISPER_TIMEOUT_S", "900")
        monkeypatch.setenv("HTTP_TIMEOUT_S", "30")
        cfg = Config.from_env(_empty_args())
        assert cfg.yt_dlp_timeout_s == 300
        assert cfg.whisper_timeout_s == 900
        assert cfg.http_timeout_s == 30

    def test_gemini_api_key_none_when_not_set(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.gemini_api_key is None

    def test_openai_api_key_none_when_not_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.openai_api_key is None

    def test_discord_chunk_defaults(self, monkeypatch):
        monkeypatch.delenv("DISCORD_CHAR_LIMIT", raising=False)
        monkeypatch.delenv("DISCORD_CHUNK_SIZE", raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.discord_char_limit == 2000
        assert cfg.discord_chunk_size == 1900
