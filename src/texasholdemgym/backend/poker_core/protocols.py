from __future__ import annotations

from typing import Protocol


Card = tuple[int, int]


class HandStrengthEvaluator(Protocol):
    """Best 5-of-7 hand strength used by showdown side-pot logic."""

    def best_rank_7(self, cards7: list[Card]) -> tuple: ...
