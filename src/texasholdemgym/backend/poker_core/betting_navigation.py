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


def all_voluntary_street_actions_complete(
    seat_participating: list[bool],
    in_hand: list[bool],
    seat_buy_in: list[int],
    street_acted: list[bool],
) -> bool:
    """For a check-down (``to_call == 0``, no aggressor): every seat that can still act has acted."""
    for s in range(6):
        if not (seat_participating[s] and in_hand[s]):
            continue
        if int(seat_buy_in[s]) <= 0:
            continue
        if not bool(street_acted[s]):
            return False
    return True


def betting_round_fully_resolved(
    seat_participating: list[bool],
    in_hand: list[bool],
    street_put_in: list[int],
    seat_buy_in: list[int],
    to_call: int,
    last_raiser: int,
    street_acted: list[bool],
) -> bool:
    """End of betting round: chip matching plus full check-down when there is no facing bet."""
    if not all_called_or_folded(seat_participating, in_hand, street_put_in, seat_buy_in, to_call):
        return False
    if int(to_call) > 0:
        return True
    if int(last_raiser) >= 0:
        return True
    return all_voluntary_street_actions_complete(seat_participating, in_hand, seat_buy_in, street_acted)


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
