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
        g._table.import_stacks([100, 0, 100, 100, 100, 100])
        g._table.import_participating([True, True, False, True, True, True])
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
            game._live.in_hand[i] = i in (0, 5)
        game._live.button_seat = 2
        game.beginNewHand()
        assert game.gameInProgress()
        assert game._live.acting_seat >= 0
        assert 0 <= game._live.sb_seat < 6 and 0 <= game._live.bb_seat < 6
        assert game._live.sb_seat != game._live.bb_seat
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
        start = int(g._live.acting_seat)
        assert start >= 0
        for _ in range(35):
            g._tick_decision()
            if int(g._live.acting_seat) != start or not g.gameInProgress():
                break
        assert int(g._live.acting_seat) != start or not g.gameInProgress()
    finally:
        g.deleteLater()


def test_poker_game_seat_position_label_full_ring():
    g = PokerGame()
    try:
        g._live.button_seat = 0
        g._live.sb_seat = 1
        g._live.bb_seat = 2
        g._table.import_participating([True] * 6)
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
        g._live.bb_seat = -1
        assert g.seatPositionLabel(0) == "—"
    finally:
        g.deleteLater()


def test_poker_game_set_root_clears_without_leak():
    """Tear down the QML root, drop connections, and allow rebinding a new object."""
    _ = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    a = QtCore.QObject()
    b = QtCore.QObject()
    g = PokerGame()
    try:
        g.setRootObject(a)
        g.setRootObject(b)
        assert g._root_obj is b
        g.setRootObject(None)
        assert g._root_obj is None
    finally:
        a.deleteLater()
        b.deleteLater()
        g.deleteLater()


def test_poker_game_emit_stats_seq_bumps_on_buy_in_and_bankroll_tweak():
    g = PokerGame()
    try:
        s0, s1 = int(g.statsSeq), int(g.statsSeq)
        g.setSeatBuyIn(0, 150)
        s1 = int(g.statsSeq)
        assert s1 > s0
        g.setSeatBankrollTotal(0, 5000)
        assert int(g.statsSeq) > s1
    finally:
        g.deleteLater()


def test_poker_game_game_screen_button_ids_use_class_constants():
    g = PokerGame()
    try:
        assert g._GAME_SCREEN_BTN_MORE_TIME == "MORE_TIME"
        g._on_game_screen_button("MORE_TIME")
    finally:
        g.deleteLater()


def test_poker_game_facing_action_codes_match_qml_contract():
    """`GameScreen` passes 0/1/2+ to `submitFacingAction`; must stay stable for QML."""
    g = PokerGame()
    try:
        assert g._FACING_FOLD == 0
        assert g._FACING_CALL == 1
    finally:
        g.deleteLater()


def test_poker_game_submit_check_or_bet_triggers_call_when_hero_must_match():
    """`submitCheckOrBet(check=True, …)` calls the engine `call` path when `chips_needed_to_call` > 0."""
    _ = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    g = PokerGame(db=None, hand_history=None)
    g.setRootObject(QtCore.QObject())
    g._interactive_human = True
    try:
        hs = int(g.HUMAN_HERO_SEAT)
        g._live.in_progress = True
        g._live.bb_preflop_waiting = False
        g._live.acting_seat = hs
        g._live.street = 1
        g._live.in_hand[:] = [True] * 6
        for i in range(6):
            g._player(i).participating = True
            g._player(i).stack_on_table = 200
        g._hand_accounting.clear_for_new_hand()
        g._hand_accounting.reset_street(1, int(g._table.big_blind))
        g._hand_accounting.to_call = 2
        g._hand_accounting.set_street_put_in(hs, 0)
        g._live.init_street_acted(g._table.participating_list(), g._live.in_hand, g._table.stacks_list())
        assert g._hand_accounting.chips_needed_to_call(hs) > 0
        g.submitCheckOrBet(True, 0)
        assert "Call" in g._live.street_action_text[hs]
    finally:
        g.deleteLater()
