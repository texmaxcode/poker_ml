"""`SessionStore`: solver field persistence via SQLite `kv`."""

from __future__ import annotations

from texasholdemgym.backend.session_store import SessionStore
from texasholdemgym.backend.sqlite_store import AppDatabase


def test_session_store_round_trip_solver_fields(tmp_path) -> None:
    db = AppDatabase(tmp_path / "s.sqlite")
    try:
        st = SessionStore(db)
        assert st.loadSolverFields() == {}
        st.saveSolverFields({"pot": 100, "toCall": 20})
        assert st.loadSolverFields() == {"pot": 100, "toCall": 20}
    finally:
        st.deleteLater()
        db.close()


def test_session_store_load_returns_empty_on_bad_json(tmp_path) -> None:
    db = AppDatabase(tmp_path / "bad.sqlite")
    st = SessionStore(db)
    try:
        # Same key as `SessionStore` (`solver_fields_json` in kv).
        db.kv_set("solver_fields_json", "{not json")
        assert st.loadSolverFields() == {}
    finally:
        st.deleteLater()
        db.close()


def test_session_store_save_swallows_db_errors(tmp_path, monkeypatch) -> None:
    db = AppDatabase(tmp_path / "x.sqlite")
    st = SessionStore(db)
    try:

        def boom(_k: str, _v: str) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(db, "kv_set", boom)
        st.saveSolverFields({"a": 1})
    finally:
        st.deleteLater()
        db.close()
