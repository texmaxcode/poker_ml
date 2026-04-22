"""Community cards: flop (3), turn (1), river (1), and all-in run-out to river."""

from __future__ import annotations

import pytest

from texasholdemgym.backend.poker_core.board_deal import deal_next_community_street, run_out_board_to_river


def test_deal_flop_takes_three_cards_and_sets_street_one() -> None:
    deck = [(0, 0), (0, 1), (0, 2), (0, 3)]
    board: list[tuple[int, int]] = []
    assert deal_next_community_street(0, board, deck) == 1
    assert len(board) == 3
    assert len(deck) == 1


def test_deal_turn_then_river_one_card_each() -> None:
    deck = [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)]
    board = [(0, 0), (0, 1), (0, 2)]
    assert deal_next_community_street(1, board, deck) == 2
    # `deck.pop()` takes from the end (same as the live engine).
    assert board == [(0, 0), (0, 1), (0, 2), (1, 4)]
    assert deal_next_community_street(2, board, deck) == 3
    assert board[-1] == (1, 3)


def test_deal_rejects_river_street_you_showdown_instead() -> None:
    deck = [(2, 0)]
    board = [(0, 0)] * 5
    with pytest.raises(ValueError, match="street_before"):
        deal_next_community_street(3, board, deck)


def test_run_out_from_preflop_deals_all_streets() -> None:
    # 3 flop + 1 turn + 1 river = 5 pops after preflop
    deck = [(i, j) for i in range(5) for j in range(5)]
    board: list[tuple[int, int]] = []
    assert run_out_board_to_river(0, board, deck) == 3
    assert len(board) == 5


def test_run_out_from_turn_only_needs_river() -> None:
    deck = [(9, 9), (8, 8)]
    board = [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert run_out_board_to_river(2, board, deck) == 3
    assert len(board) == 5


def test_run_out_at_river_is_no_op() -> None:
    deck = [(9, 9)]
    board = [(0, 0)] * 5
    before = len(deck)
    assert run_out_board_to_river(3, board, deck) == 3
    assert len(deck) == before
