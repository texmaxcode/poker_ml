from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random

RANKS = "23456789TJQKA"
SUITS = "cdhs"  # clubs, diamonds, hearts, spades


def pretty_card(card: tuple[int, int]) -> str:
    r, s = card
    if r < 2 or s < 0 or s >= 4:
        return ""
    rank = RANKS[r - 2]
    suit = SUITS[s]
    return rank + suit


def card_asset(card: tuple[int, int]) -> str:
    r, s = card
    if r < 2 or s < 0:
        return ""
    suit_name = ["clubs", "diamonds", "hearts", "spades"][s]
    rank_name = {
        11: "jack",
        12: "queen",
        13: "king",
        14: "ace",
    }.get(r, str(r))
    return f"{suit_name}_{rank_name}.svg"


def new_shuffled_deck(rng: Random) -> list[tuple[int, int]]:
    d = [(r, s) for s in range(4) for r in range(2, 15)]
    rng.shuffle(d)
    return d
