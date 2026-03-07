from dataclasses import dataclass
from typing import List

import requests

from config import Config
from retry import RetryPolicy, run_with_retry


@dataclass
class SummaryProvider:
    name: str
    max_input_chars: int

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class GeminiProvider(SummaryProvider):
    def __init__(self, api_key: str, model: str, max_input_chars: int = 24000):
        if not api_key:
            raise RuntimeError("Missing required environment variable: GEMINI_API_KEY")
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model
        super().__init__(name="gemini", max_input_chars=max_input_chars)

    def generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return response.text


class OpenAIProvider(SummaryProvider):
    def __init__(self, api_key: str, model: str, max_input_chars: int = 20000):
        if not api_key:
            raise RuntimeError("Missing required environment variable: OPENAI_API_KEY")
        self.api_key = api_key
        self.model = model
        super().__init__(name="openai", max_input_chars=max_input_chars)

    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that summarizes transcripts."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        resp = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class SummaryProviderWrapper:
    def __init__(self, provider: SummaryProvider):
        self.provider = provider
        self.retry_policy = RetryPolicy(max_attempts=5, delays_s=[10, 30, 60, 120])

    def _should_retry(self, exc: Exception) -> bool:
        msg = str(exc).lower()
        if any(token in msg for token in ["503", "unavailable", "overloaded", "timeout"]):
            return True
        if isinstance(exc, requests.HTTPError):
            status = exc.response.status_code if exc.response is not None else 0
            return status in (429, 500, 502, 503, 504)
        return False

    def generate(self, prompt: str) -> str:
        def call() -> str:
            return self.provider.generate(prompt)

        return run_with_retry(call, self.retry_policy, self._should_retry)


def build_provider(config: Config) -> SummaryProviderWrapper:
    if config.summary_provider == "gemini":
        provider = GeminiProvider(config.gemini_api_key, config.gemini_model)
    elif config.summary_provider == "openai":
        provider = OpenAIProvider(config.openai_api_key, config.openai_model)
    else:
        raise RuntimeError(f"Unsupported SUMMARY_PROVIDER: {config.summary_provider}")
    return SummaryProviderWrapper(provider)


def _build_prompt(transcript: str, max_chars: int, channel_name: str, bullet_limit: int) -> str:
    is_sam_sulek = channel_name.strip().lower() == "sam sulek"
    if is_sam_sulek:
        return (
            "Summarize this YouTube transcript into concise bullet points only. "
            f"Use at most {bullet_limit} bullets and keep the summary under {max_chars} characters. "
            "Do not include any title or heading; the title is provided separately. "
            "Always include a bullet list of exercises performed, with sets and kilograms if available:\n\n"
            f"{transcript}"
        )
    return (
        "Summarize this YouTube transcript into concise bullet points only. "
        f"Use at most {bullet_limit} bullets and keep the summary under {max_chars} characters. "
        "Do not include any title or heading; the title is provided separately:\n\n"
        f"{transcript}"
    )


def _chunk_text(text: str, max_chars: int) -> List[str]:
    if max_chars <= 0:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks


def summarize_transcript(wrapper: SummaryProviderWrapper, transcript: str, max_summary_chars: int, channel_name: str, bullet_limit: int) -> str:
    max_input = wrapper.provider.max_input_chars
    if len(transcript) <= max_input:
        prompt = _build_prompt(transcript, max_summary_chars, channel_name, bullet_limit)
        return wrapper.generate(prompt)

    # Chunk and condense
    chunk_size = max_input - 1000
    chunks = _chunk_text(transcript, chunk_size)
    partial_summaries = []
    for chunk in chunks:
        prompt = _build_prompt(chunk, max_summary_chars, channel_name, bullet_limit)
        partial_summaries.append(wrapper.generate(prompt))
    combined = "\n".join(partial_summaries)
    prompt = _build_prompt(combined, max_summary_chars, channel_name, bullet_limit)
    return wrapper.generate(prompt)
