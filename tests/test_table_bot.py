"""`TableRulesBot` — decisions from table-sized observations (no Qt)."""

from __future__ import annotations

import random
from unittest import mock

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.game_table import StrategyTuning
from texasholdemgym.backend.table_bot import BotDecisionKind, SeatBotObservation, TableRulesBot


def _obs_street(*, need: int = 0, idx: int = 0) -> SeatBotObservation:
    return SeatBotObservation(
        context="street",
        seat=3,
        street=0,
        stack=200,
        archetype_index=idx,
        tuning=StrategyTuning(),
        need_to_call=need,
        to_call=2,
        street_put_in_at_seat=1,
        min_raise_increment=2,
        preflop_blind_level=3,
        big_blind=2,
        street_bet=4,
        max_street_contrib=3,
        signal_continue=0.5,
        weight_raise_gate=0.5,
        weight_bet_layer=0.5,
        preflop_play_metric=0.5,
    )


def test_table_rules_bot_archetype_zero_always_calls_when_facing_bet() -> None:
    bot = TableRulesBot()
    rng = random.Random(0)
    d = bot.decide_street_action(_obs_street(need=10, idx=0), rng)
    assert d.kind == BotDecisionKind.CALL


def test_table_rules_bot_archetype_zero_checks_when_no_bet() -> None:
    bot = TableRulesBot()
    rng = random.Random(0)
    d = bot.decide_street_action(_obs_street(need=0, idx=0), rng)
    assert d.kind == BotDecisionKind.CHECK


def test_table_rules_bot_preflop_fold_when_continue_false() -> None:
    bot = TableRulesBot()
    rng = random.Random(0)
    obs = _obs_street(need=5, idx=3)
    with mock.patch.object(bot_strategy, "bot_preflop_continue_p", return_value=False):
        d = bot.decide_street_action(obs, rng)
    assert d.kind == BotDecisionKind.FOLD


def test_table_rules_bot_bb_preflop_always_check_archetype_zero() -> None:
    bot = TableRulesBot()
    rng = random.Random(0)
    obs = SeatBotObservation(
        context="bb_preflop_option",
        seat=2,
        street=0,
        stack=100,
        archetype_index=0,
        tuning=StrategyTuning(),
        need_to_call=0,
        to_call=2,
        street_put_in_at_seat=2,
        min_raise_increment=2,
        preflop_blind_level=3,
        big_blind=2,
        street_bet=4,
        max_street_contrib=3,
        signal_continue=0.9,
        weight_raise_gate=0.9,
        weight_bet_layer=0.9,
        preflop_play_metric=0.9,
    )
    d = bot.decide_bb_preflop_option(obs, rng)
    assert d.kind == BotDecisionKind.CHECK


def test_table_rules_bot_bb_preflop_raise_when_gates_pass() -> None:
    bot = TableRulesBot()
    rng = random.Random(0)
    obs = SeatBotObservation(
        context="bb_preflop_option",
        seat=2,
        street=0,
        stack=100,
        archetype_index=5,
        tuning=StrategyTuning(),
        need_to_call=0,
        to_call=2,
        street_put_in_at_seat=2,
        min_raise_increment=4,
        preflop_blind_level=3,
        big_blind=2,
        street_bet=4,
        max_street_contrib=3,
        signal_continue=0.99,
        weight_raise_gate=0.99,
        weight_bet_layer=0.99,
        preflop_play_metric=0.99,
    )
    with (
        mock.patch.object(bot_strategy, "bot_bb_check_or_raise_p", return_value=True),
        mock.patch.object(bot_strategy, "rng_passes_layer_gate", return_value=True),
    ):
        d = bot.decide_bb_preflop_option(obs, rng)
    assert d.kind == BotDecisionKind.BB_PREFLOP_RAISE
    assert d.bb_raise_chips == 4


def test_decide_street_rejects_wrong_context() -> None:
    bot = TableRulesBot()
    obs = SeatBotObservation(
        context="bb_preflop_option",
        seat=0,
        street=0,
        stack=1,
        archetype_index=1,
        tuning=StrategyTuning(),
        need_to_call=0,
        to_call=0,
        street_put_in_at_seat=0,
        min_raise_increment=2,
        preflop_blind_level=2,
        big_blind=2,
        street_bet=4,
        max_street_contrib=2,
        signal_continue=0.5,
        weight_raise_gate=0.5,
        weight_bet_layer=0.5,
        preflop_play_metric=0.5,
    )
    try:
        bot.decide_street_action(obs, random.Random(0))
    except ValueError as e:
        assert "street" in str(e).lower()
    else:
        raise AssertionError("expected ValueError")
