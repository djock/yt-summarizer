<p align="center">
  <img src="assets/banner.png" alt="YouTube Summarizer for Discord" width="300" />
</p>

# YouTube Summarizer for Discord

[![CI](https://github.com/djock/youtube-summary-discord/actions/workflows/ci.yml/badge.svg)](https://github.com/djock/youtube-summary-discord/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

Monitors YouTube channels, transcribes new videos with Whisper, summarizes with an LLM, and posts the summary to a Discord channel via webhook. Also supports a one-shot list mode to summarize a specific set of video IDs in order.

## How it works

```
fetch (yt-dlp) → transcribe (whisper.cpp) → summarize (Gemini / OpenAI) → notify (Discord webhook)
```

**Channel mode (default):** Each run checks configured channels for new videos, skipping any already in the archive. If a summary fails to send, the job is queued in a pending file and retried on the next run.

**List mode:** Pass a file of video IDs and the summarizer processes them in order, skipping any already in the archive (override with `--force`).

## Requirements

- Docker (recommended), or Python 3.11 with `ffmpeg`, `yt-dlp`, `nodejs`, and `whisper-cli` available on PATH.

## Configuration

Create a `.env` file from the example and fill in your secrets:

```bash
cp .env.example .env
```

**Required:**
| Variable | Description |
|---|---|
| `DISCORD_WEBHOOK_URL` | Discord incoming webhook URL |
| `GEMINI_API_KEY` | Required when `SUMMARY_PROVIDER=gemini` |
| `OPENAI_API_KEY` | Required when `SUMMARY_PROVIDER=openai` |
| `CHANNELS` | Comma-separated list of channel handles, e.g. `@MyChannel,@AnotherChannel` (not required when using `--video-ids-file`) |

**Optional:**
| Variable | Default | Description |
|---|---|---|
| `SUMMARY_PROVIDER` | `gemini` | `gemini` or `openai` |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite` | Gemini model name |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI model name |
| `DATA_DIR` | `/data` | Base directory for all state files |
| `ARCHIVE_FILE` | `/data/processed_videos.txt` | Archive of processed video IDs |
| `PENDING_FILE` | `/data/pending_summaries.txt` | Queue for retrying failed summaries |
| `TRANSCRIPTS_DIR` | `/data/transcripts` | Directory for saved transcripts |
| `TEMP_DIR` | `/data/tmp` | Temporary directory for audio files |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `WHISPER_BIN` | `./whisper-cli` | Path to `whisper-cli` binary |
| `WHISPER_MODEL` | `models/ggml-tiny.bin` | Path to Whisper GGML model |
| `DISCORD_CHUNK_SIZE` | `1900` | Max characters per Discord message chunk |
| `SUMMARY_BULLET_LIMIT` | `8` | Max bullet points in a summary |
| `YT_DLP_TIMEOUT_S` | `600` | Timeout for yt-dlp download (seconds) |
| `WHISPER_TIMEOUT_S` | `1800` | Timeout for Whisper transcription (seconds) |
| `HTTP_TIMEOUT_S` | `60` | Timeout for HTTP requests (seconds) |

**Retry tuning (all optional):**
| Variable | Default | Description |
|---|---|---|
| `DOWNLOAD_MAX_RETRIES` | `3` | Max download attempts |
| `DOWNLOAD_RETRY_DELAYS` | `10,20` | Delay between download retries (seconds) |
| `SUMMARY_MAX_RETRIES` | `5` | Max summarization attempts |
| `SUMMARY_RETRY_DELAYS` | `10,30,60,120` | Delay between summary retries |
| `DISCORD_MAX_RETRIES` | `5` | Max Discord send attempts |
| `DISCORD_RETRY_DELAYS` | `2,5,10,20` | Delay between Discord retries |
| `PENDING_MAX_RETRIES` | `5` | Attempts before a pending job is dropped |

## Run with Docker

Build the image:

```bash
docker build -t yt-summarizer .
```

Run once:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/data:/data" \
  yt-summarizer
```

Run with auto-restart on reboot:

```bash
docker run -d \
  --name yt-summarizer \
  --env-file .env \
  -v "$PWD/data:/data" \
  --restart unless-stopped \
  yt-summarizer
```

## Run with Docker Compose

```bash
docker build -t yt-summarizer .
docker compose up -d
docker compose logs -f
docker compose down
```

## Run on a schedule (cron)

Run daily at 08:00 in your local timezone:

```cron
0 8 * * * TZ=Your/Timezone docker run --rm --env-file /path/to/.env -v /path/to/data:/data yt-summarizer
```

Edit your crontab with `crontab -e`.

## Run without Docker

### 1. System dependencies

Install `ffmpeg`, `yt-dlp`, and Node.js via your package manager, then build `whisper-cli` from source:

```bash
git clone --depth 1 https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
cmake -B build && cmake --build build -j --config Release
cp build/bin/whisper-cli /usr/local/bin/whisper-cli
find build \( -name 'libwhisper.so*' -o -name 'libggml*.so*' \) -exec cp {} /usr/local/lib/ \;
```

### 2. Download a Whisper model

```bash
# From inside the whisper.cpp directory:
sh ./models/download-ggml-model.sh tiny
# Downloads models/ggml-tiny.bin (~75 MB)
```

Then configure the paths:

```bash
export WHISPER_BIN="/usr/local/bin/whisper-cli"
export WHISPER_MODEL="/path/to/whisper.cpp/models/ggml-tiny.bin"
export LD_LIBRARY_PATH="/usr/local/lib:${LD_LIBRARY_PATH}"
```

Available model sizes (larger = slower but more accurate): `tiny`, `base`, `small`, `medium`, `large`.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

**Channel mode** — check configured channels for new videos:

```bash
export DISCORD_WEBHOOK_URL="..."
export GEMINI_API_KEY="..."
export CHANNELS="@MyChannel"
python summarizer.py
```

**List mode** — summarize a specific set of video IDs in order:

```bash
# ids.txt: one video ID per line, blank lines and # comments are ignored
cat ids.txt
# dQw4w9WgXcQ
# abc123xyz

python summarizer.py --video-ids-file ids.txt

# Re-summarize even if already in the archive:
python summarizer.py --video-ids-file ids.txt --force
```

## CLI reference

```
usage: summarizer.py [-h] [--provider {gemini,openai}] [--channels CH [CH ...]]
                     [--video-ids-file PATH] [--force]
                     [--data-dir DIR] [--archive-file FILE] ...

optional arguments:
  --provider            Summary provider (gemini|openai)
  --channels            One or more channel handles (overrides CHANNELS env var)
  --video-ids-file      Path to a file with one YouTube video ID per line;
                        activates list mode (CHANNELS not required)
  --force               Re-summarize videos already in the archive
  --data-dir            Base data directory (overrides DATA_DIR env var)
```

## State files

| File | Description |
|---|---|
| `processed_videos.txt` | Archive of processed video IDs (one per line). Delete an ID to reprocess, or use `--force` in list mode. |
| `pending_summaries.txt` | JSONL queue of jobs that failed Discord delivery and are awaiting retry. |
| `transcripts/*.txt.gz` | Gzipped transcripts, kept for pending-summary retries. |

## Troubleshooting

**`whisper-cli: command not found`** — Set `WHISPER_BIN` to the full path of the binary, or ensure it is on your `PATH`.

**`libwhisper.so.1` or `libggml.so.0: cannot open shared object file`** — Install all Whisper runtime libraries (`libwhisper.so*` and `libggml*.so*`) alongside the binary or into a loader path such as `/usr/local/lib`, then export `LD_LIBRARY_PATH` if needed.

**`models/ggml-tiny.bin: no such file`** — Set `WHISPER_MODEL` to the full path of the downloaded model file.

**yt-dlp fails or hangs** — YouTube anti-bot measures change frequently. Update yt-dlp (`pip install -U yt-dlp`) and ensure Node.js is installed (required for JS player extraction).

**Discord rate-limit errors** — Tune `DISCORD_MAX_RETRIES` and `DISCORD_RETRY_DELAYS`. The bot backs off automatically on 429 responses.

**Summary is empty or malformed** — Enable `LOG_LEVEL=DEBUG` to inspect the raw transcript and provider response.

## Security

- Do not commit `.env` or any file containing secrets.
- The project handles API keys and webhook URLs; see [SECURITY.md](SECURITY.md) for responsible disclosure.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Found a bug? [Open an issue](https://github.com/djock/youtube-summary-discord/issues).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
