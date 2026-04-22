"""Burn / deal community cards from the deck (same order as the live engine).

`street` is the betting round that just finished: 0 = preflop → deal flop, 1 = flop → turn,
2 = turn → river. After river the engine goes to showdown — do not call with `street == 3`.
"""

from __future__ import annotations

Card = tuple[int, int]


def deal_next_community_street(street_before: int, board: list[Card], deck: list[Card]) -> int:
    """Append the next street from `deck` to `board`. Returns the new street index (1–3)."""
    s = int(street_before)
    if s == 0:
        board.extend([deck.pop(), deck.pop(), deck.pop()])
        return 1
    if s == 1:
        board.append(deck.pop())
        return 2
    if s == 2:
        board.append(deck.pop())
        return 3
    raise ValueError(f"cannot deal: street_before must be 0, 1, or 2 (got {s})")


def run_out_board_to_river(street: int, board: list[Card], deck: list[Card]) -> int:
    """Deal every missing board street until the river is out (all-in runout). Returns `3`."""
    st = int(street)
    while st < 3:
        st = deal_next_community_street(st, board, deck)
    return st
