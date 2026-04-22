"""Tests for `poker_core.hand_evaluation` — rank tuples + `StandardHandEvaluator`."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.hand_evaluation import (
    StandardHandEvaluator,
    best_rank_7,
    hand_rank_5,
    rank_tuple_display_name,
    rank_tuple_to_strength_01,
)


def test_hand_rank_5_flush_beats_straight() -> None:
    # Royal-ish flush (not real deck constraint — rank logic only)
    flush = [(14, 0), (13, 0), (12, 0), (11, 0), (10, 0)]
    straight = [(14, 1), (13, 2), (12, 3), (11, 0), (10, 1)]
    assert hand_rank_5(flush) > hand_rank_5(straight)


def test_hand_rank_5_wheel_straight() -> None:
    wheel = [(14, 0), (5, 1), (4, 2), (3, 3), (2, 0)]
    r = hand_rank_5(wheel)
    assert r[0] == 4  # straight category


def test_best_rank_7_picks_nuts_from_seven() -> None:
    # Seven cards where best 5 is quad aces
    cards7 = [
        (14, 0),
        (14, 1),
        (14, 2),
        (14, 3),
        (2, 0),
        (3, 1),
        (4, 2),
    ]
    r = best_rank_7(cards7)
    assert r[0] == 7  # four of a kind


def test_rank_tuple_display_name() -> None:
    assert "Flush" in rank_tuple_display_name((5, 14, 13, 12, 11, 10))


def test_rank_tuple_to_strength_01_bounded() -> None:
    s = rank_tuple_to_strength_01((8, 14))
    assert 0.0 <= s <= 1.0


def test_standard_hand_evaluator_protocol() -> None:
    ev = StandardHandEvaluator()
    cards7 = [(14, 0), (14, 1), (13, 2), (13, 3), (12, 0), (2, 1), (3, 2)]
    assert ev.best_rank_7(cards7) == best_rank_7(cards7)
