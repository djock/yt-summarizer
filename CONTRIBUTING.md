# Contributing

Contributions are welcome — bug fixes, new summary providers, documentation improvements, and tests are all appreciated.

## Setup

**Prerequisites:** Python 3.11, `ffmpeg`, `yt-dlp`, `nodejs`, and `whisper-cli` available on PATH (or use Docker).

```bash
git clone https://github.com/djock/youtube-summary-discord
cd youtube-summary-discord
pip install -e ".[dev]"
cp .env.example .env   # fill in your secrets
```

## Development commands

```bash
make test       # run the test suite with coverage
make lint       # ruff lint check
make typecheck  # mypy type check
make check      # run all three
```

Or run them individually:

```bash
pytest tests/ -v --cov
ruff check .
mypy core pipeline utils summarizer.py
```

## Project structure

```
core/        — Config, data models, state file I/O
pipeline/    — fetch (yt-dlp), transcribe (Whisper), summarize (LLM), notify (Discord)
utils/       — retry policy, subprocess helpers
summarizer.py — entry point; orchestrates the pipeline
tests/       — pytest test suite
```

## Adding a summary provider

1. Subclass `SummaryProvider` in `pipeline/summarize.py` and implement `generate(prompt)`.
2. Register it in `build_provider()`.
3. Add it to `Config.validate()` and the `SUMMARY_PROVIDER` documentation in README.
4. Add tests in `tests/test_summarize.py`.

## Coding style

- Python 3.11, 4-space indentation
- `snake_case` for functions/variables, `UPPER_SNAKE_CASE` for constants
- Structured logging via `logging.getLogger(__name__)` — no bare `print()`
- Lint and type checking enforced by ruff and mypy in CI

## Pull requests

- Run `make check` before opening a PR
- Update `CHANGELOG.md` under `[Unreleased]`
- Update `README.md` if you add or change configuration variables

## Known limitations

- Whisper model and `whisper-cli` must be available in the runtime environment.
- Summary quality depends on the configured provider and model.
- `fcntl`-based file locking is not available on Windows; concurrent runs on that platform may cause data corruption.
