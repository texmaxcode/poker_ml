"""Chips committed this hand: per-street amounts, running pot, and raise ladder.

`PokerGame` owns timers and QML; this object owns only numeric pot/street state so it is easy
to reason about and unit test.
"""

from __future__ import annotations


class HandPotState:
    """Street contributions + total hand contributions + current facing amount (`to_call`)."""

    __slots__ = (
        "street_put_in",
        "contrib_total",
        "to_call",
        "last_raiser",
        "last_raise_increment",
        "preflop_blind_level",
    )

    def __init__(self) -> None:
        self.street_put_in: list[int] = [0] * 6
        self.contrib_total: list[int] = [0] * 6
        self.to_call: int = 0
        self.last_raiser: int = -1
        self.last_raise_increment: int = 0
        self.preflop_blind_level: int = 0

    def clear_for_new_hand(self) -> None:
        """Zero everything when a new hand is dealt (before blinds)."""
        self.street_put_in[:] = [0] * 6
        self.contrib_total[:] = [0] * 6
        self.to_call = 0
        self.last_raiser = -1
        self.last_raise_increment = 0
        self.preflop_blind_level = 0

    def reset_street(self, street_index: int, big_blind: int) -> None:
        """Start a new betting round: clear street totals; keep `contrib_total` (pot).

        Preflop (`street_index == 0`) does not reset `last_raise_increment` here — blinds setup
        assigns it (matches legacy `PokerGame._reset_street` behavior).
        """
        self.street_put_in[:] = [0] * 6
        self.to_call = 0
        self.last_raiser = -1
        if street_index >= 1:
            self.last_raise_increment = int(big_blind)

    def max_street_contrib(self) -> int:
        return int(max(self.street_put_in) if self.street_put_in else 0)

    def set_after_blinds(self, sb_seat: int, bb_seat: int, big_blind: int) -> None:
        """After SB/BB are posted: facing bet and BB preflop anchor."""
        self.to_call = max(self.street_put_in)
        sb_amt = int(self.street_put_in[sb_seat])
        bb_amt = int(self.street_put_in[bb_seat])
        self.preflop_blind_level = int(max(sb_amt, bb_amt))
        self.last_raise_increment = int(big_blind)
