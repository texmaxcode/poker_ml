"""Upstream-aligned bot strategy helpers (`bot_strategy.py`)."""

from __future__ import annotations

import random

import pytest

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.game_table import StrategyTuning


def test_bot_strategy_preset_count_and_names_length():
    assert bot_strategy.STRATEGY_COUNT == 9
    assert len(bot_strategy.STRATEGY_NAMES) == 9


def test_bot_strategy_always_call_has_zero_preflop_postflop_exponents():
    p = bot_strategy.params_for_index(0)
    assert p.preflop_exponent == 0.0 and p.postflop_exponent == 0.0


def test_bot_strategy_apply_preset_maps_gto_params_to_seat_fields():
    sp = StrategyTuning()
    bot_strategy.apply_bot_params_to_strategy_fields(sp, bot_strategy.params_for_index(8))
    assert sp.preflopExponent > 1.0
    assert sp.bbCheckraiseBonus > 0.0


def test_bot_strategy_preflop_continue_probability_is_bool():
    rng = random.Random(42)
    p = StrategyTuning()
    p.preflopExponent = 2.0
    assert bot_strategy.bot_preflop_continue_p(p, 1.0, rng) is True
    rng2 = random.Random(0)
    low = bot_strategy.bot_preflop_continue_p(p, 0.01, rng2)
    assert isinstance(low, bool)


@pytest.mark.parametrize("idx", list(range(9)))
def test_params_for_index_covers_all_archetype_indices(idx: int) -> None:
    p = bot_strategy.params_for_index(idx)
    # Stable contract: every archetype has a 100bb-style buy-in and finite floats.
    assert p.buy_in_bb == 100
    assert isinstance(p.preflop_exponent, float)


def test_params_for_index_clamps_unknown_index_to_default() -> None:
    p = bot_strategy.params_for_index(99)
    assert p.preflop_exponent == 1.0
    assert p.facing_raise_bonus == 0.0


def test_strategy_summary_empty_when_index_invalid() -> None:
    assert bot_strategy.strategy_summary(-1) == ""
    assert bot_strategy.strategy_summary(10_000) == ""


def test_strategy_summary_gto_index_includes_extra_note() -> None:
    text = bot_strategy.strategy_summary(8)
    assert "GTO" in text
    assert "heuristic" in text.lower() or "equilibrium" in text

