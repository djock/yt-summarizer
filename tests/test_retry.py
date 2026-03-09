import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from retry import RetryPolicy, RetryError, run_with_retry


class TestRunWithRetry:
    def test_succeeds_on_first_attempt(self):
        calls = []

        def fn():
            calls.append(1)
            return "ok"

        result = run_with_retry(fn, RetryPolicy(max_attempts=3, delays_s=[1, 2]), lambda e: True)
        assert result == "ok"
        assert len(calls) == 1

    def test_retries_and_eventually_succeeds(self):
        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("not yet")
            return "done"

        result = run_with_retry(fn, RetryPolicy(max_attempts=3, delays_s=[0, 0]), lambda e: True)
        assert result == "done"
        assert len(calls) == 3

    def test_raises_after_max_attempts(self):
        def fn():
            raise ValueError("always fails")

        with pytest.raises(ValueError, match="always fails"):
            run_with_retry(fn, RetryPolicy(max_attempts=3, delays_s=[0, 0]), lambda e: True)

    def test_does_not_retry_when_should_retry_returns_false(self):
        calls = []

        def fn():
            calls.append(1)
            raise TypeError("don't retry this")

        with pytest.raises(TypeError, match="don't retry this"):
            run_with_retry(fn, RetryPolicy(max_attempts=5, delays_s=[0, 0, 0, 0]), lambda e: False)

        assert len(calls) == 1

    def test_retries_only_matching_exception_types(self):
        calls = []

        def fn():
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("retry me")
            raise TypeError("don't retry this")

        def should_retry(exc):
            return isinstance(exc, ValueError)

        with pytest.raises(TypeError):
            run_with_retry(fn, RetryPolicy(max_attempts=5, delays_s=[0, 0, 0, 0]), should_retry)

        assert len(calls) == 2

    def test_no_sleep_on_last_attempt(self, monkeypatch):
        sleep_calls = []
        monkeypatch.setattr("retry.time.sleep", lambda s: sleep_calls.append(s))

        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            run_with_retry(fn, RetryPolicy(max_attempts=2, delays_s=[5]), lambda e: True)

        # Should sleep once between attempt 1 and 2, but not after the last failure
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == 5

    def test_sleep_delays_are_used_in_order(self, monkeypatch):
        sleep_calls = []
        monkeypatch.setattr("retry.time.sleep", lambda s: sleep_calls.append(s))

        def fn():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            run_with_retry(fn, RetryPolicy(max_attempts=4, delays_s=[1, 2, 3]), lambda e: True)

        assert sleep_calls == [1, 2, 3]

    def test_single_attempt_no_retry(self):
        def fn():
            raise RuntimeError("immediate failure")

        with pytest.raises(RuntimeError):
            run_with_retry(fn, RetryPolicy(max_attempts=1, delays_s=[]), lambda e: True)

    def test_returns_value_from_successful_fn(self):
        def fn():
            return {"key": "value"}

        result = run_with_retry(fn, RetryPolicy(max_attempts=1, delays_s=[]), lambda e: True)
        assert result == {"key": "value"}
