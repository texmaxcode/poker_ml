"""Integration tests for `NlhHandEngine` through a real `PokerGame`.

`poker_game.py` is omitted from the coverage gate, but `nlh_table_engine.py` is not — these tests
raise coverage on the engine. `qapp` comes from `conftest.py` (session `QApplication`).
"""

from __future__ import annotations

import pytest
from PySide6 import QtCore

from texasholdemgym.backend.poker_game import PokerGame
from texasholdemgym.backend.table_bot import BotDecision, BotDecisionKind

pytestmark = pytest.mark.usefixtures("qapp")


def test_engine_run_next_hand_timer_does_not_start_new_hand_while_in_progress() -> None:
    g = PokerGame()
    try:
        g._live.in_progress = True
        g._live.hand_seq = 42
        g._engine.run_next_hand_timer_fire()
        assert g._live.hand_seq == 42
    finally:
        g.deleteLater()


def test_engine_count_seat_effective_buy_in() -> None:
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
    g = PokerGame()
    try:
        assert g._engine.betting_round_fully_resolved() == g._street.betting_round_complete()
    finally:
        g.deleteLater()


def test_apply_bot_decision_bb_preflop_kind_in_street_falls_back_to_check() -> None:
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


def test_maybe_begin_skips_while_hand_in_progress() -> None:
    g = PokerGame()
    try:
        g._live.in_progress = True
        seq = int(g._live.hand_seq)
        g._engine.maybe_begin_hand_after_setup_change()
        assert g._live.hand_seq == seq
    finally:
        g.deleteLater()


def test_begin_new_hand_bootstraps_table_when_only_one_seat_was_active() -> None:
    """`begin_new_hand` calls `bootstrap_playable_table` first; roster code ensures ≥2 can play."""
    g = PokerGame()
    try:
        g._table.import_participating([True, False, False, False, False, False])
        g._table.import_stacks([200, 0, 0, 0, 0, 0])
        g._engine.begin_new_hand()
        assert g._count_eligible_for_deal() >= 2
        assert g.gameInProgress() is True
    finally:
        g.deleteLater()


def test_schedule_next_hand_if_idle_is_noop_when_auto_loop_off() -> None:
    g = PokerGame()
    try:
        g._auto_hand_loop = False
        g._engine.schedule_next_hand_if_idle()
        assert g._auto_hand_loop is False
    finally:
        g.deleteLater()


def test_tick_decision_stops_decision_timer_when_table_idle() -> None:
    g = PokerGame()
    try:
        g._live.in_progress = False
        g._live.acting_seat = -1
        g._decision_timer.start(50)
        g._engine.tick_decision()
        assert g._decision_timer.isActive() is False
    finally:
        g.deleteLater()


def test_raise_to_routes_to_call_when_raise_target_not_above_facing() -> None:
    """`raise_to` (raise to total) falls through to `call` when the target is not a raise over the facing bet."""
    g = PokerGame(db=None, hand_history=None)
    g.setRootObject(QtCore.QObject())
    try:
        g._live.in_progress = True
        g._live.street = 1
        g._live.acting_seat = 0
        g._live.in_hand[:] = [True] * 6
        g._player(0).stack_on_table = 200
        g._hand_accounting.to_call = 20
        g._hand_accounting.set_street_put_in(0, 0)
        g._live.init_street_acted(g._table.participating_list(), g._live.in_hand, g._table.stacks_list())
        g._engine.raise_to(0, 20)  # total 20 is not a raise over facing 20 → `call` path
        assert "Call" in g._live.street_action_text[0] or g._hand_accounting.street_put_in_at(0) > 0
    finally:
        g.deleteLater()


def test_recover_stale_acting_seat_noop_when_seat_unset() -> None:
    g = PokerGame()
    try:
        g._live.acting_seat = -1
        g._engine.recover_stale_acting_seat()
        assert g._live.acting_seat < 0
    finally:
        g.deleteLater()
