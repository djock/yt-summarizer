# Contributing

## Setup
- Python 3.11
- `ffmpeg`, `yt-dlp`, and `whisper-cli` available on PATH (or use Docker)

## Development
- Copy `.env.example` to `.env` and fill in required secrets.
- Run locally: `python summarizer.py`

## Coding Style
- Python 3.11
- 4-space indentation
- `snake_case` for functions/variables, `UPPER_SNAKE_CASE` for constants
- Keep logs consistent with the `log()` helper

## Known Limitations
- Whisper model and `whisper-cli` must be available in runtime image.
- Summaries depend on the configured provider and model quality.

## Pull Requests
- Explain user impact
- List configuration changes
- Include sample logs if behavior changes
