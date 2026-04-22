"""Short human-readable lines for winners (HUD / hand history)."""

from __future__ import annotations

# Match `BotNames.qml` default labels (seat 0 = hero).
DEFAULT_SEAT_BOT_NAMES = ("Peter", "James", "John", "Andrew", "Philip")


def seat_display_name(seat: int, bot_names: tuple[str, ...] = DEFAULT_SEAT_BOT_NAMES) -> str:
    s = int(seat)
    if s == 0:
        return "You"
    if 1 <= s <= 5:
        return str(bot_names[s - 1])
    return f"Seat {s}"


def format_showdown_line(
    winner_seats: list[int],
    hand_label: str,
    *,
    bot_names: tuple[str, ...] = DEFAULT_SEAT_BOT_NAMES,
) -> str:
    seats = [int(s) for s in winner_seats if int(s) >= 0]
    if not seats:
        return "Showdown"
    names = [seat_display_name(s, bot_names) for s in seats]
    label = str(hand_label).strip() or "Showdown"
    if len(names) == 1:
        return f"{names[0]} wins — {label}"
    return f"{', '.join(names)} chop — {label}"
