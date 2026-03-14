"""サーキットブレーカーのテスト."""

import time

import pytest

from ec_hub.scrapers.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class TestCircuitBreakerClosed:
    """CLOSED 状態のテスト."""

    def test_allows_call_when_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        assert cb.is_closed is True
        assert cb.allow_request() is True

    def test_remains_closed_after_single_failure(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        assert cb.is_closed is True
        assert cb.allow_request() is True


class TestCircuitBreakerOpen:
    """OPEN 状態のテスト."""

    def test_opens_after_reaching_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.allow_request() is False

    def test_raises_error_when_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        with pytest.raises(CircuitBreakerOpenError):
            cb.ensure_closed()


class TestCircuitBreakerHalfOpen:
    """HALF_OPEN 状態のテスト."""

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True

        time.sleep(0.15)
        assert cb.is_half_open is True
        assert cb.allow_request() is True

    def test_closes_on_success_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()

        time.sleep(0.15)
        assert cb.is_half_open is True

        cb.record_success()
        assert cb.is_closed is True

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()

        time.sleep(0.15)
        assert cb.is_half_open is True

        cb.record_failure()
        assert cb.is_open is True


class TestCircuitBreakerReset:
    """リセットのテスト."""

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.is_closed is True

    def test_manual_reset(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True

        cb.reset()
        assert cb.is_closed is True
        assert cb.failure_count == 0
