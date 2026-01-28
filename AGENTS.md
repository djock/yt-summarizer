# Repository Guidelines

## Project Structure & Module Organization
- `summarizer.py` is the main entry point; it downloads audio, transcribes with Whisper, summarizes with Gemini, and posts to Discord.
- `Dockerfile` builds the runtime image and compiles `whisper.cpp`.
- `processed_videos.txt` is the local archive of processed YouTube IDs; the container expects it at `/data/processed_videos.txt`.
- `.env` holds required secrets (`DISCORD_WEBHOOK_URL`, `GEMINI_API_KEY`); see `.env.example`.

## Build, Test, and Development Commands
- Build the container image:
  - `docker build -t yt-summarizer .`
- Run locally with a persistent archive:
  - `docker run --rm --env-file .env -v "$PWD/processed_videos.txt:/data/processed_videos.txt" yt-summarizer`
- Run without Docker (requires `ffmpeg`, `yt-dlp`, `whisper-cli`, and Python deps):
  - `python summarizer.py`

## Coding Style & Naming Conventions
- Language: Python 3.11.
- Indentation: 4 spaces.
- Naming: `snake_case` for functions/variables, `UPPER_SNAKE_CASE` for constants (see `WEBHOOK_URL`, `GEMINI_API_KEY`).
- Keep logs in the `log()` helper for consistent output.

## Testing Guidelines
- No automated tests are currently present.
- If adding tests, prefer `pytest` and place them under a `tests/` directory with `test_*.py` naming.

## Commit & Pull Request Guidelines
- Git history only includes `Initial commit`, so no established convention yet.
- Use short, imperative commit subjects (e.g., `Add retry for Discord webhook`).
- PRs should explain the user impact, list configuration changes, and include sample logs or screenshots if output changes.

## Security & Configuration Tips
- Secrets are provided via `.env` or environment variables; do not commit `.env`.
- Treat `/data/processed_videos.txt` as durable state; avoid deleting it unless you intend to reprocess channels.
