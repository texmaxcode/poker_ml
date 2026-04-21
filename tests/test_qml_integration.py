"""
Headless QML integration: load the same `Main.qml` bundle as the desktop app and assert
`game_screen` binding + `PokerGame` → QML property sync (startup race that left the table dead).

Requires Qt `rcc` on PATH (or `QT_RCC`) — same as `texasholdemgym.qt_resources`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Headless CI / dev without a display server
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QML_XHR_ALLOW_FILE_READ", "1")

import pytest
from PySide6 import QtCore, QtGui, QtQml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _try_register_qrc() -> None:
    from texasholdemgym.qt_resources import QrcRegistrationError, ensure_qrc_resources_registered

    qml_root = _repo_root() / "poker" / "qml"
    try:
        ensure_qrc_resources_registered(qml_root / "application.qrc", qml_root)
    except QrcRegistrationError as e:
        pytest.skip(str(e))


pytest.importorskip("PySide6.QtQml", reason="Qt QML not available")


def _engine_with_main_qml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    poker_game,
    hand_history,
    db,
    poker_solver,
    toy_nash_solver,
    training_store,
    trainer,
    session_store,
) -> QtQml.QQmlApplicationEngine:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TEXAS_HOLDEM_GYM_SQLITE", raising=False)

    _try_register_qrc()

    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication(sys.argv)
    assert app is not None

    qml_root = _repo_root() / "poker" / "qml"
    engine = QtQml.QQmlApplicationEngine()
    engine.addImportPath(str(qml_root))
    engine.addImportPath("qrc:/")

    ctx = engine.rootContext()
    for k, v in {
        "appFontFamily": "sans-serif",
        "appFontFamilyDisplay": "serif",
        "appFontFamilyButton": "sans-serif",
        "appFontFamilyMono": "monospace",
    }.items():
        ctx.setContextProperty(k, v)
    ctx.setContextProperty("appVersion", "test")
    ctx.setContextProperty("pokerGame", poker_game)
    ctx.setContextProperty("pokerSolver", poker_solver)
    ctx.setContextProperty("toyNashSolver", toy_nash_solver)
    ctx.setContextProperty("trainingStore", training_store)
    ctx.setContextProperty("trainer", trainer)
    ctx.setContextProperty("sessionStore", session_store)
    ctx.setContextProperty("handHistory", hand_history)

    engine.load(QtCore.QUrl("qrc:/Main.qml"))
    for _ in range(300):
        app.processEvents()
        if engine.rootObjects():
            break
    assert engine.rootObjects(), "Main.qml failed to produce root objects (check qrc / QML errors)"
    return engine


def _find_game_screen(win: QtCore.QObject) -> QtCore.QObject | None:
    return win.findChild(QtCore.QObject, "game_screen")


def _process_events() -> None:
    inst = QtGui.QGuiApplication.instance()
    if inst is not None:
        inst.processEvents()


def _full_poker_bundle(tmp_path: Path):
    from texasholdemgym.backend.hand_history import HandHistory
    from texasholdemgym.backend.poker_game import PokerGame
    from texasholdemgym.backend.poker_solver import PokerSolver
    from texasholdemgym.backend.session_store import SessionStore
    from texasholdemgym.backend.sqlite_store import AppDatabase
    from texasholdemgym.backend.toy_nash_solver import ToyNashSolver
    from texasholdemgym.backend.training import Trainer, TrainingStore

    db = AppDatabase(tmp_path / "t.sqlite")
    hand_history = HandHistory(db)
    poker_game = PokerGame(db=db, hand_history=hand_history)
    poker_solver = PokerSolver()
    toy_nash_solver = ToyNashSolver()
    training_store = TrainingStore(db)
    trainer = Trainer(training_store)
    session_store = SessionStore(db)
    return (
        db,
        hand_history,
        poker_game,
        poker_solver,
        toy_nash_solver,
        training_store,
        trainer,
        session_store,
    )


def test_qml_application_loads_main_and_finds_game_screen(tmp_path, monkeypatch):
    bundle = _full_poker_bundle(tmp_path)
    db, hand_history, poker_game, ps, tn, ts, tr, ss = bundle
    engine = None
    try:
        engine = _engine_with_main_qml(
            tmp_path,
            monkeypatch,
            poker_game=poker_game,
            hand_history=hand_history,
            db=db,
            poker_solver=ps,
            toy_nash_solver=tn,
            training_store=ts,
            trainer=tr,
            session_store=ss,
        )
        win = engine.rootObjects()[0]
        gs = _find_game_screen(win)
        assert gs is not None, "findChild(game_screen) failed — app.py bind would never attach PokerGame"
        p = QtQml.QQmlProperty(gs, "actingSeat")
        assert p.isValid()
    finally:
        if engine is not None:
            engine.deleteLater()
        poker_game.deleteLater()
        for o in (tr, ts, ss, tn, ps, hand_history):
            o.deleteLater()
        db.close()
        _process_events()


def test_qml_game_screen_acting_seat_matches_engine_after_set_root(tmp_path, monkeypatch):
    bundle = _full_poker_bundle(tmp_path)
    db, hand_history, poker_game, ps, tn, ts, tr, ss = bundle
    engine = None
    try:
        engine = _engine_with_main_qml(
            tmp_path,
            monkeypatch,
            poker_game=poker_game,
            hand_history=hand_history,
            db=db,
            poker_solver=ps,
            toy_nash_solver=tn,
            training_store=ts,
            trainer=tr,
            session_store=ss,
        )
        win = engine.rootObjects()[0]
        gs = _find_game_screen(win)
        assert gs is not None
        poker_game._interactive_human = False
        poker_game._bot_slow_actions = False
        poker_game._bot_decision_delay_sec = 0
        poker_game.setRootObject(gs)
        poker_game.beginNewHand()
        assert poker_game.gameInProgress()
        eng_seat = int(poker_game._acting_seat)
        p = QtQml.QQmlProperty(gs, "actingSeat")
        assert p.isValid()
        qml_seat = int(p.read())
        assert qml_seat == eng_seat, "QML actingSeat must match engine after setRootObject + beginNewHand"
    finally:
        if engine is not None:
            engine.deleteLater()
        poker_game.deleteLater()
        for o in (tr, ts, ss, tn, ps, hand_history):
            o.deleteLater()
        db.close()
        _process_events()


def test_qml_late_set_root_syncs_ui_after_hand_started_off_screen(tmp_path, monkeypatch):
    """Regression: hand may start with no QML root; later `setRootObject` must push `actingSeat` to GameScreen."""
    bundle = _full_poker_bundle(tmp_path)
    db, hand_history, poker_game, ps, tn, ts, tr, ss = bundle
    poker_game._interactive_human = False
    poker_game._bot_slow_actions = False
    poker_game._bot_decision_delay_sec = 0
    poker_game.beginNewHand()
    assert poker_game.gameInProgress()

    engine = None
    try:
        engine = _engine_with_main_qml(
            tmp_path,
            monkeypatch,
            poker_game=poker_game,
            hand_history=hand_history,
            db=db,
            poker_solver=ps,
            toy_nash_solver=tn,
            training_store=ts,
            trainer=tr,
            session_store=ss,
        )
        win = engine.rootObjects()[0]
        gs = _find_game_screen(win)
        assert gs is not None
        poker_game.setRootObject(gs)
        poker_game.beginNewHand()
        assert poker_game.gameInProgress()
        p = QtQml.QQmlProperty(gs, "actingSeat")
        # Timers may advance bots while Main.qml loads; UI must match engine, not a stale snapshot.
        assert int(p.read()) == int(poker_game._acting_seat)
    finally:
        if engine is not None:
            engine.deleteLater()
        poker_game.deleteLater()
        for o in (tr, ts, ss, tn, ps, hand_history):
            o.deleteLater()
        db.close()
        _process_events()


def test_qml_game_screen_pot_matches_engine_contribution_total(tmp_path, monkeypatch):
    bundle = _full_poker_bundle(tmp_path)
    db, hand_history, poker_game, ps, tn, ts, tr, ss = bundle
    engine = None
    try:
        engine = _engine_with_main_qml(
            tmp_path,
            monkeypatch,
            poker_game=poker_game,
            hand_history=hand_history,
            db=db,
            poker_solver=ps,
            toy_nash_solver=tn,
            training_store=ts,
            trainer=tr,
            session_store=ss,
        )
        # Keep a strong ref to the window — a temporary `engine.rootObjects()[0]` can be GC'd and
        # invalidate children before we read QML properties (PySide wrapper lifetime).
        win = engine.rootObjects()[0]
        gs = _find_game_screen(win)
        assert gs is not None
        poker_game._interactive_human = False
        poker_game._bot_slow_actions = False
        poker_game._bot_decision_delay_sec = 0
        poker_game.setRootObject(gs)
        poker_game.beginNewHand()
        pot_q = QtQml.QQmlProperty(gs, "pot")
        assert pot_q.isValid()
        assert int(pot_q.read()) == int(sum(poker_game._contrib_total))
    finally:
        if engine is not None:
            engine.deleteLater()
        poker_game.deleteLater()
        for o in (tr, ts, ss, tn, ps, hand_history):
            o.deleteLater()
        db.close()
        _process_events()
