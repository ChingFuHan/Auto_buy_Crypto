from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_base_seconds: float
    backoff_max_seconds: float

    def delay_for_attempt(self, attempt: int) -> float:
        delay = self.backoff_base_seconds * (2 ** max(attempt - 1, 0))
        return min(delay, self.backoff_max_seconds)
