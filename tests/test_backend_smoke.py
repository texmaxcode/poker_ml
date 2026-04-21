"""Solvers, session store, training store — no full QML shell."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets


def _app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def _pump_timers(ms: int = 300) -> None:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def test_toy_nash_solver_solve_finished_signal():
    from texasholdemgym.backend.toy_nash_solver import ToyNashSolver

    _app()
    sol = ToyNashSolver()
    got: list[dict] = []

    def on_done(m):
        got.append(dict(m or {}))

    sol.solveFinished.connect(on_done)
    try:
        sol.solveKuhnAsync(10)
        _pump_timers(200)
        assert got and "summaryText" in got[0]
    finally:
        sol.deleteLater()
        _pump_timers(0)


def test_poker_solver_equity_finished_signal():
    from texasholdemgym.backend.poker_solver import PokerSolver

    _app()
    s = PokerSolver()
    got: list[dict] = []

    def on_eq(m):
        got.append(dict(m or {}))

    s.equityComputationFinished.connect(on_eq)
    try:
        s.computeEquityAsync("c1", "c2", "", "", "", "", 100, 10, 5)
        _pump_timers(200)
        assert got and "equityPct" in got[0]
    finally:
        s.deleteLater()
        _pump_timers(0)


def test_session_store_without_db_has_no_disk_persistence():
    from texasholdemgym.backend.session_store import SessionStore

    st = SessionStore(db=None)
    try:
        assert st.loadSolverFields() == {}
        st.saveSolverFields({"pot": 100})
        assert st.loadSolverFields() == {}
    finally:
        st.deleteLater()


def test_training_store_exposes_sane_defaults(tmp_path, monkeypatch):
    from texasholdemgym.backend.sqlite_store import AppDatabase
    from texasholdemgym.backend.training import TrainingStore

    monkeypatch.chdir(tmp_path)
    db = AppDatabase(tmp_path / "x.sqlite")
    st = TrainingStore(db)
    try:
        assert int(st.trainerDecisionSeconds) >= 1
        assert int(st.trainerAutoAdvanceMs) >= 1
    finally:
        st.deleteLater()
        db.close()
