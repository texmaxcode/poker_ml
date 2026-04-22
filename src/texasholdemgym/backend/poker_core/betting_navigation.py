"""Pure seat-walking rules: who still has cards, who must act, next seat clockwise.

Used by `PokerGame` so the “who’s next?” logic stays small, testable, and Qt-free.
"""

from __future__ import annotations


def remaining_players(seat_participating: list[bool], in_hand: list[bool]) -> list[int]:
    return [s for s in range(6) if seat_participating[s] and in_hand[s]]


def all_called_or_folded(
    seat_participating: list[bool],
    in_hand: list[bool],
    street_put_in: list[int],
    seat_buy_in: list[int],
    to_call: int,
) -> bool:
    """Everyone still in the hand has matched `to_call` or is all-in for less."""
    for s in range(6):
        if not (seat_participating[s] and in_hand[s]):
            continue
        if seat_buy_in[s] == 0:
            continue  # all-in
        if street_put_in[s] < to_call:
            return False
    return True


def next_seat_clockwise(
    start: int,
    seat_participating: list[bool],
    in_hand: list[bool],
    seat_buy_in: list[int],
    *,
    need_chips: bool,
) -> int:
    """Next seat from `start` among players still in the hand.

    `need_chips=True` skips all-in (0-stack) players so betting does not deadlock when nobody
    can put more money in but the street is not legally complete yet.
    """
    for k in range(1, 7):
        s = (start + k) % 6
        if not (seat_participating[s] and in_hand[s]):
            continue
        if need_chips and seat_buy_in[s] <= 0:
            continue
        return s
    return -1


def next_live_stack_seat(
    start: int,
    seat_participating: list[bool],
    seat_buy_in: list[int],
) -> int:
    """Next clockwise seat with chips that is marked participating (button / blinds; ignores `_in_hand`)."""
    for k in range(1, 7):
        s = (int(start) + k) % 6
        if seat_participating[s] and seat_buy_in[s] > 0:
            return s
    return -1
