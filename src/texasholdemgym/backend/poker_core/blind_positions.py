"""Button advance and SB/BB placement for a new hand (NLHE, 6-max).

Uses the same clockwise walk as the live engine (`next_live_stack_seat` from
`betting_navigation`).
"""

from __future__ import annotations

from collections.abc import Callable

from texasholdemgym.backend.poker_core.betting_navigation import next_live_stack_seat


def advance_button_seat(
    current_button: int,
    dealing: list[bool],
    seat_participating: list[bool],
    seat_buy_in: list[int],
) -> int:
    """Move the button among seats actually playing this hand."""
    nxt = next_live_stack_seat(int(current_button), seat_participating, seat_buy_in)
    if nxt >= 0:
        return int(nxt)
    return int(next(i for i in range(6) if dealing[i]))


def blind_seats_for_hand(
    button_seat: int,
    n_live: int,
    seat_participating: list[bool],
    seat_buy_in: list[int],
) -> tuple[int, int]:
    """Return (small_blind_seat, big_blind_seat). Heads-up uses BTN as SB."""
    btn = int(button_seat)
    if n_live == 2:
        sb = btn
        bb = next_live_stack_seat(btn, seat_participating, seat_buy_in)
        if bb < 0:
            bb = btn
        return sb, int(bb)
    sb = next_live_stack_seat(btn, seat_participating, seat_buy_in)
    if sb < 0:
        sb = btn
    bb = next_live_stack_seat(sb, seat_participating, seat_buy_in)
    if bb < 0:
        bb = next_live_stack_seat(btn, seat_participating, seat_buy_in)
    return int(sb), int(bb)


def first_postflop_actor(
    button_seat: int,
    alive_seats: list[int],
    seat_buy_in: list[int],
    next_clockwise_from_button: Callable[[bool], int],
    *,
    started_as_heads_up: bool,
) -> int:
    """First seat to act on flop / turn / river (NLHE).

    **Clockwise from the button among players still in the hand** is the general rule (SB first
    when the SB seat is still in; if SB folded, the next active seat — often BB — opens).

    **True heads-up** (exactly two players were dealt this hand): the button posts the small blind
    and must act first post-flop, *not* the seat immediately clockwise after the button (that is
    the BB). Use ``started_as_heads_up`` from the deal (e.g. ``hand_num_dealt == 2``).

    Treating every two-player flop/turn/river as true HU mis-orders action after an SB folds from
    a larger field, which strands the wrong ``acting_seat`` and freezes betting/UI.
    """
    btn = int(button_seat)
    alive_set = {int(s) for s in alive_seats}
    if (
        started_as_heads_up
        and len(alive_set) == 2
        and btn in alive_set
        and int(seat_buy_in[btn]) > 0
    ):
        return btn
    first = int(next_clockwise_from_button(True))
    if first < 0:
        first = int(next_clockwise_from_button(False))
    return first


def first_preflop_actor(
    bb_seat: int,
    n_live: int,
    dealing: list[bool],
    next_seat_from_bb: Callable[[bool], int],
) -> int:
    """First seat to act preflop (heads-up: BB; else UTG clockwise from BB)."""
    bb = int(bb_seat)
    if n_live == 2:
        return bb
    first = int(next_seat_from_bb(True))
    if first < 0:
        first = int(next_seat_from_bb(False))
    if first < 0:
        for s in range(6):
            if dealing[s]:
                return int(s)
    return first
