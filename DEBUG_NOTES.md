# Debug Notes: yt-dlp Audio Download Failure

## Symptom
`yt-dlp did not produce a usable audio output` error when running the pipeline on Raspberry Pi (ARM64).

## Root Cause
Two compounding issues introduced after commit `9d0520b`:

### 1. `--print` implies `--simulate` in newer yt-dlp
The pipeline uses `--print "%(channel)s||%(title)s||%(duration_string)s"` to extract video metadata alongside the download. In newer yt-dlp versions, `--print` implies `--simulate` (no actual download). yt-dlp prints the metadata from the info dict and exits 0 — without downloading or converting anything. This is why no audio file is ever produced, yet no error is raised.

**Fix:** Add `--no-simulate` to the yt-dlp args to force the actual download alongside `--print`.

### 2. Android player client requires GVS PO Token on newer yt-dlp
The pipeline's first attempt uses `--extractor-args youtube:player_client=android`. On newer yt-dlp (as installed on the Pi), the android client's HTTPS formats require a GVS PO Token. Without it, all android formats are skipped and yt-dlp again exits 0 with no file produced.

**Fix:** The fallback chain (non-android attempts) must be tried if the first attempt produces no audio file. The pipeline was breaking out of the fallback loop on first successful command exit, even if no file was created. Fixed by checking for the audio file inside the loop before breaking.

## What Was Changed
- `pipeline/fetch.py`: Added `--no-simulate` to yt-dlp args
- `pipeline/fetch.py`: Moved `_resolve_audio_path` check inside the fallback loop so a missing audio file triggers the next fallback instead of raising immediately
- `pipeline/fetch.py`: Added `%(ext)s` to the `-o` output template for predictable filenames
- `pipeline/fetch.py`: Log yt-dlp stderr as WARNING when non-empty

## Last Known Working State
Commit `9d0520b3760ab59e1470beb5547899dafd7a7dd1` — different run command and archive file path:

```bash
touch processed_videos.txt
docker run --rm --env-file .env -v "$PWD/processed_videos.txt:/data/processed_videos.txt" yt-summarizer
```

## Current State
Fixes applied but not yet verified on Pi. To test:
1. SCP updated `pipeline/fetch.py` to Pi
2. `docker build -t yt-summarizer .`
3. `docker run --rm --env-file .env -v "$PWD/data:/data" yt-summarizer`
