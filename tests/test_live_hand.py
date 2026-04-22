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
