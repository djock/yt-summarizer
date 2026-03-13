# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.1.0] - 2026-03-09

### Added
- Structured logging via Python's `logging` module; `LOG_LEVEL` env var controls verbosity (default `INFO`).
- Configurable retry policies: `DOWNLOAD_MAX_RETRIES`, `DOWNLOAD_RETRY_DELAYS`, `SUMMARY_MAX_RETRIES`, `SUMMARY_RETRY_DELAYS`, `DISCORD_MAX_RETRIES`, `DISCORD_RETRY_DELAYS`, `PENDING_MAX_RETRIES`.
- `Config.validate()` performs fail-fast startup checks and reports all configuration errors at once.
- Channel handle validation: `@handle` format enforced before any network calls.
- `fcntl` import now emits a `WARNING` log on non-Unix platforms (e.g. Windows) rather than silently disabling locking.
- `pyproject.toml` for project metadata and tool configuration (pytest, ruff, mypy).
- GitHub Actions CI pipeline running pytest, ruff, and mypy on every push and pull request.
- GitHub issue templates (bug report, feature request) and pull request template.
- `HEALTHCHECK` in Dockerfile for production deployments.
- Whisper model download documentation in README.

### Changed
- `SummaryProviderWrapper` and `send_discord` now accept an optional `RetryPolicy` parameter; callers use config-driven policies.
- `build_provider()` passes the config-driven `summary_retry_policy()` to `SummaryProviderWrapper`.
- Logging configuration is set up before any other work in `main()`.

## [1.0.0] - 2025-04-01

### Added
- Initial release: YouTube audio download via `yt-dlp`, transcription via `whisper.cpp`, summarization via Gemini or OpenAI, Discord posting via webhook.
- Persistent archive (`processed_videos.txt`) to skip already-processed videos.
- Pending summaries queue (`pending_summaries.txt`) with retry logic for failed Discord posts.
- Configurable channels, models, timeouts, chunk sizes via environment variables.
- Multi-stage Dockerfile with compiled `whisper-cli` and bundled `ggml-small.bin`.
- Docker Compose support for always-on deployments.
- Cron-based scheduling documentation.
