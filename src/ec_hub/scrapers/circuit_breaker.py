"""サーキットブレーカーパターンの実装."""

from __future__ import annotations

import time
from enum import Enum


class CircuitBreakerOpenError(Exception):
    """サーキットブレーカーが OPEN 状態のため操作が拒否された."""


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """サーキットブレーカー.

    連続失敗が閾値に達すると OPEN に遷移し、リクエストをブロックする。
    recovery_timeout 経過後に HALF_OPEN で1件だけ試行を許可し、
    成功すれば CLOSED に戻り、失敗すれば再び OPEN になる。
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._state = _State.CLOSED
        self._opened_at: float = 0.0

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def is_closed(self) -> bool:
        self._evaluate_state()
        return self._state == _State.CLOSED

    @property
    def is_open(self) -> bool:
        self._evaluate_state()
        return self._state == _State.OPEN

    @property
    def is_half_open(self) -> bool:
        self._evaluate_state()
        return self._state == _State.HALF_OPEN

    def _evaluate_state(self) -> None:
        """OPEN 状態でタイムアウトを過ぎていれば HALF_OPEN に遷移."""
        if self._state == _State.OPEN:
            if time.monotonic() - self._opened_at >= self._recovery_timeout:
                self._state = _State.HALF_OPEN

    def allow_request(self) -> bool:
        """リクエストを許可するかどうか."""
        self._evaluate_state()
        if self._state == _State.CLOSED:
            return True
        if self._state == _State.HALF_OPEN:
            return True
        return False

    def ensure_closed(self) -> None:
        """CLOSED / HALF_OPEN でなければ例外を送出."""
        if not self.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is OPEN (failures={self._failure_count}, "
                f"threshold={self._failure_threshold})"
            )

    def record_success(self) -> None:
        """成功を記録し CLOSED に遷移."""
        self._failure_count = 0
        self._state = _State.CLOSED

    def record_failure(self) -> None:
        """失敗を記録し、閾値到達で OPEN に遷移."""
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._state = _State.OPEN
            self._opened_at = time.monotonic()

    def reset(self) -> None:
        """手動リセット."""
        self._failure_count = 0
        self._state = _State.CLOSED
        self._opened_at = 0.0
