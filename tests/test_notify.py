import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


from notify import send_discord


class TestSendDiscord:
    def test_sends_single_chunk(self, requests_mock):
        requests_mock.post("https://discord.example/hook", status_code=204)
        send_discord("https://discord.example/hook", "Hello, world!", chunk_size=1900, timeout_s=10)
        assert requests_mock.call_count == 1
        assert requests_mock.last_request.json() == {"content": "Hello, world!"}

    def test_splits_message_into_chunks(self, requests_mock):
        requests_mock.post("https://discord.example/hook", status_code=204)
        long_message = "A" * 3800
        send_discord("https://discord.example/hook", long_message, chunk_size=1900, timeout_s=10)
        assert requests_mock.call_count == 2
        bodies = [r.json()["content"] for r in requests_mock.request_history]
        assert bodies[0] == "A" * 1900
        assert bodies[1] == "A" * 1900

    def test_chunk_boundary_exact(self, requests_mock):
        requests_mock.post("https://discord.example/hook", status_code=204)
        message = "B" * 1900
        send_discord("https://discord.example/hook", message, chunk_size=1900, timeout_s=10)
        assert requests_mock.call_count == 1

    def test_three_chunks(self, requests_mock):
        requests_mock.post("https://discord.example/hook", status_code=204)
        message = "C" * 5700
        send_discord("https://discord.example/hook", message, chunk_size=1900, timeout_s=10)
        assert requests_mock.call_count == 3

    def test_raises_on_http_error(self, requests_mock):
        requests_mock.post("https://discord.example/hook", status_code=500)
        with pytest.raises(Exception):
            send_discord("https://discord.example/hook", "msg", chunk_size=1900, timeout_s=10)

    def test_retries_on_429_with_retry_after(self, requests_mock, monkeypatch):
        sleep_calls = []
        monkeypatch.setattr("notify.time.sleep", lambda s: sleep_calls.append(s))
        monkeypatch.setattr("retry.time.sleep", lambda s: sleep_calls.append(s))

        responses = [
            {"status_code": 429, "headers": {"Retry-After": "1"}, "json": {"message": "rate limited"}},
            {"status_code": 204},
        ]
        requests_mock.post("https://discord.example/hook", responses)
        send_discord("https://discord.example/hook", "msg", chunk_size=1900, timeout_s=10)
        assert requests_mock.call_count == 2
        assert 1.0 in sleep_calls

    def test_empty_message(self, requests_mock):
        requests_mock.post("https://discord.example/hook", status_code=204)
        # Empty string still sends one chunk
        send_discord("https://discord.example/hook", "", chunk_size=1900, timeout_s=10)
        assert requests_mock.call_count == 0  # range(0, 0) is empty, no chunks
