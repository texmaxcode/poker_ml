"""Upstream-aligned bot strategy helpers (`bot_strategy.py`)."""

from __future__ import annotations

import random

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.poker_game import _StrategyParams


def test_bot_strategy_preset_count_and_names_length():
    assert bot_strategy.STRATEGY_COUNT == 9
    assert len(bot_strategy.STRATEGY_NAMES) == 9


def test_bot_strategy_always_call_has_zero_preflop_postflop_exponents():
    p = bot_strategy.params_for_index(0)
    assert p.preflop_exponent == 0.0 and p.postflop_exponent == 0.0


def test_bot_strategy_apply_preset_maps_gto_params_to_seat_fields():
    sp = _StrategyParams()
    bot_strategy.apply_bot_params_to_strategy_fields(sp, bot_strategy.params_for_index(8))
    assert sp.preflopExponent > 1.0
    assert sp.bbCheckraiseBonus > 0.0


def test_bot_strategy_preflop_continue_probability_is_bool():
    rng = random.Random(42)
    p = _StrategyParams()
    p.preflopExponent = 2.0
    assert bot_strategy.bot_preflop_continue_p(p, 1.0, rng) is True
    rng2 = random.Random(0)
    low = bot_strategy.bot_preflop_continue_p(p, 0.01, rng2)
    assert isinstance(low, bool)

