import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

from summarize import (
    SummaryProvider,
    SummaryProviderWrapper,
    OpenAIProvider,
    _build_prompt,
    _chunk_text,
    summarize_transcript,
)


class FakeProvider(SummaryProvider):
    def __init__(self, responses=None):
        super().__init__(name="fake", max_input_chars=100)
        self._responses = list(responses or ["summary text"])
        self._calls = []

    def generate(self, prompt: str) -> str:
        self._calls.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return "default summary"


class TestSummaryProviderWrapper:
    def test_returns_result_on_success(self):
        provider = FakeProvider(["the summary"])
        wrapper = SummaryProviderWrapper(provider)
        assert wrapper.generate("some prompt") == "the summary"

    def test_retries_on_503_in_message(self, monkeypatch):
        monkeypatch.setattr("retry.time.sleep", lambda s: None)
        call_count = [0]

        def generate(prompt):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("503 service unavailable")
            return "success"

        provider = FakeProvider()
        provider.generate = generate
        wrapper = SummaryProviderWrapper(provider)
        result = wrapper.generate("prompt")
        assert result == "success"
        assert call_count[0] == 3

    def test_retries_on_http_429(self, monkeypatch):
        monkeypatch.setattr("retry.time.sleep", lambda s: None)
        call_count = [0]

        def generate(prompt):
            call_count[0] += 1
            if call_count[0] < 2:
                resp = MagicMock()
                resp.status_code = 429
                raise requests.HTTPError("429", response=resp)
            return "ok"

        provider = FakeProvider()
        provider.generate = generate
        wrapper = SummaryProviderWrapper(provider)
        result = wrapper.generate("prompt")
        assert result == "ok"

    def test_does_not_retry_on_unknown_error(self):
        call_count = [0]

        def generate(prompt):
            call_count[0] += 1
            raise ValueError("bad input, don't retry")

        provider = FakeProvider()
        provider.generate = generate
        wrapper = SummaryProviderWrapper(provider)
        with pytest.raises(ValueError):
            wrapper.generate("prompt")
        assert call_count[0] == 1

    def test_should_retry_overloaded_message(self):
        wrapper = SummaryProviderWrapper(FakeProvider())
        assert wrapper._should_retry(RuntimeError("model is overloaded")) is True

    def test_should_retry_timeout_message(self):
        wrapper = SummaryProviderWrapper(FakeProvider())
        assert wrapper._should_retry(RuntimeError("request timeout occurred")) is True

    def test_should_not_retry_generic_error(self):
        wrapper = SummaryProviderWrapper(FakeProvider())
        assert wrapper._should_retry(ValueError("bad value")) is False

    def test_should_retry_http_500(self):
        wrapper = SummaryProviderWrapper(FakeProvider())
        resp = MagicMock()
        resp.status_code = 500
        assert wrapper._should_retry(requests.HTTPError("500", response=resp)) is True

    def test_should_not_retry_http_400(self):
        wrapper = SummaryProviderWrapper(FakeProvider())
        resp = MagicMock()
        resp.status_code = 400
        assert wrapper._should_retry(requests.HTTPError("400", response=resp)) is False


class TestBuildPrompt:
    def test_returns_string_with_transcript(self):
        prompt = _build_prompt("transcript text", max_chars=500, channel_name="SomeChannel", bullet_limit=5)
        assert "transcript text" in prompt
        assert "5" in prompt

    def test_non_sam_sulek_prompt_no_exercise_mention(self):
        prompt = _build_prompt("transcript", max_chars=500, channel_name="OtherChannel", bullet_limit=5)
        assert "exercises" not in prompt.lower()

    def test_sam_sulek_prompt_includes_exercise_mention(self):
        prompt = _build_prompt("transcript", max_chars=500, channel_name="Sam Sulek", bullet_limit=5)
        assert "exercises" in prompt.lower()

    def test_bullet_limit_in_prompt(self):
        prompt = _build_prompt("transcript", max_chars=500, channel_name="Chan", bullet_limit=8)
        assert "8" in prompt


class TestChunkText:
    def test_no_chunking_when_within_limit(self):
        text = "short text"
        chunks = _chunk_text(text, max_chars=100)
        assert chunks == [text]

    def test_splits_into_correct_chunks(self):
        text = "A" * 300
        chunks = _chunk_text(text, max_chars=100)
        assert len(chunks) == 3
        assert all(len(c) == 100 for c in chunks)

    def test_last_chunk_is_remainder(self):
        text = "B" * 250
        chunks = _chunk_text(text, max_chars=100)
        assert len(chunks) == 3
        assert len(chunks[2]) == 50

    def test_zero_or_negative_max_chars_returns_full_text(self):
        text = "some text"
        assert _chunk_text(text, max_chars=0) == [text]

    def test_exact_boundary(self):
        text = "C" * 200
        chunks = _chunk_text(text, max_chars=100)
        assert len(chunks) == 2


class TestSummarizeTranscript:
    def test_short_transcript_single_call(self):
        provider = FakeProvider(["- bullet one\n- bullet two"])
        wrapper = SummaryProviderWrapper(provider)
        wrapper.provider = provider
        result = summarize_transcript(wrapper, "short transcript", max_summary_chars=500, channel_name="Chan", bullet_limit=5)
        assert len(provider._calls) == 1
        assert "bullet" in result

    def test_long_transcript_is_chunked(self):
        # chunk_size = max_input - 1000; use max_input=1050 → chunk_size=50
        # transcript of 1100 chars > 1050 → chunking path, multiple LLM calls made
        call_count = [0]

        def fake_generate(prompt):
            call_count[0] += 1
            return f"summary_{call_count[0]}"

        provider = FakeProvider()
        provider.max_input_chars = 1050
        provider.generate = fake_generate
        wrapper = SummaryProviderWrapper(provider)
        transcript = "A" * 1100
        result = summarize_transcript(wrapper, transcript, max_summary_chars=500, channel_name="Chan", bullet_limit=5)
        assert call_count[0] > 1  # chunked → multiple LLM calls
        assert result.startswith("summary_")

    def test_transcript_at_exact_limit_not_chunked(self):
        provider = FakeProvider(["summary"])
        provider.max_input_chars = 50
        wrapper = SummaryProviderWrapper(provider)
        transcript = "A" * 50
        result = summarize_transcript(wrapper, transcript, max_summary_chars=200, channel_name="Chan", bullet_limit=5)
        assert result == "summary"


class TestOpenAIProvider:
    def test_raises_if_no_api_key(self):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            OpenAIProvider(api_key="", model="gpt-4")

    def test_calls_openai_api(self, requests_mock):
        requests_mock.post(
            "https://api.openai.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "summary result"}}]},
        )
        provider = OpenAIProvider(api_key="test-key", model="gpt-4.1-mini")
        result = provider.generate("my prompt")
        assert result == "summary result"
        assert requests_mock.last_request.headers["Authorization"] == "Bearer test-key"

    def test_raises_on_http_error(self, requests_mock):
        requests_mock.post("https://api.openai.com/v1/chat/completions", status_code=401)
        provider = OpenAIProvider(api_key="bad-key", model="gpt-4.1-mini")
        with pytest.raises(Exception):
            provider.generate("prompt")
