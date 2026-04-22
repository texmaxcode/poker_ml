"""Pytest: shared `QApplication` for tests that construct `PokerGame` (Qt `QObject` + timers)."""

from __future__ import annotations

import pytest
from PySide6 import QtWidgets


@pytest.fixture(scope="session")
def qapp() -> QtWidgets.QApplication:
    """Build once per session, then reuse; tests opt in with `qapp` or `usefixtures("qapp")`."""
    inst = QtWidgets.QApplication.instance()
    if inst is None:
        return QtWidgets.QApplication([])
    return inst  # type: ignore[return-value]
