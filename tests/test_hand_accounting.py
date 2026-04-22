"""`HandAccounting` is the only public surface over pot + action log for a deal."""

from __future__ import annotations

from texasholdemgym.backend.hand_accounting import HandAccounting


def test_clear_for_new_hand_resets_pot_not_log_until_begin() -> None:
    h = HandAccounting()
    h.add_street_and_contrib(0, 5)
    h.begin_action_log(100)
    h.append_action(0, 0, "SB", 5, is_blind=True)
    h.clear_for_new_hand()
    assert h.total_contrib_chips() == 0
    assert h.street_put_in_at(0) == 0
    # Action log rows survive clear_for_new_hand; new hand should call begin_action_log again.
    assert len(h.snapshot_actions()) == 1


def test_begin_action_log_clears_rows() -> None:
    h = HandAccounting()
    h.begin_action_log(1)
    h.append_action(0, 1, "BB", 2, is_blind=True)
    h.begin_action_log(2)
    assert h.history_started_ms() == 2
    assert h.snapshot_actions() == []


def test_last_raiser_property_round_trip() -> None:
    h = HandAccounting()
    h.last_raiser = 3
    assert h.last_raiser == 3


def test_set_contrib_totals_truncates_after_six_seats() -> None:
    h = HandAccounting()
    h.set_contrib_totals([1, 2, 3, 4, 5, 6, 99, 100])
    assert [h.contrib_at(i) for i in range(6)] == [1, 2, 3, 4, 5, 6]


def test_chips_needed_to_call_and_bump() -> None:
    h = HandAccounting()
    h.set_street_put_in(1, 2)
    h.to_call = 10
    assert h.chips_needed_to_call(1) == 8
    h.add_street_and_contrib(1, 8)
    h.bump_to_call_with_seat_street(1)
    assert h.to_call == 10
    h.add_street_and_contrib(2, 10)
    h.bump_to_call_with_seat_street(2)
    assert h.to_call == 10
