"""Tests for `poker_core.pot` — pot slices + showdown awards via `HandStrengthEvaluator`."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.hand_evaluation import StandardHandEvaluator
from texasholdemgym.backend.poker_core.pot import compute_pot_slices, distribute_showdown_side_pots


def test_compute_pot_slices_single_level() -> None:
    contrib = [0, 0, 10, 10, 10, 0]
    in_hand = [False, False, True, True, True, False]
    slices = compute_pot_slices(contrib, in_hand)
    assert len(slices) == 1
    assert slices[0]["amount"] == 30
    assert set(slices[0]["eligible"]) == {2, 3, 4}


def test_distribute_showdown_side_pots_play_the_board_chop() -> None:
    """Both play the same five board cards → even chop."""
    board = [(14, 0), (14, 1), (13, 2), (12, 3), (11, 0)]
    holes = [[(-1, -1), (-1, -1)]] * 6
    holes[0] = [(2, 1), (3, 2)]
    holes[1] = [(4, 3), (5, 0)]
    contrib = [20, 20, 0, 0, 0, 0]
    in_hand = [True, True, False, False, False, False]
    alive = [0, 1]
    awards = distribute_showdown_side_pots(contrib, in_hand, alive, board, holes, StandardHandEvaluator())
    assert sum(awards) == 40
    assert awards[0] == awards[1] == 20


class _FixedWinnerEvaluator:
    """Protocol test double: always ranks seat 1 above seat 0."""

    def best_rank_7(self, cards7: list[tuple[int, int]]) -> tuple:
        # Infer seat from hole cards (fragile but fine for unit test)
        if (14, 2) in cards7 and (12, 2) in cards7:
            return (8, 14)  # fake nuts for seat 1
        return (0,)


def test_distribute_showdown_respects_evaluator_protocol() -> None:
    board = [(2, 0), (3, 1), (4, 2), (5, 3), (6, 0)]
    holes = [[(-1, -1), (-1, -1)]] * 6
    holes[0] = [(7, 1), (8, 1)]
    holes[1] = [(14, 2), (12, 2)]
    contrib = [10, 10, 0, 0, 0, 0]
    in_hand = [True, True, False, False, False, False]
    awards = distribute_showdown_side_pots(contrib, in_hand, [0, 1], board, holes, _FixedWinnerEvaluator())
    assert awards[1] == 20
    assert awards[0] == 0
