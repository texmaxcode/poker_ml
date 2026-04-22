"""
PokerGame: HUD / timer / recovery expectations (see docs/improvements.md).

Related: decision tick without `_bot_timer` → `tests/test_poker_game.py::test_poker_game_decision_tick_advances_bots_without_separate_bot_timer`.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6 import QtCore


def _decision_seconds_displayed(game) -> int:
    """Mirror `_sync_root` → `decisionSecondsLeft` for QML."""
    hs = int(game.HUMAN_HERO_SEAT)
    human_bb = bool(game._live.bb_preflop_waiting)
    human_acting = (
        game._live.acting_seat == hs
        and game._interactive_human
        and game._live.in_hand[hs]
        and not game._human_sitting_out
    )
    return int(game._decision_seconds_left if (human_acting or human_bb) else 0)


def test_hud_decision_seconds_zero_on_bot_turn_nonzero_on_hero_turn():
    """HUD shows no hero countdown on bot seats; hero seat shows internal clock."""
    from texasholdemgym.backend.poker_game import PokerGame

    g = PokerGame()
    try:
        g._interactive_human = True
        g._live.acting_seat = 3
        g._decision_seconds_left = 18
        g._live.in_hand[3] = True
        g._live.in_hand[0] = True
        assert _decision_seconds_displayed(g) == 0

        g._live.acting_seat = 0
        g._live.in_hand[0] = True
        assert _decision_seconds_displayed(g) == 18

        g._live.bb_preflop_waiting = True
        g._live.acting_seat = -1
        g._decision_seconds_left = 12
        assert _decision_seconds_displayed(g) == 12
    finally:
        g.deleteLater()


def test_begin_betting_round_invalid_first_seat_awards_uncontested_when_one_player_left():
    """`first == -1` must not leave an active hand stuck with no actor."""
    from texasholdemgym.backend.poker_game import PokerGame

    g = PokerGame(db=None, hand_history=None)
    try:
        g._live.in_progress = True
        g._live.showdown = False
        for i in range(6):
            g._player(i).participating = True
            g._live.in_hand[i] = i == 0
        g._hand_accounting.set_contrib_totals([100 if i == 0 else 0 for i in range(6)])
        g._live.button_seat = 0
        g._live.sb_seat = 0
        g._live.bb_seat = 0
        g._live.street = 0
        g._live.bb_preflop_option_open = False
        g._begin_betting_round(-1)
        assert not g.gameInProgress()
        assert g._live.acting_seat < 0
    finally:
        g.deleteLater()


def test_bot_act_recover_from_stale_acting_seat():
    """Acting seat pointing at a folded player must recover (no infinite stall)."""
    from texasholdemgym.backend.poker_game import PokerGame

    g = PokerGame(db=None, hand_history=None)
    try:
        g.beginNewHand()
        assert g.gameInProgress()
        seat = int(g._live.acting_seat)
        assert 0 <= seat < 6
        g._live.in_hand[seat] = False
        g._bot_act()
        assert not g.gameInProgress() or g._live.acting_seat < 0 or g._live.in_hand[g._live.acting_seat]
    finally:
        g.deleteLater()


def test_tick_decision_recover_when_acting_seat_negative_while_hand_live():
    """`acting_seat == -1` with `in_progress` must not strand the table (no timeout / no flop)."""
    from texasholdemgym.backend.poker_game import PokerGame

    g = PokerGame(db=None, hand_history=None)
    try:
        g.setRootObject(QtCore.QObject())
        g._interactive_human = False
        g._bot_slow_actions = False
        g._bot_decision_delay_sec = 0
        g.beginNewHand()
        assert g.gameInProgress()
        g._live.acting_seat = -1
        g._tick_decision()
        assert g._live.acting_seat >= 0 or not g.gameInProgress()
    finally:
        g.deleteLater()


def test_auto_action_timeout_folds_hero_when_facing_bet():
    from texasholdemgym.backend.poker_game import PokerGame

    g = PokerGame(db=None, hand_history=None)
    try:
        g._interactive_human = True
        g.beginNewHand()
        assert g.gameInProgress()
        g._live.acting_seat = int(g.HUMAN_HERO_SEAT)
        g._live.in_hand[g.HUMAN_HERO_SEAT] = True
        g._hand_accounting.to_call = 10
        g._hand_accounting.set_street_put_in(g.HUMAN_HERO_SEAT, 0)
        g._player(g.HUMAN_HERO_SEAT).stack_on_table = 200
        g._decision_seconds_left = 0
        g._auto_action_timeout()
        assert g._live.in_hand[g.HUMAN_HERO_SEAT] is False
    finally:
        g.deleteLater()


def test_award_uncontested_leaves_table_idle_even_if_history_raises(tmp_path):
    """Game must end even if `record_completed_hand` fails (e.g. disk full)."""
    from texasholdemgym.backend.hand_history import HandHistory
    from texasholdemgym.backend.poker_game import PokerGame
    from texasholdemgym.backend.sqlite_store import AppDatabase

    db = AppDatabase(tmp_path / "t.sqlite")
    hh = HandHistory(db)
    g = PokerGame(db=db, hand_history=hh)
    try:
        g._live.in_progress = True
        g._live.showdown = False
        for i in range(6):
            g._player(i).participating = True
            g._live.in_hand[i] = i == 1
        g._hand_accounting.set_contrib_totals([0, 80, 0, 0, 0, 0])
        g._player(1).stack_on_table = 200
        g._live.holes[1] = ((14, 3), (14, 2))
        g._hand_accounting.begin_action_log(1)
        with patch.object(hh, "record_completed_hand", side_effect=RuntimeError("disk full")):
            with pytest.raises(RuntimeError, match="disk full"):
                g._award_uncontested(1)
        assert not g.gameInProgress()
    finally:
        g.deleteLater()
        db.close()
