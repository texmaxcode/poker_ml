"""Tests for `poker_core.cards` — display + deck helpers."""

from __future__ import annotations

import random

from texasholdemgym.backend.poker_core.cards import RANKS, SUITS, card_asset, new_shuffled_deck, pretty_card


def test_pretty_card_maps_rank_and_suit() -> None:
    # Ace spades: rank 14, suit 3
    assert pretty_card((14, 3)) == "As"
    assert len(RANKS) == 13
    assert len(SUITS) == 4


def test_pretty_card_invalid_returns_empty() -> None:
    assert pretty_card((1, 0)) == ""
    assert pretty_card((14, 5)) == ""


def test_card_asset_svg_path() -> None:
    assert "ace" in card_asset((14, 3))
    assert card_asset((1, 0)) == ""


def test_new_shuffled_deck_is_52_unique_cards() -> None:
    rng = random.Random(0)
    d = new_shuffled_deck(rng)
    assert len(d) == 52
    assert len(set(d)) == 52
    for r, s in d:
        assert 2 <= r <= 14
        assert 0 <= s <= 3
