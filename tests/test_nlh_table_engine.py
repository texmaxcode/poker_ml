"""`NlhHandEngine` on a real `PokerGame` (no coverage for `poker_game.py` itself)."""

from __future__ import annotations

import sys

from PySide6 import QtWidgets

from texasholdemgym.backend.poker_game import PokerGame
from texasholdemgym.backend.table_bot import BotDecision, BotDecisionKind


def _qapp() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def test_engine_run_next_hand_timer_does_not_start_new_hand_while_in_progress() -> None:
    _ = _qapp()
    g = PokerGame()
    try:
        g._live.in_progress = True
        g._live.hand_seq = 42
        g._engine.run_next_hand_timer_fire()
        assert g._live.hand_seq == 42
    finally:
        g.deleteLater()


def test_engine_count_seat_effective_buy_in() -> None:
    _ = _qapp()
    g = PokerGame()
    try:
        g._table.start_stack = 200
        g._table.max_on_table_bb = 0
        assert g._engine.count_eligible_for_deal() >= 2
        assert g._engine.seat_eligible_for_new_hand(0) is True
        assert g._engine.effective_seat_buy_in_chips(0) == g._table.start_stack
    finally:
        g.deleteLater()


def test_engine_betting_delegates_to_street() -> None:
    _ = _qapp()
    g = PokerGame()
    try:
        assert g._engine.betting_round_fully_resolved() == g._street.betting_round_complete()
    finally:
        g.deleteLater()


def test_apply_bot_decision_bb_preflop_kind_in_street_falls_back_to_check() -> None:
    _ = _qapp()
    g = PokerGame(db=None, hand_history=None)
    try:
        g._interactive_human = False
        g._live.in_progress = True
        g._live.acting_seat = 0
        g._live.street = 1
        g._live.in_hand[0] = True
        g._player(0).stack_on_table = 200
        g._hand_accounting.to_call = 0
        g._engine.apply_bot_decision(0, BotDecision(BotDecisionKind.BB_PREFLOP_RAISE, bb_raise_chips=0))
        assert g._live.street_action_text[0] == "Check"
    finally:
        g.deleteLater()
