"""Append-only table actions for one hand (persisted via `HandHistory`)."""

from __future__ import annotations

from typing import Any


class HandActionLog:
    """Keeps `started_ms`, monotonic `seq`, and JSON-serializable action rows."""

    __slots__ = ("started_ms", "_seq", "_rows")

    def __init__(self) -> None:
        self.started_ms: int = 0
        self._seq: int = 0
        self._rows: list[dict[str, Any]] = []

    def begin_hand(self, started_ms: int) -> None:
        self.started_ms = int(started_ms)
        self._seq = 0
        self._rows.clear()

    def append(self, street: int, seat: int, kind_label: str, chips: int, *, is_blind: bool = False) -> None:
        self._seq += 1
        self._rows.append(
            {
                "seq": int(self._seq),
                "street": int(street),
                "seat": int(seat),
                "kindLabel": str(kind_label),
                "isBlind": bool(is_blind),
                "chips": int(chips),
            }
        )

    def snapshot_actions(self) -> list[dict[str, Any]]:
        return list(self._rows)
