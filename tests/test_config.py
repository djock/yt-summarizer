import argparse
import os
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import Config, _split_csv, _split_ints, parse_args
from retry import RetryPolicy


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

    def test_log_level_default(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.log_level == "INFO"

    def test_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        cfg = Config.from_env(_empty_args())
        assert cfg.log_level == "DEBUG"

    def test_retry_policy_defaults(self, monkeypatch):
        for key in ("DOWNLOAD_MAX_RETRIES", "DOWNLOAD_RETRY_DELAYS",
                    "SUMMARY_MAX_RETRIES", "SUMMARY_RETRY_DELAYS",
                    "DISCORD_MAX_RETRIES", "DISCORD_RETRY_DELAYS", "PENDING_MAX_RETRIES"):
            monkeypatch.delenv(key, raising=False)
        cfg = Config.from_env(_empty_args())
        assert cfg.download_max_retries == 3
        assert cfg.download_retry_delays == [10, 20]
        assert cfg.summary_max_retries == 5
        assert cfg.summary_retry_delays == [10, 30, 60, 120]
        assert cfg.discord_max_retries == 5
        assert cfg.discord_retry_delays == [2, 5, 10, 20]
        assert cfg.pending_max_retries == 5

    def test_retry_policy_from_env(self, monkeypatch):
        monkeypatch.setenv("DOWNLOAD_MAX_RETRIES", "2")
        monkeypatch.setenv("DOWNLOAD_RETRY_DELAYS", "5,15")
        cfg = Config.from_env(_empty_args())
        assert cfg.download_max_retries == 2
        assert cfg.download_retry_delays == [5, 15]


class TestSplitInts:
    def test_basic(self):
        assert _split_ints("1,2,3") == [1, 2, 3]

    def test_strips_whitespace(self):
        assert _split_ints("1, 2, 3") == [1, 2, 3]

    def test_skips_empty(self):
        assert _split_ints("1,,3") == [1, 3]

    def test_single(self):
        assert _split_ints("10") == [10]

    def test_empty_string(self):
        assert _split_ints("") == []


class TestRetryPolicies:
    def _make_cfg(self, **overrides):
        base = dict(
            webhook_url="https://example.com/hook",
            summary_provider="gemini",
            gemini_api_key="key",
            gemini_model="m",
            openai_api_key=None,
            openai_model="m",
            channels=["@test"],
            data_dir="/data",
            archive_file="/data/a.txt",
            pending_file="/data/p.txt",
            transcripts_dir="/data/t",
            temp_dir="/data/tmp",
            whisper_bin="./w",
            whisper_model="m.bin",
            discord_char_limit=2000,
            discord_chunk_size=1900,
            summary_bullet_limit=8,
            yt_dlp_timeout_s=600,
            whisper_timeout_s=1800,
            http_timeout_s=60,
            log_level="INFO",
            download_max_retries=3,
            download_retry_delays=[10, 20],
            summary_max_retries=5,
            summary_retry_delays=[10, 30, 60, 120],
            discord_max_retries=5,
            discord_retry_delays=[2, 5, 10, 20],
            pending_max_retries=5,
        )
        base.update(overrides)
        return Config(**base)

    def test_download_retry_policy(self):
        cfg = self._make_cfg(download_max_retries=2, download_retry_delays=[5, 15])
        policy = cfg.download_retry_policy()
        assert isinstance(policy, RetryPolicy)
        assert policy.max_attempts == 2
        assert list(policy.delays_s) == [5, 15]

    def test_summary_retry_policy(self):
        cfg = self._make_cfg(summary_max_retries=3, summary_retry_delays=[1, 2, 4])
        policy = cfg.summary_retry_policy()
        assert policy.max_attempts == 3
        assert list(policy.delays_s) == [1, 2, 4]

    def test_discord_retry_policy(self):
        cfg = self._make_cfg(discord_max_retries=4, discord_retry_delays=[1, 2, 3])
        policy = cfg.discord_retry_policy()
        assert policy.max_attempts == 4
        assert list(policy.delays_s) == [1, 2, 3]


class TestConfigValidate:
    def _make_cfg(self, **overrides):
        base = dict(
            webhook_url="https://example.com/hook",
            summary_provider="gemini",
            gemini_api_key="key123",
            gemini_model="m",
            openai_api_key=None,
            openai_model="m",
            channels=["@test"],
            data_dir="/data",
            archive_file="/data/a.txt",
            pending_file="/data/p.txt",
            transcripts_dir="/data/t",
            temp_dir="/data/tmp",
            whisper_bin="./w",
            whisper_model="m.bin",
            discord_char_limit=2000,
            discord_chunk_size=1900,
            summary_bullet_limit=8,
            yt_dlp_timeout_s=600,
            whisper_timeout_s=1800,
            http_timeout_s=60,
            log_level="INFO",
            download_max_retries=3,
            download_retry_delays=[10, 20],
            summary_max_retries=5,
            summary_retry_delays=[10, 30, 60, 120],
            discord_max_retries=5,
            discord_retry_delays=[2, 5, 10, 20],
            pending_max_retries=5,
        )
        base.update(overrides)
        return Config(**base)

    def test_valid_config_passes(self):
        self._make_cfg().validate()  # should not raise

    def test_missing_webhook_raises(self):
        with pytest.raises(RuntimeError, match="DISCORD_WEBHOOK_URL"):
            self._make_cfg(webhook_url="").validate()

    def test_missing_gemini_key_raises(self):
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            self._make_cfg(gemini_api_key=None).validate()

    def test_missing_openai_key_raises(self):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            self._make_cfg(summary_provider="openai", openai_api_key=None).validate()

    def test_invalid_provider_raises(self):
        with pytest.raises(RuntimeError, match="SUMMARY_PROVIDER"):
            self._make_cfg(summary_provider="unknown").validate()

    def test_empty_channels_raises(self):
        with pytest.raises(RuntimeError, match="CHANNELS"):
            self._make_cfg(channels=[]).validate()

    def test_multiple_errors_reported_together(self):
        with pytest.raises(RuntimeError) as exc_info:
            self._make_cfg(webhook_url="", channels=[]).validate()
        msg = str(exc_info.value)
        assert "DISCORD_WEBHOOK_URL" in msg
        assert "CHANNELS" in msg

    def test_valid_openai_config_passes(self):
        self._make_cfg(summary_provider="openai", openai_api_key="sk-test").validate()
