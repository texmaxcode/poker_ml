"""`HandPotState`: per-hand chip math the engine resets between streets and hands."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.hand_pot import HandPotState


def test_clear_for_new_hand_zeros_everything() -> None:
    p = HandPotState()
    p.street_put_in[0] = 5
    p.contrib_total[1] = 100
    p.to_call = 10
    p.last_raiser = 3
    p.last_raise_increment = 4
    p.preflop_blind_level = 2
    p.clear_for_new_hand()
    assert p.street_put_in == [0] * 6
    assert p.contrib_total == [0] * 6
    assert p.last_raiser == -1
    assert p.to_call == 0
    assert p.last_raise_increment == 0
    assert p.preflop_blind_level == 0


def test_reset_street_keeps_contrib_clears_street() -> None:
    p = HandPotState()
    p.contrib_total[:] = [10, 10, 0, 0, 0, 0]
    p.street_put_in[:] = [2, 2, 0, 0, 0, 0]
    p.to_call = 2
    p.reset_street(1, big_blind=2)
    assert sum(p.contrib_total) == 20
    assert p.street_put_in == [0] * 6
    assert p.to_call == 0
    assert p.last_raise_increment == 2


def test_reset_street_preflop_does_not_touch_raise_increment() -> None:
    p = HandPotState()
    p.last_raise_increment = 99
    p.reset_street(0, big_blind=2)
    assert p.last_raise_increment == 99


def test_set_after_blinds_matches_sb_bb_totals() -> None:
    p = HandPotState()
    p.street_put_in[2] = 1
    p.street_put_in[4] = 2
    p.set_after_blinds(sb_seat=2, bb_seat=4, big_blind=2)
    assert p.to_call == 2
    assert p.preflop_blind_level == 2
    assert p.last_raise_increment == 2


def test_max_street_contrib_is_highest_single_seat_on_this_street() -> None:
    p = HandPotState()
    p.street_put_in[:] = [0, 4, 10, 10, 0, 0]
    assert p.max_street_contrib() == 10
