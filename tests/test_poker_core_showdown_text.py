"""Winner lines for HUD / history: hero is \"You\", bots match default QML names."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.showdown_text import (
    DEFAULT_SEAT_BOT_NAMES,
    format_showdown_line,
    seat_display_name,
)


def test_seat_zero_is_you() -> None:
    assert seat_display_name(0) == "You"


def test_default_bot_names_match_seats_one_to_five() -> None:
    for i, name in enumerate(DEFAULT_SEAT_BOT_NAMES, start=1):
        assert seat_display_name(i) == name


def test_custom_bot_tuple_is_used() -> None:
    assert seat_display_name(1, ("A", "B", "C", "D", "E")) == "A"


def test_unknown_seat_falls_back_to_label() -> None:
    assert seat_display_name(9) == "Seat 9"


def test_single_winner_line() -> None:
    assert format_showdown_line([0], "Full house") == "You wins — Full house"


def test_chop_line_joins_names() -> None:
    line = format_showdown_line([0, 1], "Straight")
    assert line == "You, Peter chop — Straight"


def test_empty_winners_is_generic_showdown() -> None:
    assert format_showdown_line([], "anything") == "Showdown"
