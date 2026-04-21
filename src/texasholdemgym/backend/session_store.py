from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6 import QtCore

if TYPE_CHECKING:
    from texasholdemgym.backend.sqlite_store import AppDatabase

_SOLVER_KV_KEY = "solver_fields_json"


class SessionStore(QtCore.QObject):
    """
    Persist solver form fields (QML `sessionStore.loadSolverFields` / `saveSolverFields`).
    Uses the shared `AppDatabase` SQLite file when provided.
    """

    def __init__(self, db: AppDatabase | None = None) -> None:
        super().__init__()
        self._db = db

    @QtCore.Slot(result="QVariantMap")
    def loadSolverFields(self):
        if self._db is None:
            return {}
        raw = self._db.kv_get(_SOLVER_KV_KEY)
        if not raw:
            return {}
        try:
            m = json.loads(raw)
            return dict(m) if isinstance(m, dict) else {}
        except Exception:
            return {}

    @QtCore.Slot("QVariantMap")
    def saveSolverFields(self, m):
        if self._db is None:
            return
        try:
            self._db.kv_set(_SOLVER_KV_KEY, json.dumps(dict(m or {}), separators=(",", ":")))
        except Exception:
            pass
