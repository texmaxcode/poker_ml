"""SQLite KV for table + client flags (`game_state_persist`)."""

from __future__ import annotations

import sys

from PySide6 import QtTest, QtWidgets

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.game_state_persist import (
    GAME_STATE_KV_KEY,
    RANGES_BUNDLE_KEY,
    build_table_client_snapshot,
    clear_game_and_range_kv,
    load_table_client_from_db,
    save_table_client_to_db,
)
from texasholdemgym.backend.poker_game import PokerGame
from texasholdemgym.backend.sqlite_store import AppDatabase


def _qapp() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def test_load_table_client_returns_false_when_key_missing(tmp_path) -> None:
    db = AppDatabase(tmp_path / "a.sqlite")
    g = PokerGame()
    try:
        assert not load_table_client_from_db(db, g)
    finally:
        g.deleteLater()
        db.close()


def test_load_table_client_returns_false_when_value_not_a_dict(tmp_path) -> None:
    db = AppDatabase(tmp_path / "b.sqlite")
    db.kv_set_json(GAME_STATE_KV_KEY, [1, 2, 3])  # type: ignore[arg-type]
    g = PokerGame()
    try:
        assert not load_table_client_from_db(db, g)
    finally:
        g.deleteLater()
        db.close()


def test_build_and_save_load_roundtrip_restores_stakes_stacks_strategies(tmp_path) -> None:
    _ = _qapp()
    db = AppDatabase(tmp_path / "c.sqlite")
    g1 = PokerGame()
    g2 = PokerGame()
    try:
        g1._table.small_blind, g1._table.big_blind = 2, 4
        g1._table.street_bet, g1._table.max_on_table_bb = 8, 200
        g1._table.start_stack = 300
        g1._table.import_stacks([10, 20, 30, 40, 50, 60])
        g1._table.import_bankrolls([1, 2, 3, 4, 5, 6])
        g1._table.import_participating([True, False, True, True, True, True])
        g1._live.button_seat = 4
        g1._interactive_human = True
        g1._human_sitting_out = False
        g1._bot_slow_actions = False
        g1._winning_hand_show_ms = 9_000
        g1._bot_decision_delay_sec = 2
        g1._auto_hand_loop = True
        for s in range(6):
            g1._player(s).strategy.archetype_index = (s * 2) % bot_strategy.STRATEGY_COUNT
        save_table_client_to_db(db, g1)
        assert load_table_client_from_db(db, g2)
        assert g2._table.stacks_list() == [10, 20, 30, 40, 50, 60]
        assert g2._table.bankrolls_list() == [1, 2, 3, 4, 5, 6]
        assert g2._table.participating_list() == [True, False, True, True, True, True]
        assert g2._table.small_blind == 2
        assert g2._table.big_blind == 4
        assert g2._table.street_bet == 8
        assert g2._table.max_on_table_bb == 200
        assert g2._table.start_stack == 300
        assert g2._live.button_seat == 4
        assert g2._auto_hand_loop is True
        assert g2._winning_hand_show_ms == 9_000
        assert g2._player(g2.HUMAN_HERO_SEAT).participating is True
        for s in range(6):
            assert g2._player(s).strategy.archetype_index == (s * 2) % bot_strategy.STRATEGY_COUNT
    finally:
        g1.deleteLater()
        g2.deleteLater()
        db.close()
        for _ in (100, 100, 200):
            QtTest.QTest.qWait(0)  # drain QObject cleanup


def test_load_clamps_seat_strategy_indices(tmp_path) -> None:
    _ = _qapp()
    db = AppDatabase(tmp_path / "d.sqlite")
    g = PokerGame()
    try:
        m = {
            "sb": 1,
            "bb": 2,
            "streetBeat": 4,  # typo: engine uses "streetBet" in snapshot
            "maxTableBb": 100,
            "startStack": 200,
            "seatBuyIn": [0] * 6,
            "seatBankrollTotal": [0] * 6,
            "seatParticipating": [True] * 6,
            "seatStrategyIdx": [-1, 999, 0, 1, 2, 3],
        }
        db.kv_set_json(GAME_STATE_KV_KEY, m)  # type: ignore[arg-type]
        assert load_table_client_from_db(db, g)
        assert g._player(0).strategy.archetype_index == 0
        assert g._player(1).strategy.archetype_index == bot_strategy.STRATEGY_COUNT - 1
    finally:
        g.deleteLater()
        db.close()


def test_client_flag_emits_when_interactive_toggles_on_load(tmp_path) -> None:
    _ = _qapp()
    db = AppDatabase(tmp_path / "e.sqlite")
    g = PokerGame()
    g._interactive_human = True
    save_table_client_to_db(db, g)
    db.kv_set_json(
        GAME_STATE_KV_KEY,
        {**build_table_client_snapshot(g), "interactiveHuman": False},
    )
    try:
        spy = QtTest.QSignalSpy(g.interactiveHumanChanged)
        assert load_table_client_from_db(db, g)
        assert g._interactive_human is False
        assert spy.count() >= 1
    finally:
        g.deleteLater()
        db.close()


def test_load_emits_bot_and_timing_sliders_when_values_change(tmp_path) -> None:
    """`winningHandShowMs` / `botSlowActions` / `botDecisionDelaySec` emit when KV differs."""
    _ = _qapp()
    db = AppDatabase(tmp_path / "g.sqlite")
    g = PokerGame()
    g._winning_hand_show_ms = 1_000
    g._bot_slow_actions = True
    g._bot_decision_delay_sec = 1
    save_table_client_to_db(db, g)
    m = {**build_table_client_snapshot(g), "winningHandShowMs": 3_200, "botSlowActions": False, "botDecisionDelaySec": 3}
    db.kv_set_json(GAME_STATE_KV_KEY, m)  # type: ignore[arg-type]
    try:
        spy_w = QtTest.QSignalSpy(g.winningHandShowMsChanged)
        spy_b = QtTest.QSignalSpy(g.botSlowActionsChanged)
        spy_d = QtTest.QSignalSpy(g.botDecisionDelaySecChanged)
        assert load_table_client_from_db(db, g)
        assert g._winning_hand_show_ms == 3_200
        assert g._bot_slow_actions is False
        assert g._bot_decision_delay_sec == 3
        assert spy_w.count() >= 1
        assert spy_b.count() >= 1
        assert spy_d.count() >= 1
    finally:
        g.deleteLater()
        db.close()


def test_clear_game_and_range_kv_removes_both_keys(tmp_path) -> None:
    db = AppDatabase(tmp_path / "f.sqlite")
    db.kv_set_json(GAME_STATE_KV_KEY, {"a": 1})
    db.kv_set_json(RANGES_BUNDLE_KEY, {"b": 2})
    assert db.kv_get_json(GAME_STATE_KV_KEY) is not None
    clear_game_and_range_kv(db)
    assert db.kv_get(GAME_STATE_KV_KEY) is None
    assert db.kv_get(RANGES_BUNDLE_KEY) is None
    db.close()
