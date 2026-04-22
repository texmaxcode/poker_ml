"""`qt_resources` helpers (rcc path resolution — no full qrc compile unless resources missing)."""

from __future__ import annotations

from texasholdemgym import qt_resources


def test_rcc_from_pyside6_returns_path_or_none() -> None:
    p = qt_resources._rcc_from_pyside6()
    assert p is None or isinstance(p, str)


def test_which_finds_nothing_for_unlikely_command() -> None:
    assert qt_resources._which("__no_such_executable_texas_holdem_gym__") is None
