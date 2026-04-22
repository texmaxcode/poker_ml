"""Street-level chip flow: seat contributions, blind posting, and betting-round completion.

`PokerGame` keeps Qt (timers, QML sync); this type owns the pure table + live + accounting
interactions for one NLHE street.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from texasholdemgym.backend.game_table import Player, Table
from texasholdemgym.backend.hand_accounting import HandAccounting
from texasholdemgym.backend.live_hand import LiveHandState
from texasholdemgym.backend.poker_core.betting_navigation import (
    all_called_or_folded,
    betting_round_fully_resolved,
    remaining_players,
)
from texasholdemgym.backend.poker_core.pot import compute_pot_slices, distribute_showdown_side_pots
from texasholdemgym.backend.poker_core.protocols import HandStrengthEvaluator


class StreetBetController:
    """Applies contributions from `Player` stacks into `HandAccounting` and HUD street lines."""

    __slots__ = ("_table", "_live", "_accounting", "_after_chips_sync")

    def __init__(
        self,
        table: Table,
        live: LiveHandState,
        accounting: HandAccounting,
        *,
        after_chips_sync: Callable[[], None],
    ) -> None:
        self._table = table
        self._live = live
        self._accounting = accounting
        self._after_chips_sync = after_chips_sync

    def player_at(self, seat: int) -> Player:
        return self._table.players[int(seat) % 6]

    def reset_street(self) -> None:
        self._accounting.reset_street(self._live.street, self._table.big_blind)
        self._live.reset_street_labels()

    def betting_round_complete(self) -> bool:
        return bool(
            betting_round_fully_resolved(
                self._table.participating_list(),
                self._live.in_hand,
                self._accounting.street_put_in_list(),
                self._table.stacks_list(),
                int(self._accounting.to_call),
                int(self._accounting.last_raiser),
                self._live.street_acted,
            )
        )

    def all_street_bets_matched(self) -> bool:
        """No active seat (with chips) is behind the current ``to_call`` on this street."""
        return all_called_or_folded(
            self._table.participating_list(),
            self._live.in_hand,
            self._accounting.street_put_in_list(),
            self._table.stacks_list(),
            int(self._accounting.to_call),
        )

    def seats_still_in_hand(self) -> list[int]:
        """Seats with ``participating and in_hand`` in button order (see :func:`remaining_players`)."""
        return remaining_players(self._table.participating_list(), self._live.in_hand)

    def pot_slices_for_hud(self) -> list[dict[str, Any]]:
        """Contiguous contribution tiers (main + side-pots) for the HUD / QML `potSlices`."""
        return compute_pot_slices(self._accounting.contrib_totals_list(), self._live.in_hand)

    def distribute_showdown_payouts(self, evaluator: HandStrengthEvaluator) -> list[int]:
        return distribute_showdown_side_pots(
            self._accounting.contrib_totals_list(),
            self._live.in_hand,
            self.seats_still_in_hand(),
            self._live.board,
            self._live.holes,
            evaluator,
        )

    def log_street_action(self, seat: int, kind_label: str, chips: int, *, is_blind: bool = False) -> None:
        self._accounting.append_action(
            int(self._live.street), int(seat), str(kind_label), int(chips), is_blind=is_blind
        )

    def mark_street_acted(self, seat: int) -> None:
        s = int(seat)
        if 0 <= s < 6:
            self._live.street_acted[s] = True

    def apply_contribution(self, seat: int, amount: int, label: str = "") -> int:
        """Move chips from seat toward the pot; return amount moved. Optional HUD line + action log."""
        seat_i = int(seat)
        if not self._live.in_hand[seat_i]:
            return 0
        amt = int(self.player_at(seat_i).commit_to_pot(int(amount)))
        self._accounting.add_street_and_contrib(seat_i, amt)
        if label:
            blind = label in ("SB", "BB")
            if amt > 0 and label in ("Call", "Raise", "SB", "BB"):
                self._live.street_action_text[seat_i] = f"{label} ${int(amt)}"
            else:
                self._live.street_action_text[seat_i] = label
            self.log_street_action(seat_i, label, int(amt), is_blind=blind)
            if not blind:
                self.mark_street_acted(seat_i)
        self._after_chips_sync()
        return amt

    def post_blinds(self) -> None:
        self.apply_contribution(self._live.sb_seat, self._table.small_blind, label="SB")
        self.apply_contribution(self._live.bb_seat, self._table.big_blind, label="BB")
        self._accounting.set_after_blinds(self._live.sb_seat, self._live.bb_seat, self._table.big_blind)
        self._live.bb_preflop_option_open = True
