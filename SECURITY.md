# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not open a public GitHub issue**.

Instead, report it by opening a [GitHub Security Advisory](https://github.com/djock/youtube-summary-discord/security/advisories/new) (private disclosure). We will respond as quickly as possible.

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce or a proof-of-concept (if applicable)
- Any suggested mitigations

## Scope

This project handles:
- API keys (Gemini, OpenAI) loaded from environment variables
- A Discord webhook URL
- Local file I/O for state files and transcripts
- Subprocess execution of `yt-dlp` and `whisper-cli`

Vulnerabilities in third-party dependencies (`yt-dlp`, `google-genai`, `requests`) should be reported to their respective maintainers.

## Security notes for self-hosters

- Never commit `.env` or any file containing secrets.
- Run the container with a non-root user in production if possible.
- Restrict access to the `DATA_DIR` volume, as it contains transcripts.
- Rotate your Discord webhook URL if you suspect it has been exposed.
