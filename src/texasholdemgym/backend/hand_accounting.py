"""Per-hand money and history: one façade over pot math + append-only action log.

`HandPotState` / `HandActionLog` are implementation details; callers use `HandAccounting` only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from texasholdemgym.backend.poker_core.hand_action_log import HandActionLog
from texasholdemgym.backend.poker_core.hand_pot import HandPotState


class HandAccounting:
    """Street/pot chip math and serialized table actions for the current deal."""

    __slots__ = ("_pot", "_log")

    def __init__(self) -> None:
        self._pot = HandPotState()
        self._log = HandActionLog()

    # --- lifecycle ---
    def clear_for_new_hand(self) -> None:
        self._pot.clear_for_new_hand()

    def begin_action_log(self, started_ms: int) -> None:
        self._log.begin_hand(int(started_ms))

    def reset_street(self, street_index: int, big_blind: int) -> None:
        self._pot.reset_street(int(street_index), int(big_blind))

    def set_after_blinds(self, sb_seat: int, bb_seat: int, big_blind: int) -> None:
        self._pot.set_after_blinds(int(sb_seat), int(bb_seat), int(big_blind))

    # --- reads (pot) ---
    def max_street_contrib(self) -> int:
        return self._pot.max_street_contrib()

    def total_contrib_chips(self) -> int:
        return int(sum(self._pot.contrib_total))

    def street_put_in_list(self) -> list[int]:
        return [int(x) for x in self._pot.street_put_in]

    def contrib_totals_list(self) -> list[int]:
        return [int(x) for x in self._pot.contrib_total]

    def street_put_in_at(self, seat: int) -> int:
        return int(self._pot.street_put_in[int(seat)])

    def contrib_at(self, seat: int) -> int:
        return int(self._pot.contrib_total[int(seat)])

    def chips_needed_to_call(self, seat: int) -> int:
        s = int(seat)
        return max(0, int(self._pot.to_call) - int(self._pot.street_put_in[s]))

    @property
    def to_call(self) -> int:
        return int(self._pot.to_call)

    @to_call.setter
    def to_call(self, value: int) -> None:
        self._pot.to_call = int(value)

    @property
    def last_raise_increment(self) -> int:
        return int(self._pot.last_raise_increment)

    @last_raise_increment.setter
    def last_raise_increment(self, value: int) -> None:
        self._pot.last_raise_increment = int(value)

    @property
    def last_raiser(self) -> int:
        return int(self._pot.last_raiser)

    @last_raiser.setter
    def last_raiser(self, value: int) -> None:
        self._pot.last_raiser = int(value)

    @property
    def preflop_blind_level(self) -> int:
        return int(self._pot.preflop_blind_level)

    # --- writes (pot) ---
    def add_street_and_contrib(self, seat: int, amount: int) -> None:
        s, a = int(seat), int(amount)
        self._pot.street_put_in[s] += a
        self._pot.contrib_total[s] += a

    def bump_to_call_with_seat_street(self, seat: int) -> None:
        s = int(seat)
        self._pot.to_call = max(int(self._pot.to_call), int(self._pot.street_put_in[s]))

    # --- test / harness (explicit mutators instead of reaching into `_pot`) ---
    def set_contrib_totals(self, amounts: Sequence[int]) -> None:
        for i, v in enumerate(amounts):
            if i >= 6:
                break
            self._pot.contrib_total[i] = int(v)

    def set_street_put_in(self, seat: int, value: int) -> None:
        self._pot.street_put_in[int(seat)] = int(value)

    # --- action log (history payload) ---
    def append_action(
        self, street: int, seat: int, kind_label: str, chips: int, *, is_blind: bool = False
    ) -> None:
        self._log.append(int(street), int(seat), str(kind_label), int(chips), is_blind=is_blind)

    def history_started_ms(self) -> int:
        return int(self._log.started_ms)

    def snapshot_actions(self) -> list[dict[str, Any]]:
        return self._log.snapshot_actions()
