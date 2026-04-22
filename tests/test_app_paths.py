"""Lightweight checks for `app` path helpers (no full `main()` / event loop)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_repo_root_contains_poker_qml() -> None:
    from texasholdemgym.app import _qml_root, _repo_root_from_here

    root = _repo_root_from_here()
    qml = _qml_root(root)
    assert qml == root / "poker" / "qml"
    assert (qml / "Main.qml").is_file()


def test_set_default_env_is_idempotent() -> None:
    from texasholdemgym.app import _set_default_env

    _set_default_env()
    _set_default_env()
