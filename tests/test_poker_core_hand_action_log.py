"""Hand-scoped action log."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.hand_action_log import HandActionLog


def test_begin_hand_clears_and_sets_clock() -> None:
    j = HandActionLog()
    j.append(0, 1, "Call", 2)
    j.begin_hand(12345)
    assert j.started_ms == 12345
    assert j.snapshot_actions() == []


def test_append_increments_seq() -> None:
    j = HandActionLog()
    j.begin_hand(1)
    j.append(0, 2, "SB", 1, is_blind=True)
    j.append(0, 4, "BB", 2, is_blind=True)
    rows = j.snapshot_actions()
    assert len(rows) == 2
    assert rows[0]["seq"] == 1 and rows[1]["seq"] == 2
    assert rows[0]["isBlind"] is True
