"""Minimum raise step: never below one big blind, never below the last raise size."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.raise_rules import min_raise_increment_chips


def test_floor_is_big_blind_when_last_raise_was_small() -> None:
    assert min_raise_increment_chips(big_blind=10, last_raise_increment=4) == 10


def test_follows_large_prior_raise_when_above_bb() -> None:
    assert min_raise_increment_chips(big_blind=10, last_raise_increment=25) == 25


def test_heads_up_bb_only_preflop_still_uses_max() -> None:
    assert min_raise_increment_chips(big_blind=2, last_raise_increment=2) == 2
