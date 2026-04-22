"""`game_screen_sync.sync_game_screen_properties` — QML property fan-out."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from texasholdemgym.backend.game_screen_sync import sync_game_screen_properties
from texasholdemgym.backend.poker_game import PokerGame


def _app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def test_sync_game_screen_properties_smoke_collects_keys() -> None:
    _app()
    g = PokerGame()
    try:
        props: dict[str, object] = {}

        def set_root(k: str, v: object) -> None:
            props[k] = v

        sync_game_screen_properties(g, None, set_root, sync_depth=0)
        assert props["pot"] == 0
        assert len(props["seatStacks"]) == 6
        assert props["streetPhase"] in ("Preflop", "Flop", "Turn", "River", "Hand", "Showdown")
    finally:
        g.deleteLater()


def test_sync_game_screen_showdown_and_bb_wait_branches() -> None:
    _app()
    g = PokerGame()
    try:
        props: dict[str, object] = {}

        def set_root(k: str, v: object) -> None:
            props[k] = v

        g._live.showdown = True
        sync_game_screen_properties(g, None, set_root, sync_depth=0)
        assert props["streetPhase"] == "Showdown"

        props.clear()
        g._live.showdown = False
        g._live.street = 99
        sync_game_screen_properties(g, None, set_root, sync_depth=0)
        assert props["streetPhase"] == "Hand"

        props.clear()
        g._live.street = 0
        g._live.bb_preflop_waiting = True
        g._live.acting_seat = 0
        g._interactive_human = True
        g._live.in_hand[0] = True
        sync_game_screen_properties(g, None, set_root, sync_depth=0)
        assert props["humanBbPreflopOption"] is True
        assert int(props["bbPreflopMinChips"]) >= 0
    finally:
        g.deleteLater()


def test_sync_game_screen_process_events_when_depth_one() -> None:
    _app()
    g = PokerGame()
    try:
        props: dict[str, object] = {}

        def set_root(k: str, v: object) -> None:
            props[k] = v

        sync_game_screen_properties(g, None, set_root, sync_depth=1)
        assert "pot" in props
    finally:
        g.deleteLater()
