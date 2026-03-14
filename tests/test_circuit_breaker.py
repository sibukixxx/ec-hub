"""サーキットブレーカーのテスト."""

import time

import pytest

from ec_hub.scrapers.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, CircuitState


class TestCircuitBreakerClosed:
    """CLOSED 状態のテスト."""

    def test_allows_call_when_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        assert cb.state == CircuitState.CLOSED
        cb.allow_request()  # should not raise

    def test_remains_closed_after_single_failure(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.allow_request()  # should not raise


class TestCircuitBreakerOpen:
    """OPEN 状態のテスト."""

    def test_opens_after_reaching_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_raises_error_when_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpen):
            cb.allow_request()


class TestCircuitBreakerHalfOpen:
    """HALF_OPEN 状態のテスト."""

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.allow_request()  # should not raise in HALF_OPEN

    def test_closes_on_success_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerReset:
    """リセットのテスト."""

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        cb.allow_request()  # should not raise

    def test_success_after_failures_prevents_open(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # After reset, need full threshold again to open
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
