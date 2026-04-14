"""Token accounting helpers. Uses Anthropic usage fields; no offline estimation."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TokenBudget:
    limit: int
    spent: int = 0

    def charge(self, n: int) -> None:
        self.spent += n

    def remaining(self) -> int:
        return max(0, self.limit - self.spent)

    def exceeded(self) -> bool:
        return self.spent > self.limit
