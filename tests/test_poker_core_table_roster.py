"""Tests for `poker_core.table_roster` — eligibility + bootstrap rules."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.table_roster import (
    bootstrap_playable_table,
    count_eligible_for_deal,
    dealing_mask_for_new_hand,
    seat_eligible_for_new_hand,
)


def test_count_eligible_respects_sit_out_and_participation() -> None:
    buy_in = [100, 100, 0, 0, 0, 0]
    part = [True, True, False, False, False, False]
    assert count_eligible_for_deal(buy_in, False, part) == 2
    assert count_eligible_for_deal(buy_in, True, part) == 1  # hero sits out


def test_seat_eligible_for_new_hand() -> None:
    buy_in = [50, 50, 0, 0, 0, 0]
    part = [True, False, True, True, True, True]
    assert seat_eligible_for_new_hand(0, buy_in, False, part) is True
    assert seat_eligible_for_new_hand(1, buy_in, False, part) is False  # bot off
    assert seat_eligible_for_new_hand(2, buy_in, False, part) is False  # no chips


def test_bootstrap_forces_two_bots_when_empty_table() -> None:
    sp = [True] + [False] * 5
    bi = [0, 0, 0, 0, 0, 0]
    sp2, bi2, hso, changed = bootstrap_playable_table(sp, bi, False, 200)
    assert changed is True
    assert sp2[0] and sp2[1] and sp2[2]
    assert bi2[0] >= 200 and bi2[1] >= 200 and bi2[2] >= 200
    assert count_eligible_for_deal(bi2, hso, sp2) >= 2


def test_dealing_mask_matches_seat_eligible() -> None:
    buy_in = [200] * 6
    part = [True] * 6
    m = dealing_mask_for_new_hand(buy_in, False, part)
    assert m == [seat_eligible_for_new_hand(i, buy_in, False, part) for i in range(6)]
