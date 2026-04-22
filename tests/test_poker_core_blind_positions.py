"""Blind / button placement for a new deal."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.blind_positions import (
    advance_button_seat,
    blind_seats_for_hand,
    first_postflop_actor,
    first_preflop_actor,
)


def test_advance_button_moves_to_next_live_stack() -> None:
    dealing = [True, True, True, False, False, False]
    part = [True, True, True, False, False, False]
    buy = [100, 100, 100, 0, 0, 0]
    assert advance_button_seat(0, dealing, part, buy) == 1


def test_heads_up_blinds_button_is_small_blind() -> None:
    part = [True, True, False, False, False, False]
    buy = [50, 50, 0, 0, 0, 0]
    sb, bb = blind_seats_for_hand(1, 2, part, buy)
    assert sb == 1
    assert bb == 0


def test_first_preflop_actor_heads_up_is_bb() -> None:
    dealing = [True, True, False, False, False, False]
    first = first_preflop_actor(0, 2, dealing, lambda _: 99)
    assert first == 0


def test_first_preflop_actor_falls_back_to_dealing_mask() -> None:
    dealing = [True, True, False, False, False, False]
    first = first_preflop_actor(0, 6, dealing, lambda _: -1)
    assert first == 0


def test_first_postflop_actor_true_heads_up_button_opens_not_bb() -> None:
    """Dealt HU: dealer is SB and opens post-flop; must not be `next_clockwise(button)` (that is BB)."""
    buy = [100, 100, 0, 0, 0, 0]
    alive = [0, 1]

    def nxt(need: bool) -> int:
        from texasholdemgym.backend.poker_core.betting_navigation import next_seat_clockwise

        part = [True] * 6
        inh = [s in alive for s in range(6)]
        return next_seat_clockwise(0, part, inh, buy, need_chips=need)

    assert first_postflop_actor(0, alive, buy, nxt, started_as_heads_up=True) == 0
    assert nxt(True) == 1


def test_first_postflop_actor_heads_up_btn_all_in_uses_clockwise() -> None:
    buy = [0, 200, 0, 0, 0, 0]
    alive = [0, 1]

    def nxt(need: bool) -> int:
        from texasholdemgym.backend.poker_core.betting_navigation import next_seat_clockwise

        part = [True] * 6
        inh = [s in alive for s in range(6)]
        return next_seat_clockwise(0, part, inh, buy, need_chips=need)

    assert first_postflop_actor(0, alive, buy, nxt, started_as_heads_up=True) == 1


def test_first_postflop_actor_three_way_uses_first_clockwise_after_button() -> None:
    buy = [100, 100, 100, 0, 0, 0]
    alive = [0, 1, 2]

    def nxt(need: bool) -> int:
        from texasholdemgym.backend.poker_core.betting_navigation import next_seat_clockwise

        part = [True] * 6
        inh = [s in alive for s in range(6)]
        return next_seat_clockwise(0, part, inh, buy, need_chips=need)

    assert first_postflop_actor(0, alive, buy, nxt, started_as_heads_up=False) == 1


def test_first_postflop_actor_two_left_after_sb_folded_is_not_true_hu_button_first() -> None:
    """BTN + BB only, but SB seat folded from a larger field: BB acts first (clockwise from BTN)."""
    buy = [100, 100, 0, 0, 0, 0]
    alive = [0, 1]

    def nxt(need: bool) -> int:
        from texasholdemgym.backend.poker_core.betting_navigation import next_seat_clockwise

        part = [True] * 6
        inh = [s in alive for s in range(6)]
        return next_seat_clockwise(0, part, inh, buy, need_chips=need)

    assert first_postflop_actor(0, alive, buy, nxt, started_as_heads_up=False) == 1
