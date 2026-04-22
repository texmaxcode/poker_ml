"""`HandHistory` QML bridge when DB is absent or present."""

from __future__ import annotations

from texasholdemgym.backend.hand_history import HandHistory
from texasholdemgym.backend.sqlite_store import AppDatabase


def test_hand_history_without_db_returns_empty_slots() -> None:
    hh = HandHistory(db=None)
    try:
        assert hh.listRecent(10, 0) == []
        assert hh.hand(1) == {}
    finally:
        hh.deleteLater()


def test_record_completed_hand_without_db_returns_minus_one() -> None:
    hh = HandHistory(db=None)
    try:
        assert hh.record_completed_hand({"startedMs": 1, "endedMs": 2}) == -1
    finally:
        hh.deleteLater()


def test_clear_all_without_db_only_emits_safe() -> None:
    hh = HandHistory(db=None)
    try:
        hh.clearAll()
    finally:
        hh.deleteLater()


def test_list_recent_with_db(tmp_path) -> None:
    db = AppDatabase(tmp_path / "h.sqlite")
    try:
        hh = HandHistory(db)
        assert hh.listRecent(5, 0) == []
    finally:
        hh.deleteLater()
        db.close()


def test_notify_history_changed_emits_signal(tmp_path) -> None:
    db = AppDatabase(tmp_path / "n.sqlite")
    hh = HandHistory(db)
    try:
        got: list[int] = []
        hh.historyChanged.connect(lambda: got.append(1))
        hh.notifyHistoryChanged()
        assert got == [1]
    finally:
        hh.deleteLater()
        db.close()


def test_clear_all_with_db_emits_and_clears(tmp_path) -> None:
    db = AppDatabase(tmp_path / "c.sqlite")
    hh = HandHistory(db)
    try:
        got: list[int] = []
        hh.historyChanged.connect(lambda: got.append(1))
        hh.clearAll()
        assert got == [1]
    finally:
        hh.deleteLater()
        db.close()
