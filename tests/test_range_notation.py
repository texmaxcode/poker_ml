"""Preflop range string ↔ 13×13 grid (`range_notation.py`)."""

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.range_notation import (
    cell_to_token,
    format_grid_to_range,
    parse_range_to_grid,
    rank_index,
)


def test_rank_index_ace_two():
    assert rank_index("A") == 0
    assert rank_index("2") == 12


def test_parse_star_full():
    g = parse_range_to_grid("*")
    assert len(g) == 169
    assert all(x >= 0.99 for x in g)


def test_parse_pair_plus_and_suited():
    g = parse_range_to_grid("TT+")
    assert g[rank_index("T") * 13 + rank_index("T")] > 0.5
    assert g[0 * 13 + 0] > 0.5  # AA
    assert g[12 * 13 + 12] < 0.5  # 22 not in TT+

    g2 = parse_range_to_grid("AKs,AKo")
    assert g2[0 * 13 + 1] > 0.5  # AKs
    assert g2[1 * 13 + 0] > 0.5  # AKo


def test_ats_plus():
    g = parse_range_to_grid("ATs+")
    assert g[0 * 13 + 4] > 0.5  # ATs
    assert g[0 * 13 + 1] > 0.5  # AKs
    assert g[1 * 13 + 0] < 0.5  # not AKo


def test_format_roundtrip_subset():
    g = parse_range_to_grid("JJ+,AKs")
    s = format_grid_to_range(g)
    g2 = parse_range_to_grid(s)
    assert g == g2


def test_cell_to_token_matches_hole_convention():
    """AKs → row 0 col 1; AKo → row 1 col 0 (see `test_poker_game_range_grid_hole_cell`)."""
    assert cell_to_token(0, 1) == "AKs"
    assert cell_to_token(1, 0) == "AKo"


def test_all_strategy_presets_parse():
    assert len(bot_strategy.STRATEGY_RANGE_PRESETS) == bot_strategy.STRATEGY_COUNT
    for trip in bot_strategy.STRATEGY_RANGE_PRESETS:
        for s in trip:
            g = parse_range_to_grid(s)
            assert len(g) == 169
