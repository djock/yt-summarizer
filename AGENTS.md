# Repository Guidelines

## Project Structure

```
core/        — Config dataclass, Job/PendingEntry models, state file I/O (archive, pending queue)
pipeline/    — fetch.py (yt-dlp download), transcribe.py (Whisper), summarize.py (LLM providers), notify.py (Discord)
utils/       — retry.py (RetryPolicy, run_with_retry), subprocess_utils.py (run_command, CommandError)
summarizer.py — entry point; orchestrates the full pipeline
tests/       — pytest test suite (114+ tests)
```

## Build, Test, and Development Commands

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v --cov

# Lint
ruff check .

# Type check (covers all packages)
mypy core pipeline utils summarizer.py

# All checks at once
make check

# Build Docker image
docker build -t yt-summarizer .

# Run with Docker
docker run --rm --env-file .env -v "$PWD/data:/data" yt-summarizer
```

## Key Conventions

- Language: Python 3.11
- Indentation: 4 spaces
- Naming: `snake_case` for functions/variables, `UPPER_SNAKE_CASE` for constants
- Logging: use `logging.getLogger(__name__)` — no bare `print()`
- All new code must pass `ruff check .` and `mypy`

## Testing Guidelines

- Tests live in `tests/test_*.py` using pytest
- Use `unittest.mock.patch` to mock external calls (yt-dlp, whisper, Discord, LLM APIs)
- A `conftest.py` handles `sys.path` so tests can import `core`, `pipeline`, and `utils` without installing the package
- CI enforces a coverage threshold (`--cov-fail-under=70`)

## Configuration

All settings are loaded from environment variables in `core/config.py`. Required variables:
- `DISCORD_WEBHOOK_URL`
- `CHANNELS` (comma-separated, e.g. `@MyChannel`)
- `GEMINI_API_KEY` or `OPENAI_API_KEY` depending on `SUMMARY_PROVIDER`

## Security Notes

- Secrets are loaded from `.env` or environment variables — never commit `.env`
- State files live under `DATA_DIR` (default `/data`) — treat as durable state
- See `SECURITY.md` for vulnerability reporting
