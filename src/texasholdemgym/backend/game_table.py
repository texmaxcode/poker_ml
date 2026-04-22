"""Human-oriented table model: six seats, stakes, and per-seat bot tuning.

`PokerGame` owns Qt timers, QML sync, and the current hand; `Table` owns who is
seated, how much money they have, which archetype they play, and the blind
structure for the session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.poker_core.blind_positions import advance_button_seat, blind_seats_for_hand
from texasholdemgym.backend.poker_core.betting_navigation import next_live_stack_seat, next_seat_clockwise
from texasholdemgym.backend.poker_core.table_roster import (
    bootstrap_playable_table,
    count_eligible_for_deal,
    dealing_mask_for_new_hand,
    seat_eligible_for_new_hand,
)
from texasholdemgym.backend.table_hud_text import TableMessages


@dataclass
class StrategyTuning:
    """Numeric knobs the UI edits and the RNG uses (camelCase matches legacy QML / upstream)."""

    preflopExponent: float = 1.0
    postflopExponent: float = 1.0
    facingRaiseBonus: float = 0.0
    facingRaiseTightMul: float = 1.0
    openBetBonus: float = 0.0
    openBetTightMul: float = 1.0
    bbCheckraiseBonus: float = 0.0
    bbCheckraiseTightMul: float = 1.0
    buyInBb: int = 100


@dataclass
class SeatStrategy:
    """Built-in bot personality for one seat: archetype preset + per-seat tuning."""

    archetype_index: int = 6
    tuning: StrategyTuning = field(default_factory=StrategyTuning)

    def reload_params_from_archetype(self) -> None:
        idx = int(self.archetype_index) % bot_strategy.STRATEGY_COUNT
        bp = bot_strategy.params_for_index(idx)
        bot_strategy.apply_bot_params_to_strategy_fields(self.tuning, bp)


@dataclass
class Player:
    """One seat: wallet split (on-table stack vs off-table bankroll), in-game flags, bot strategy."""

    seat: int
    participating: bool = True
    stack_on_table: int = 200
    bankroll_off_table: int = 0
    strategy: SeatStrategy = field(default_factory=SeatStrategy)

    def commit_to_pot(self, amount: int) -> int:
        """Move up to ``amount`` chips from the on-table stack toward the pot; returns chips moved."""
        amt = max(0, min(int(amount), int(self.stack_on_table)))
        self.stack_on_table -= int(amt)
        return int(amt)

    def receive_from_pot(self, amount: int) -> None:
        """Add chips won from the pot (or refund) to the on-table stack."""
        self.stack_on_table += int(amount)

    def reconcile_stack_with_table_cap(self, cap: int) -> None:
        """If on-table stack exceeds ``cap``, move overflow off-table; repair negative stacks."""
        c = int(max(0, int(cap)))
        if int(self.stack_on_table) > c:
            overflow = int(self.stack_on_table - c)
            self.stack_on_table = c
            self.bankroll_off_table += overflow
        if int(self.stack_on_table) < 0:
            deficit = -int(self.stack_on_table)
            self.stack_on_table = 0
            self.bankroll_off_table = max(0, int(self.bankroll_off_table) - deficit)

    def set_stack_with_total_preservation(self, want_on_table: int, *, cap: int) -> None:
        """Set on-table stack toward ``want_on_table``, clipped by ``cap`` when ``cap`` > 0; wealth preserved."""
        want = max(0, int(want_on_table))
        c = int(cap)
        if c > 0:
            want = min(want, c)
        total = int(self.stack_on_table + self.bankroll_off_table)
        want = min(want, total)
        self.stack_on_table = want
        self.bankroll_off_table = max(0, total - want)

    def transfer_from_bankroll_to_table(self, amount: int) -> int:
        """Move up to ``amount`` chips from bankroll to the on-table stack; returns chips moved."""
        amt = max(0, min(int(amount), int(self.bankroll_off_table)))
        self.bankroll_off_table -= int(amt)
        self.stack_on_table += int(amt)
        return int(amt)


def _six_players() -> list[Player]:
    return [Player(seat=i) for i in range(6)]


@dataclass
class Table:
    """Session table: blind structure, buy-in defaults, and six `Player` records."""

    players: list[Player] = field(default_factory=_six_players)
    small_blind: int = 1
    big_blind: int = 2
    street_bet: int = 4
    max_on_table_bb: int = 100
    start_stack: int = 200

    @classmethod
    def default_six_max(cls) -> Table:
        t = cls()
        for p in t.players:
            p.strategy.reload_params_from_archetype()
        return t

    def stacks_list(self) -> list[int]:
        return [int(p.stack_on_table) for p in self.players]

    def bankrolls_list(self) -> list[int]:
        return [int(p.bankroll_off_table) for p in self.players]

    def participating_list(self) -> list[bool]:
        return [bool(p.participating) for p in self.players]

    def total_wealth_list(self) -> list[int]:
        """Off-table + on-table chips per seat (session stats / snapshots)."""
        return [int(p.bankroll_off_table + p.stack_on_table) for p in self.players]

    def session_baseline_snapshot(self) -> tuple[list[int], list[int]]:
        """On-table stacks and total wealth per seat (session stats baselines)."""
        return self.stacks_list(), self.total_wealth_list()

    def buy_in_cap_chips(self) -> int:
        """Maximum on-table chips from the configured BB cap (0 if uncapped)."""
        return int(max(0, int(self.max_on_table_bb) * int(self.big_blind)))

    def max_buy_in_chips(self) -> int:
        """Default buy-in UI cap (table cap, or start stack when cap is zero)."""
        cap = self.buy_in_cap_chips()
        return int(cap) if cap > 0 else int(self.start_stack)

    def effective_buy_in_chips(self, seat: int, *, hero_seat: int, interactive_hero: bool) -> int:
        """Target on-table stack for a seat (Setup buy-in × BB, capped)."""
        s = int(seat)
        if not (0 <= s < 6):
            return int(self.start_stack)
        cap = self.buy_in_cap_chips()
        p = self.players[s]
        if s == int(hero_seat) and interactive_hero:
            return int(min(max(0, int(p.stack_on_table)), cap)) if cap > 0 else int(p.stack_on_table)
        bb = max(1, int(self.big_blind))
        mult = max(1, int(p.strategy.tuning.buyInBb))
        return int(max(1, min(mult * bb, cap))) if cap > 0 else max(1, mult * bb)

    def count_eligible_for_deal_roster(self, human_sitting_out: bool) -> int:
        return int(count_eligible_for_deal(self.stacks_list(), human_sitting_out, self.participating_list()))

    def dealing_mask(self, human_sitting_out: bool) -> list[bool]:
        return list(dealing_mask_for_new_hand(self.stacks_list(), human_sitting_out, self.participating_list()))

    def seat_eligible_for_deal(self, seat: int, human_sitting_out: bool) -> bool:
        return bool(seat_eligible_for_new_hand(int(seat), self.stacks_list(), human_sitting_out, self.participating_list()))

    def bootstrap_if_insufficient_players(self, human_sitting_out: bool) -> tuple[bool, bool]:
        """If fewer than two can deal, seed defaults. Returns ``(new_human_sitting_out, changed)``."""
        sp, bi, hso, changed = bootstrap_playable_table(
            self.participating_list(),
            self.stacks_list(),
            human_sitting_out,
            self.start_stack,
        )
        self.import_participating(sp)
        self.import_stacks(bi)
        return bool(hso), bool(changed)

    @staticmethod
    def seat_position_label(
        seat: int,
        *,
        button_seat: int,
        sb_seat: int,
        bb_seat: int,
        participating: Sequence[bool],
    ) -> str:
        """BTN / SB / BB / UTG / HJ / CO for a seat (6-max, matches former QML ``GameScreen.seatRole``)."""
        n = 6
        s = int(seat)
        btn = int(button_seat)
        sb = int(sb_seat)
        bb = int(bb_seat)
        part = list(participating)[:6] + [False] * max(0, 6 - len(participating))

        def in_dealing_pool(idx: int) -> bool:
            if idx < 0 or idx >= n:
                return False
            if idx < len(part) and part[idx] is False:
                return False
            return True

        if bb < 0:
            return "—"
        if s == btn:
            return "BTN"
        if sb >= 0 and s == sb:
            return "SB"
        if bb >= 0 and s == bb:
            return "BB"
        order: list[int] = []
        for k in range(1, n):
            si = (bb + k) % n
            if si != btn and si != sb and si != bb and in_dealing_pool(si):
                order.append(si)
        m = len(order)
        if m > 0 and s == order[0]:
            return "UTG"
        if m >= 2 and s == order[m - 1]:
            return "CO"
        if m >= 3 and s == order[m - 2]:
            return "HJ"
        return "—"

    def next_seat_clockwise_from(self, start: int, in_hand: list[bool], *, need_chips: bool) -> int:
        """Next clockwise seat from ``start`` among participating players still in the hand."""
        return int(
            next_seat_clockwise(
                int(start),
                self.participating_list(),
                in_hand,
                self.stacks_list(),
                need_chips=need_chips,
            )
        )

    def next_live_stack_seat_from(self, start: int) -> int:
        """Next clockwise participating seat after ``start`` with chips (button / blind walk)."""
        return int(next_live_stack_seat(int(start), self.participating_list(), self.stacks_list()))

    # --- HUD copy (QML / upstream) — see ``TableMessages`` for implementation. ---
    HERO_SEAT: int = TableMessages.HERO_SEAT
    DEFAULT_BOT_NAMES: tuple[str, str, str, str, str] = TableMessages.DEFAULT_BOT_NAMES

    @staticmethod
    def format_showdown_line(
        winner_seats: list[int],
        hand_label: str,
        *,
        bot_names: tuple[str, ...] | None = None,
    ) -> str:
        return TableMessages.format_showdown_line(winner_seats, hand_label, bot_names=bot_names)

    @staticmethod
    def format_hud_status_line(
        street_index: int,
        pot_chips: int,
        acting_seat: int,
        *,
        showdown: bool,
        showdown_status_text: str,
        bb_preflop_waiting: bool,
        interactive_human: bool,
        hero_seat: int = 0,
        bot_names: tuple[str, ...] | None = None,
    ) -> str:
        return TableMessages.hud_status_line(
            street_index,
            pot_chips,
            acting_seat,
            showdown=showdown,
            showdown_status_text=showdown_status_text,
            bb_preflop_waiting=bb_preflop_waiting,
            interactive_human=interactive_human,
            hero_seat=hero_seat,
            bot_names=bot_names,
        )

    @staticmethod
    def format_hero_hole_hud_text(
        h0: tuple[int, int],
        h1: tuple[int, int],
        *,
        hero_in_hand: bool,
        human_sitting_out: bool,
    ) -> str:
        return TableMessages.hero_hole_hud_text(
            h0, h1, hero_in_hand=hero_in_hand, human_sitting_out=human_sitting_out
        )

    def import_stacks(self, stacks: list[int]) -> None:
        for i, v in enumerate(stacks[:6]):
            self.players[i].stack_on_table = int(v)

    def import_bankrolls(self, bankrolls: list[int]) -> None:
        for i, v in enumerate(bankrolls[:6]):
            self.players[i].bankroll_off_table = int(v)

    def import_participating(self, participating: list[bool]) -> None:
        for i, v in enumerate(participating[:6]):
            self.players[i].participating = bool(v)

    def reset_like_new_install(self) -> None:
        """Match `factoryResetToDefaultsAndClearHistory` table + roster defaults."""
        self.small_blind = 1
        self.big_blind = 2
        self.street_bet = 4
        self.max_on_table_bb = 100
        self.start_stack = 200
        for p in self.players:
            p.participating = True
            p.stack_on_table = 200
            p.bankroll_off_table = 0
            p.strategy.archetype_index = 6
            p.strategy.reload_params_from_archetype()


@dataclass
class DealPositions:
    """Who is dealt this hand and where the button and blinds sit (6-max roster on a ``Table``)."""

    dealing: list[bool]
    n_live: int
    button_seat: int
    sb_seat: int
    bb_seat: int

    @classmethod
    def from_table(cls, table: Table, prev_button: int, human_sitting_out: bool) -> DealPositions:
        dealing = list(table.dealing_mask(human_sitting_out))
        n_live = int(sum(dealing))
        btn = advance_button_seat(
            int(prev_button), dealing, table.participating_list(), table.stacks_list()
        )
        sb, bb = blind_seats_for_hand(int(btn), n_live, table.participating_list(), table.stacks_list())
        return cls(
            dealing=dealing,
            n_live=n_live,
            button_seat=int(btn),
            sb_seat=int(sb),
            bb_seat=int(bb),
        )
