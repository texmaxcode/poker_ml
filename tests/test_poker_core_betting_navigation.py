"""Pure navigation: remaining players, facing completion, next seat."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.betting_navigation import (
    all_called_or_folded,
    next_live_stack_seat,
    next_seat_clockwise,
    remaining_players,
)


def test_remaining_players_filters_participation_and_in_hand() -> None:
    part = [True, True, False, True, True, True]
    inh = [True, False, True, True, True, True]
    assert remaining_players(part, inh) == [0, 3, 4, 5]


def test_all_called_or_folded_true_when_matched() -> None:
    part = [True, True, True, False, False, False]
    inh = [True, True, True, False, False, False]
    street = [2, 2, 2, 0, 0, 0]
    buy = [100, 0, 100, 0, 0, 0]  # seat 1 all-in; others matched `to_call`
    assert all_called_or_folded(part, inh, street, buy, to_call=2) is True


def test_all_called_or_folded_true_when_no_bet_yet_all_zeros() -> None:
    """Fresh street: everyone matches ``to_call == 0``; do not confuse with 'street complete'."""
    part = [True] * 6
    inh = [True, True, False, False, False, False]
    street = [0, 0, 0, 0, 0, 0]
    buy = [100, 100, 0, 0, 0, 0]
    assert all_called_or_folded(part, inh, street, buy, to_call=0) is True


def test_all_called_or_folded_false_when_behind() -> None:
    part = [True, True, False, False, False, False]
    inh = [True, True, False, False, False, False]
    street = [1, 2, 0, 0, 0, 0]
    buy = [100, 100, 0, 0, 0, 0]
    assert all_called_or_folded(part, inh, street, buy, to_call=2) is False


def test_next_seat_clockwise_skips_folded_and_respects_need_chips() -> None:
    part = [True] * 6
    inh = [True, False, True, True, False, True]
    buy = [10, 0, 0, 10, 0, 10]
    assert next_seat_clockwise(0, part, inh, buy, need_chips=True) == 3
    assert next_seat_clockwise(0, part, inh, buy, need_chips=False) == 2


def test_next_live_stack_seat_ignores_in_hand() -> None:
    part = [True, True, False, False, False, False]
    buy = [5, 5, 0, 0, 0, 0]
    assert next_live_stack_seat(0, part, buy) == 1


def test_next_seat_clockwise_returns_minus_one_when_no_eligible() -> None:
    part = [True] * 6
    inh = [False] * 6
    buy = [10] * 6
    assert next_seat_clockwise(0, part, inh, buy, need_chips=True) == -1


def test_next_seat_clockwise_need_chips_all_in_zero_stack() -> None:
    """Everyone in hand but no stack: nobody can act with `need_chips=True`."""
    part = [True] * 6
    inh = [True] * 6
    buy = [0] * 6
    assert next_seat_clockwise(3, part, inh, buy, need_chips=True) == -1


def test_next_live_stack_seat_returns_minus_one_when_no_stacks_ahead() -> None:
    part = [True, True, True, False, False, False]
    buy = [0, 0, 0, 0, 0, 0]
    assert next_live_stack_seat(0, part, buy) == -1
