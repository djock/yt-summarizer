import logging
import time
import requests

from retry import RetryPolicy, run_with_retry

logger = logging.getLogger(__name__)

_DEFAULT_POLICY = RetryPolicy(max_attempts=5, delays_s=[2, 5, 10, 20])


def send_discord(webhook_url: str, content: str, chunk_size: int, timeout_s: int, policy: RetryPolicy | None = None) -> None:
    chunks = [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]

    def should_retry(exc: Exception) -> bool:
        if isinstance(exc, requests.HTTPError):
            status = exc.response.status_code if exc.response is not None else 0
            return status in (429, 500, 502, 503, 504)
        if isinstance(exc, requests.RequestException):
            return True
        return False

    policy = policy or _DEFAULT_POLICY

    for chunk in chunks:
        def send_chunk() -> None:
            resp = requests.post(webhook_url, json={"content": chunk}, timeout=timeout_s)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    time.sleep(float(retry_after))
                    raise requests.HTTPError("rate limited", response=resp)
            resp.raise_for_status()

        run_with_retry(send_chunk, policy, should_retry)
