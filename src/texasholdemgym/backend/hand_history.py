from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6 import QtCore

if TYPE_CHECKING:
    from texasholdemgym.backend.sqlite_store import AppDatabase


class HandHistory(QtCore.QObject):
    historyChanged = QtCore.Signal()

    def __init__(self, db: AppDatabase | None = None) -> None:
        super().__init__()
        self._db = db

    @QtCore.Slot(int, int, result="QVariantList")
    def listRecent(self, limit: int, offset: int):
        if self._db is None:
            return []
        return self._db.list_hands(limit, offset)

    @QtCore.Slot(int, result="QVariantMap")
    def hand(self, hid: int):
        if self._db is None:
            return {}
        return self._db.hand_by_id(int(hid))

    @QtCore.Slot()
    def clearAll(self) -> None:
        if self._db is not None:
            self._db.clear_hands()
        self.historyChanged.emit()

    @QtCore.Slot()
    def notifyHistoryChanged(self) -> None:
        self.historyChanged.emit()

    def record_completed_hand(self, payload: dict[str, Any]) -> int:
        """Persist a completed hand (`hands` / `actions` / `players`)."""
        if self._db is None:
            return -1
        try:
            hid = self._db.insert_hand_log(dict(payload))
        except Exception as exc:  # pragma: no cover — log and keep UI/game loop alive
            QtCore.qWarning(f"HandHistory: insert_hand_log failed: {exc}")
            return -1
        self.historyChanged.emit()
        return hid
