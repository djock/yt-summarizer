# YouTube Summarizer

Automates YouTube audio download, Whisper transcription, Gemini summarization, and Discord posting.

## Requirements
- Docker (recommended), or Python 3.11 with `ffmpeg`, `yt-dlp`, and `whisper-cli` available.

## Configuration
Create a `.env` file from the example and set your secrets:

```bash
cp .env.example .env
```

Required variables:
- `DISCORD_WEBHOOK_URL`
- `GEMINI_API_KEY`

## Run with Docker
Build the image:

```bash
docker build -t yt-summarizer .
```

Run once with environment and persistent archive:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/processed_videos.txt:/data/processed_videos.txt" \
  yt-summarizer
```

Run with auto-restart on reboot (no `--rm`):

```bash
docker run -d \
  --name yt-summarizer \
  --env-file .env \
  -v "$PWD/processed_videos.txt:/data/processed_videos.txt" \
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
0 8 * * * TZ=Europe/Helsinki docker run --rm --env-file /path/to/.env -v /path/to/processed_videos.txt:/data/processed_videos.txt yt-summarizer
```

This keeps scheduling on the host and avoids bundling cron inside the container.
If you want the container always running, use the `--restart unless-stopped` option instead of cron.

Edit your crontab with:

```bash
crontab -e
```

## Run without Docker
Ensure dependencies are installed, then:

```bash
export DISCORD_WEBHOOK_URL="..."
export GEMINI_API_KEY="..."
python summarizer.py
```
