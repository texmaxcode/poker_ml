"""`LiveHandState`: one object holds the current deal's cards and positions."""

from __future__ import annotations

from texasholdemgym.backend.live_hand import LiveHandState


def test_default_holes_are_six_independent_pairs() -> None:
    h = LiveHandState()
    assert len(h.holes) == 6
    h.holes[0][0] = (14, 0)
    assert h.holes[1][0] == (-1, -1)


def test_reset_for_new_deal_clears_showdown_flags() -> None:
    h = LiveHandState()
    h.showdown = True
    h.showdown_status_text = "You wins — Full house"
    h.bb_preflop_waiting = True
    h.reset_for_new_deal()
    assert h.showdown is False
    assert h.showdown_status_text == ""
    assert h.bb_preflop_waiting is False


def test_clear_showdown_banner_only_clears_banner_fields() -> None:
    h = LiveHandState()
    h.showdown = True
    h.showdown_status_text = "x"
    h.in_progress = True
    h.clear_showdown_banner()
    assert h.showdown is False
    assert h.showdown_status_text == ""
    assert h.in_progress is True


def test_init_street_acted_marks_all_in_seats() -> None:
    h = LiveHandState()
    part = [True] * 6
    inn = [True] * 6
    stacks = [100, 0, 100, 100, 100, 100]
    h.init_street_acted(part, inn, stacks)
    assert h.street_acted[1] is True
    assert h.street_acted[0] is False
