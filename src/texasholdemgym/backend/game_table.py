"""Human-oriented table model: six seats, stakes, and per-seat bot tuning.

`PokerGame` owns Qt timers, QML sync, and the current hand; `Table` owns who is
seated, how much money they have, which archetype they play, and the blind
structure for the session.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from texasholdemgym.backend import bot_strategy


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
