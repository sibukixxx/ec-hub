"""サーキットブレーカーパターン."""

from __future__ import annotations

import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """サーキットブレーカーが OPEN 状態で呼び出された場合の例外."""


class CircuitBreaker:
    """連続失敗を検知してリクエストを遮断するサーキットブレーカー.

    Args:
        failure_threshold: OPEN に遷移する連続失敗回数
        recovery_timeout: OPEN から HALF_OPEN に遷移するまでの秒数
    """

    def __init__(self, *, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioned to HALF_OPEN after %.1fs", elapsed)
        return self._state

    def allow_request(self) -> None:
        """リクエスト可否を判定する. OPEN なら CircuitBreakerOpen を送出."""
        current = self.state
        if current == CircuitState.OPEN:
            raise CircuitBreakerOpen(
                f"Circuit breaker is OPEN (failures={self._failure_count}, retry after {self._recovery_timeout}s)"
            )

    def record_failure(self) -> None:
        """失敗を記録する."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker OPENED after %d consecutive failures",
                self._failure_count,
            )
        elif self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker re-OPENED from HALF_OPEN")

    def record_success(self) -> None:
        """成功を記録する."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker CLOSED from HALF_OPEN")
        self._failure_count = 0
        self._state = CircuitState.CLOSED
