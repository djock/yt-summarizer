import time
from dataclasses import dataclass
from typing import Callable, Iterable, Type


@dataclass
class RetryPolicy:
    max_attempts: int
    delays_s: Iterable[int]


class RetryError(RuntimeError):
    pass


def run_with_retry(fn: Callable[[], object], policy: RetryPolicy, should_retry: Callable[[Exception], bool]) -> object:
    attempts = 0
    last_exc: Exception | None = None
    for delay in list(policy.delays_s) + [0]:
        attempts += 1
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempts >= policy.max_attempts or not should_retry(exc):
                raise
            time.sleep(delay)
    raise RetryError("retry attempts exceeded") from last_exc
