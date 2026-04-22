"""Seat bot policy: decisions from table stakes, pot state, and strategy tuning (no Qt)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.game_table import Table, StrategyTuning
from texasholdemgym.backend.hand_accounting import HandAccounting
from texasholdemgym.backend.live_hand import LiveHandState
from texasholdemgym.backend.poker_core.hand_evaluation import hand_strength_01_hole_board
from texasholdemgym.backend.poker_core.raise_rules import min_raise_increment_chips
from texasholdemgym.backend.range_manager import RangeManager


class BotDecisionKind(Enum):
    FOLD = auto()
    CHECK = auto()
    CALL = auto()
    RAISE_TO_LEVEL = auto()
    BB_PREFLOP_RAISE = auto()


@dataclass(frozen=True)
class BotDecision:
    """Engine output applied by ``PokerGame`` (fold / check / call / raise)."""

    kind: BotDecisionKind
    raise_to_street_level: int = 0
    bb_raise_chips: int = 0


@dataclass(frozen=True)
class SeatBotObservation:
    """Read-only snapshot: ``Table`` stakes + ``HandAccounting`` + hand signals for one seat."""

    context: str  # "street" | "bb_preflop_option"
    seat: int
    street: int
    stack: int
    archetype_index: int
    tuning: StrategyTuning
    need_to_call: int
    to_call: int
    street_put_in_at_seat: int
    min_raise_increment: int
    preflop_blind_level: int
    big_blind: int
    street_bet: int
    max_street_contrib: int
    signal_continue: float
    weight_raise_gate: float
    weight_bet_layer: float
    preflop_play_metric: float


def build_seat_bot_observation(
    context: str,
    seat: int,
    table: Table,
    live: LiveHandState,
    accounting: HandAccounting,
    ranges: RangeManager,
) -> SeatBotObservation:
    """Fold hole cards + table/accounting into the snapshot ``TableRulesBot`` consumes."""
    s = int(seat)
    h0, h1 = live.holes[s]
    cw = ranges.chart_weights_for_hole(s, h0, h1)
    ppm = ranges.play_metric_for_hole(s, h0, h1)
    if live.street == 0:
        sig = float(ppm)
        rw = float(cw[1])
    else:
        sig = float(hand_strength_01_hole_board(h0, h1, live.board))
        rw = float(sig)
    p = table.players[s]
    return SeatBotObservation(
        context=str(context),
        seat=s,
        street=int(live.street),
        stack=int(p.stack_on_table),
        archetype_index=int(p.strategy.archetype_index),
        tuning=p.strategy.tuning,
        need_to_call=int(accounting.chips_needed_to_call(s)),
        to_call=int(accounting.to_call),
        street_put_in_at_seat=int(accounting.street_put_in_at(s)),
        min_raise_increment=int(
            min_raise_increment_chips(table.big_blind, accounting.last_raise_increment)
        ),
        preflop_blind_level=int(accounting.preflop_blind_level),
        big_blind=int(table.big_blind),
        street_bet=int(table.street_bet),
        max_street_contrib=int(accounting.max_street_contrib()),
        signal_continue=float(sig),
        weight_raise_gate=float(rw),
        weight_bet_layer=float(cw[2]),
        preflop_play_metric=float(ppm),
    )


class TableRulesBot:
    """NLHE bot that uses ``Table`` blind/bet sizes and ``bot_strategy`` RNG policy."""

    __slots__ = ("_strategy_count",)

    def __init__(self, *, strategy_count: int | None = None) -> None:
        self._strategy_count = int(strategy_count) if strategy_count is not None else int(
            bot_strategy.STRATEGY_COUNT
        )

    def decide_street_action(self, obs: SeatBotObservation, rng: random.Random) -> BotDecision:
        if obs.context != "street":
            raise ValueError("decide_street_action expects context 'street'")
        idx = int(obs.archetype_index) % self._strategy_count
        tuning = obs.tuning
        stack = int(obs.stack)
        need = int(obs.need_to_call)
        inc = int(obs.min_raise_increment)

        if idx == 0:
            return BotDecision(BotDecisionKind.CALL) if need > 0 else BotDecision(BotDecisionKind.CHECK)

        sig = float(obs.signal_continue)
        rw = float(obs.weight_raise_gate)

        if need > 0:
            if int(obs.street) == 0:
                if not bot_strategy.bot_preflop_continue_p(tuning, sig, rng):
                    return BotDecision(BotDecisionKind.FOLD)
            else:
                if not bot_strategy.bot_postflop_continue_p(tuning, sig, rng):
                    return BotDecision(BotDecisionKind.FOLD)
            try_raise = bot_strategy.bot_wants_raise_after_continue_p(tuning, sig, rng)
            new_level = int(obs.to_call + inc)
            chips_needed = new_level - int(obs.street_put_in_at_seat)
            if try_raise and chips_needed > 0 and chips_needed <= stack:
                gate = True
                if int(obs.street) == 0:
                    gate = bot_strategy.rng_passes_layer_gate(rw, sig, rng)
                if gate:
                    return BotDecision(BotDecisionKind.RAISE_TO_LEVEL, raise_to_street_level=new_level)
            return BotDecision(BotDecisionKind.CALL)

        if int(obs.street) == 0:
            if not bot_strategy.bot_preflop_continue_p(tuning, sig, rng):
                return BotDecision(BotDecisionKind.CHECK)
            try_raise = bot_strategy.bot_wants_raise_after_continue_p(tuning, sig, rng)
            if try_raise and inc > 0 and stack >= inc:
                if bot_strategy.rng_passes_layer_gate(rw, sig, rng):
                    return BotDecision(
                        BotDecisionKind.RAISE_TO_LEVEL,
                        raise_to_street_level=int(obs.to_call + obs.big_blind),
                    )
            return BotDecision(BotDecisionKind.CHECK)

        if not bot_strategy.bot_wants_open_bet_postflop_p(tuning, sig, rng):
            return BotDecision(BotDecisionKind.CHECK)
        bet_w = float(obs.weight_bet_layer)
        play_triple = float(obs.preflop_play_metric)
        if not bot_strategy.rng_passes_layer_gate(bet_w, play_triple, rng):
            return BotDecision(BotDecisionKind.CHECK)
        open_amt = min(int(obs.street_bet), stack)
        if open_amt <= 0:
            return BotDecision(BotDecisionKind.CHECK)
        target = int(obs.street_put_in_at_seat) + open_amt
        return BotDecision(BotDecisionKind.RAISE_TO_LEVEL, raise_to_street_level=target)

    def decide_bb_preflop_option(self, obs: SeatBotObservation, rng: random.Random) -> BotDecision:
        if obs.context != "bb_preflop_option":
            raise ValueError("decide_bb_preflop_option expects context 'bb_preflop_option'")
        idx = int(obs.archetype_index) % self._strategy_count
        tuning = obs.tuning
        inc = int(obs.min_raise_increment)
        pw = float(obs.signal_continue)
        rw = float(obs.weight_raise_gate)

        if idx == 0:
            return BotDecision(BotDecisionKind.CHECK)

        raise_ok = bot_strategy.bot_bb_check_or_raise_p(tuning, pw, rng)
        if (
            raise_ok
            and inc > 0
            and int(obs.stack) >= inc
            and int(obs.max_street_contrib) == int(obs.preflop_blind_level)
            and bot_strategy.rng_passes_layer_gate(rw, pw, rng)
        ):
            return BotDecision(BotDecisionKind.BB_PREFLOP_RAISE, bb_raise_chips=inc)
        return BotDecision(BotDecisionKind.CHECK)
