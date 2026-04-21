"""PokerGame engine behaviour: lifecycle, eligibility, range mapping, SQLite hand log, HUD routes."""

from __future__ import annotations

import sys

from PySide6 import QtCore, QtWidgets

from texasholdemgym.backend.hand_history import HandHistory
from texasholdemgym.backend.poker_game import PokerGame
from texasholdemgym.backend.sqlite_store import AppDatabase
from texasholdemgym.backend.training import Trainer, TrainingStore


def test_poker_game_is_qobject():
    game = PokerGame()
    store = TrainingStore()
    trainer = Trainer(store)
    try:
        assert isinstance(game, QtCore.QObject)
        assert isinstance(store, QtCore.QObject)
        assert isinstance(trainer, QtCore.QObject)
    finally:
        for o in (trainer, store, game):
            if isinstance(o, QtCore.QObject):
                o.deleteLater()


def test_poker_game_begin_new_hand_without_qml_root():
    game = PokerGame()
    try:
        game.beginNewHand()
        assert game.statsSeq >= 0
    finally:
        game.deleteLater()


def test_poker_game_range_grid_hole_cell_matches_qml_convention():
    """13×13: row/col 0 = Ace … 12 = Two; row<col suited, row>col offsuit (RangeGrid.qml)."""
    g = PokerGame()
    try:
        assert g._hole_to_grid_row_col((14, 3), (13, 3)) == (0, 1)  # AKs
        assert g._hole_to_grid_row_col((14, 0), (13, 1)) == (1, 0)  # AKo
        assert g._hole_to_grid_row_col((14, 2), (14, 3)) == (0, 0)  # AA
    finally:
        g.deleteLater()


def test_poker_game_count_eligible_for_deal():
    g = PokerGame()
    try:
        g._seat_buy_in = [100, 0, 100, 100, 100, 100]
        g._seat_participating = [True, True, False, True, True, True]
        g._human_sitting_out = False
        assert g._count_eligible_for_deal() == 4
        g._human_sitting_out = True
        assert g._count_eligible_for_deal() == 3
    finally:
        g.deleteLater()


def test_poker_game_begin_new_hand_uses_fresh_dealing_mask_not_stale_in_hand():
    """New hand must not reuse previous `_in_hand` fold flags for blinds / first actor."""
    game = PokerGame()
    try:
        for i in range(6):
            game._in_hand[i] = i in (0, 5)
        game._button_seat = 2
        game.beginNewHand()
        assert game.gameInProgress()
        assert game._acting_seat >= 0
        assert 0 <= game._sb_seat < 6 and 0 <= game._bb_seat < 6
        assert game._sb_seat != game._bb_seat
    finally:
        game.deleteLater()


def test_poker_game_bot_only_hand_completes_and_writes_hand_history(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    db = AppDatabase(tmp_path / "session.sqlite")
    hh = HandHistory(db)
    g = PokerGame(db=db, hand_history=hh)
    dummy = QtCore.QObject()
    try:
        g._interactive_human = False
        g._bot_slow_actions = False
        g._bot_decision_delay_sec = 0
        g._winning_hand_show_ms = 150
        g.setRootObject(dummy)
        g.beginNewHand()
        assert g.gameInProgress()
        for _ in range(3000):
            app.processEvents()
            if not g.gameInProgress():
                break
        assert not g.gameInProgress()
        assert len(db.list_hands(5, 0)) >= 1
    finally:
        g.deleteLater()
        dummy.deleteLater()
        app.processEvents()
        db.close()


def test_poker_game_more_time_route_does_not_raise():
    _ = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    g = PokerGame()
    try:
        g._on_game_screen_button("MORE_TIME")
    finally:
        g.deleteLater()


def test_poker_game_decision_tick_advances_bots_without_separate_bot_timer():
    """1s decision timer must drive bot actions even if `_bot_timer` never fires."""
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication(sys.argv)
    g = PokerGame(db=None, hand_history=None)
    g.setRootObject(QtCore.QObject())
    g._interactive_human = False
    g._maybe_schedule_bot = lambda: None  # type: ignore[method-assign]
    try:
        g.beginNewHand()
        assert g.gameInProgress()
        start = int(g._acting_seat)
        assert start >= 0
        for _ in range(35):
            g._tick_decision()
            if int(g._acting_seat) != start or not g.gameInProgress():
                break
        assert int(g._acting_seat) != start or not g.gameInProgress()
    finally:
        g.deleteLater()


def test_poker_game_seat_position_label_full_ring():
    g = PokerGame()
    try:
        g._button_seat = 0
        g._sb_seat = 1
        g._bb_seat = 2
        g._seat_participating = [True] * 6
        assert g.seatPositionLabel(0) == "BTN"
        assert g.seatPositionLabel(1) == "SB"
        assert g.seatPositionLabel(2) == "BB"
        assert g.seatPositionLabel(3) == "UTG"
        assert g.seatPositionLabel(4) == "HJ"
        assert g.seatPositionLabel(5) == "CO"
    finally:
        g.deleteLater()


def test_poker_game_seat_position_label_before_deal():
    g = PokerGame()
    try:
        g._bb_seat = -1
        assert g.seatPositionLabel(0) == "—"
    finally:
        g.deleteLater()
