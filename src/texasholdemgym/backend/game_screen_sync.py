"""Push `PokerGame` engine state onto the QML `GameScreen` root (Qt-free except QML property writes).

Kept separate from `poker_game.py` so the QObject stays orchestration + engine, while this module
owns the flat property list the table HUD expects.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6 import QtCore

from texasholdemgym.backend.game_table import Table
from texasholdemgym.backend.poker_core.cards import card_asset
from texasholdemgym.backend.poker_core.raise_rules import min_raise_increment_chips

try:
    from PySide6.QtQuick import QQuickItem
except ImportError:  # pragma: no cover
    QQuickItem = None  # type: ignore[misc, assignment]


def sync_game_screen_properties(
    game: Any,
    root: Any,
    set_root: Callable[[str, Any], None],
    *,
    sync_depth: int,
) -> None:
    """Mirror engine state to QML `game_screen` properties (same keys as legacy C++ sync)."""
    # Pot / slices (int amounts for QML)
    pot = int(game._hand_accounting.total_contrib_chips())
    set_root("pot", pot)
    raw_slices = game._street.pot_slices_for_hud()
    set_root("potSlices", [int(s.get("amount", 0)) if isinstance(s, dict) else int(s) for s in raw_slices])

    # Seats
    set_root("seatStacks", game._table.stacks_list())
    set_root("seatInHand", [bool(x) for x in game._live.in_hand])
    set_root("seatStreetChips", game._hand_accounting.street_put_in_list())
    set_root("seatStreetActions", list(game._live.street_action_text))

    c1 = [card_asset(h[0]) if game._live.in_hand[i] else "" for i, h in enumerate(game._live.holes)]
    c2 = [card_asset(h[1]) if game._live.in_hand[i] else "" for i, h in enumerate(game._live.holes)]
    set_root("seatC1", c1)
    set_root("seatC2", c2)

    set_root("buttonSeat", int(game._live.button_seat))
    set_root("sbSeat", int(game._live.sb_seat))
    set_root("bbSeat", int(game._live.bb_seat))
    set_root(
        "seatPositionLabels",
        [
            Table.seat_position_label(
                i,
                button_seat=int(game._live.button_seat),
                sb_seat=int(game._live.sb_seat),
                bb_seat=int(game._live.bb_seat),
                participating=game._table.participating_list(),
            )
            for i in range(6)
        ],
    )
    set_root("smallBlind", int(game._table.small_blind))
    set_root("bigBlind", int(game._table.big_blind))
    set_root("maxStreetContrib", int(game._hand_accounting.max_street_contrib()))

    # Board
    b = [card_asset(c) for c in game._live.board] + [""] * 5
    set_root("board0", b[0])
    set_root("board1", b[1])
    set_root("board2", b[2])
    set_root("board3", b[3])
    set_root("board4", b[4])

    set_root("handSeq", int(game._live.hand_seq))
    set_root("actingSeat", int(game._live.acting_seat))
    set_root("showdown", bool(game._live.showdown))
    set_root("seatParticipating", game._table.participating_list())
    set_root("humanSittingOut", bool(game._human_sitting_out))

    # Facing values for human HUD (raise/call/check affordances)
    hs = int(game.HUMAN_HERO_SEAT)
    stack0 = int(game._player(hs).stack_on_table)
    human_bb_wait = bool(game._live.bb_preflop_waiting)
    human_acting = (
        game._live.acting_seat == hs
        and game._interactive_human
        and game._live.in_hand[hs]
        and not game._human_sitting_out
    )
    human_facing = bool(
        human_acting
        and not human_bb_wait
        and game._hand_accounting.to_call > game._hand_accounting.street_put_in_at(hs)
    )
    human_open_lane = bool(
        human_acting
        and not human_bb_wait
        and game._hand_accounting.to_call <= game._hand_accounting.street_put_in_at(hs)
    )

    set_root(
        "decisionSecondsLeft",
        int(game._decision_seconds_left if (human_acting or human_bb_wait) else 0),
    )
    more_time = bool(
        (human_facing or human_open_lane or human_bb_wait)
        and game._human_more_time_available
        and (human_acting or human_bb_wait)
    )
    set_root("humanMoreTimeAvailable", more_time)

    set_root("humanBbPreflopOption", bool(human_bb_wait))
    set_root("humanCanCheck", bool(human_open_lane and not human_bb_wait))

    inc = min_raise_increment_chips(game._table.big_blind, game._hand_accounting.last_raise_increment)
    need_raw = game._hand_accounting.chips_needed_to_call(hs) if human_facing else 0
    need = min(need_raw, max(0, stack0)) if human_facing else 0
    can_raise_facing = bool(human_facing and inc > 0 and stack0 >= need + inc)
    set_root("humanCanRaiseFacing", can_raise_facing)
    set_root("facingNeedChips", int(need))
    set_root("facingMinRaiseChips", int(need + inc) if human_facing else 0)
    set_root("facingMaxChips", int(stack0) if human_facing else 0)
    set_root("facingPotAmount", int(pot))

    if human_open_lane:
        sb_open = int(game._table.street_bet)
        min_open = sb_open if stack0 >= sb_open else max(1, stack0)
        set_root("openRaiseMinChips", int(min_open))
        set_root("openRaiseMaxChips", int(stack0))
    else:
        set_root("openRaiseMinChips", 0)
        set_root("openRaiseMaxChips", 0)

    if human_bb_wait:
        bb_inc = min_raise_increment_chips(game._table.big_blind, game._hand_accounting.last_raise_increment)
        set_root("bbPreflopMinChips", int(max(1, bb_inc)))
        set_root("bbPreflopMaxChips", int(stack0))
        bb_can_raise = bool(
            bb_inc > 0
            and stack0 >= bb_inc
            and game._hand_accounting.max_street_contrib() == game._hand_accounting.preflop_blind_level
        )
        set_root("humanBbCanRaise", bb_can_raise)
    else:
        set_root("bbPreflopMinChips", 0)
        set_root("bbPreflopMaxChips", 0)
        set_root("humanBbCanRaise", False)

    set_root("humanStackChips", int(stack0))
    set_root("humanHandText", game._human_hand_line_for_ui())
    set_root("statusText", game._status_line())
    set_root("interactiveHuman", bool(game._interactive_human))
    set_root("botDecisionDelaySec", int(game._bot_decision_delay_sec))
    if game._live.showdown:
        set_root("streetPhase", "Showdown")
    elif 0 <= game._live.street < 4:
        set_root("streetPhase", ("Preflop", "Flop", "Turn", "River")[game._live.street])
    else:
        set_root("streetPhase", "Hand")

    cap = int(game._table.buy_in_cap_chips())
    can_buy = bool(
        not game._live.in_progress
        and game._interactive_human
        and stack0 <= 0
        and cap > 0
        and int(game._player(hs).bankroll_off_table) >= game._effective_seat_buy_in_chips(hs)
    )
    set_root("humanCanBuyBackIn", can_buy)
    set_root("buyInChips", int(game._effective_seat_buy_in_chips(hs)))

    game.pot_changed.emit()
    game.sessionStatsChanged.emit()

    if root is not None and QQuickItem is not None and isinstance(root, QQuickItem):
        try:
            root.update()
            win = root.window()
            if win is not None:
                win.update()
        except Exception:
            pass

    if sync_depth == 1:
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 16)
