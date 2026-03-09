# YouTube Summarizer

Automates YouTube audio download, Whisper transcription, LLM summarization, and Discord posting.

## Requirements
- Docker (recommended), or Python 3.11 with `ffmpeg`, `yt-dlp`, and `whisper-cli` available.

## Configuration
Create a `.env` file from the example and set your secrets:

```bash
cp .env.example .env
```

Required variables:
- `DISCORD_WEBHOOK_URL`
- `GEMINI_API_KEY` (when `SUMMARY_PROVIDER=gemini`)
- `OPENAI_API_KEY` (when `SUMMARY_PROVIDER=openai`)

Optional variables:
- `SUMMARY_PROVIDER` (`gemini` or `openai`, default: `gemini`)
- `GEMINI_MODEL` (default: `gemini-2.5-flash-lite`)
- `OPENAI_MODEL` (default: `gpt-4.1-mini`)
- `CHANNELS` (comma-separated list, default: `@sam_sulek,@TeamRICHEY,@NicksStrengthandPower`)
- `DATA_DIR` (default: `/data`)
- `ARCHIVE_FILE` (default: `/data/processed_videos.txt`)
- `PENDING_FILE` (default: `/data/pending_summaries.txt`)
- `TRANSCRIPTS_DIR` (default: `/data/transcripts`)
- `TEMP_DIR` (default: `/data/tmp`)
- `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, `ERROR`, default: `INFO`)

Retry tuning (all optional):
- `DOWNLOAD_MAX_RETRIES` (default: `3`)
- `DOWNLOAD_RETRY_DELAYS` (comma-separated seconds, default: `10,20`)
- `SUMMARY_MAX_RETRIES` (default: `5`)
- `SUMMARY_RETRY_DELAYS` (default: `10,30,60,120`)
- `DISCORD_MAX_RETRIES` (default: `5`)
- `DISCORD_RETRY_DELAYS` (default: `2,5,10,20`)
- `PENDING_MAX_RETRIES` (default: `5`)

## Run with Docker
Build the image:

```bash
docker build -t yt-summarizer .
```

Run once with environment and persistent archive:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/data:/data" \
  yt-summarizer
```

Run with auto-restart on reboot (no `--rm`):

```bash
docker run -d \
  --name yt-summarizer \
  --env-file .env \
  -v "$PWD/data:/data" \
  --restart unless-stopped \
  yt-summarizer
```

## Run with Docker Compose

Recommended for always-on runs with auto-restart.

```bash
docker build -t yt-summarizer .
docker compose up -d
```

Logs:

```bash
docker compose logs -f
```

Stop:

```bash
docker compose down
```

## Run on a Schedule (cron)
To run daily at 08:00 EEST on the Raspberry Pi host, add a cron entry that launches the container:

```cron
0 8 * * * TZ=Europe/Helsinki docker run --rm --env-file /path/to/.env -v /path/to/data:/data yt-summarizer
```

This keeps scheduling on the host and avoids bundling cron inside the container.
If you want the container always running, use the `--restart unless-stopped` option instead of cron.

Edit your crontab with:

```bash
crontab -e
```

## Run without Docker

### 1. System dependencies

Install `ffmpeg`, `yt-dlp`, and Node.js via your package manager, then build `whisper-cli` from source:

```bash
git clone --depth 1 https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
cmake -B build && cmake --build build -j --config Release
cp build/bin/whisper-cli /usr/local/bin/whisper-cli   # or any directory on PATH
```

### 2. Download a Whisper model

```bash
# From inside the whisper.cpp directory:
sh ./models/download-ggml-model.sh small
# Downloads models/ggml-small.bin (~466 MB)
```

Then tell the app where to find it:

```bash
export WHISPER_BIN="/usr/local/bin/whisper-cli"
export WHISPER_MODEL="/path/to/whisper.cpp/models/ggml-small.bin"
```

Available model sizes (larger = slower but more accurate): `tiny`, `base`, `small` (default), `medium`, `large`.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
export DISCORD_WEBHOOK_URL="..."
export GEMINI_API_KEY="..."
export CHANNELS="@MyChannel"
python summarizer.py
```

## State Files
- `/data/processed_videos.txt`: archive of processed YouTube IDs (one per line).
- `/data/pending_summaries.txt`: pending summaries in JSONL format (legacy `||` lines are still read).
- `/data/transcripts/`: gzipped transcripts (`.txt.gz`).

## Security
Do not commit `.env` or any file containing secrets.
