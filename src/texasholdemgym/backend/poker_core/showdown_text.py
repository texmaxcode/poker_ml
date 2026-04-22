"""Short human-readable lines for winners (HUD / hand history).

Implemented in :mod:`texasholdemgym.backend.table_hud_text` and exposed on :class:`texasholdemgym.backend.game_table.Table`.
"""

from __future__ import annotations

from texasholdemgym.backend.table_hud_text import TableMessages

# Match `BotNames.qml` default labels (seat 0 = hero).
DEFAULT_SEAT_BOT_NAMES = TableMessages.DEFAULT_BOT_NAMES


def seat_display_name(seat: int, bot_names: tuple[str, ...] = DEFAULT_SEAT_BOT_NAMES) -> str:
    return TableMessages.seat_display_name(seat, bot_names)


def format_showdown_line(
    winner_seats: list[int],
    hand_label: str,
    *,
    bot_names: tuple[str, ...] = DEFAULT_SEAT_BOT_NAMES,
) -> str:
    return TableMessages.format_showdown_line(winner_seats, hand_label, bot_names=bot_names)
