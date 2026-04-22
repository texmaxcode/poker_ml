"""Hole card → 13×13 range matrix indices."""

from __future__ import annotations

from texasholdemgym.backend.poker_core.hole_grid import hole_to_range_grid_row_col


def test_ace_king_suited_and_offsuit() -> None:
    assert hole_to_range_grid_row_col((14, 3), (13, 3)) == (0, 1)  # AKs
    assert hole_to_range_grid_row_col((14, 0), (13, 1)) == (1, 0)  # AKo


def test_pocket_pair_is_diagonal() -> None:
    assert hole_to_range_grid_row_col((14, 2), (14, 3)) == (0, 0)
