"""6-max table HUD copy: seat labels, showdown line, status strip, hero hole text.

``Table`` delegates to this module so QML-facing strings stay in one place.
"""

from __future__ import annotations

from typing import Final, TypeAlias

from texasholdemgym.backend.poker_core.cards import pretty_card

Card: TypeAlias = tuple[int, int]


class TableMessages:
    """User-facing strings for a 6-max table (matches ``BotNames.qml`` / legacy upstream)."""

    HERO_SEAT: Final[int] = 0
    DEFAULT_BOT_NAMES: Final[tuple[str, str, str, str, str]] = (
        "Peter",
        "James",
        "John",
        "Andrew",
        "Philip",
    )
    STREET_LABELS: Final[tuple[str, str, str, str]] = ("Preflop", "Flop", "Turn", "River")

    @staticmethod
    def seat_display_name(
        seat: int,
        bot_names: tuple[str, ...] | None = None,
    ) -> str:
        """Label for a seat: ``You``, bot name, or ``Seat n`` for out-of-range seats."""
        bn: tuple[str, ...] = bot_names if bot_names is not None else TableMessages.DEFAULT_BOT_NAMES
        s = int(seat)
        if s == TableMessages.HERO_SEAT:
            return "You"
        if 1 <= s <= 5:
            return str(bn[s - 1])
        return f"Seat {s}"

    @staticmethod
    def format_showdown_line(
        winner_seats: list[int],
        hand_label: str,
        *,
        bot_names: tuple[str, ...] | None = None,
    ) -> str:
        """Single-winner or chop line with hand name (e.g. ``You wins — Two pair``)."""
        bn = bot_names if bot_names is not None else TableMessages.DEFAULT_BOT_NAMES
        seats = [int(s) for s in winner_seats if int(s) >= 0]
        if not seats:
            return "Showdown"
        names = [TableMessages.seat_display_name(s, bn) for s in seats]
        label = str(hand_label).strip() or "Showdown"
        if len(names) == 1:
            return f"{names[0]} wins — {label}"
        return f"{', '.join(names)} chop — {label}"

    @staticmethod
    def hud_status_line(
        street_index: int,
        pot_chips: int,
        acting_seat: int,
        *,
        showdown: bool,
        showdown_status_text: str,
        bb_preflop_waiting: bool,
        interactive_human: bool,
        hero_seat: int = 0,
        bot_names: tuple[str, ...] | None = None,
    ) -> str:
        """Short HUD line: ``Preflop $4 You`` (legacy upstream table strip)."""
        if showdown:
            return showdown_status_text or "Showdown"
        st = (
            TableMessages.STREET_LABELS[street_index]
            if 0 <= street_index < len(TableMessages.STREET_LABELS)
            else "Hand"
        )
        pot = int(pot_chips)
        if acting_seat < 0 and not bb_preflop_waiting:
            return f"{st} ${pot}"
        hs = int(hero_seat)
        who = (
            "You"
            if (acting_seat == hs or bb_preflop_waiting) and interactive_human
            else TableMessages.seat_display_name(acting_seat, bot_names)
        )
        return f"{st} ${pot} {who}"

    @staticmethod
    def hero_hole_hud_text(
        h0: Card,
        h1: Card,
        *,
        hero_in_hand: bool,
        human_sitting_out: bool,
    ) -> str:
        """Space-separated pretty cards for the hero, or empty when not shown."""
        if not hero_in_hand or human_sitting_out:
            return ""
        if h0[0] < 2 or h1[0] < 2:
            return ""
        return f"{pretty_card(h0)} {pretty_card(h1)}".strip()
