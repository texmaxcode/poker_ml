"""`Table` / `Player` / `SeatStrategy`: session roster and built-in bot tuning."""

from __future__ import annotations

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.game_table import Table


def test_default_table_has_six_seats_with_balanced_bots() -> None:
    t = Table.default_six_max()
    assert len(t.players) == 6
    for i, p in enumerate(t.players):
        assert p.seat == i
        assert p.strategy.archetype_index == 6
        assert p.stack_on_table == 200
        assert p.participating is True


def test_import_stacks_and_lists_round_trip() -> None:
    t = Table.default_six_max()
    t.import_stacks([1, 2, 3, 4, 5, 6])
    assert t.stacks_list() == [1, 2, 3, 4, 5, 6]


def test_import_bankrolls_and_participating_truncates_to_six() -> None:
    t = Table.default_six_max()
    t.import_bankrolls([10, 20, 0, 0, 0, 0, 99])
    assert t.bankrolls_list()[:2] == [10, 20]
    t.import_participating([False, True] + [True] * 8)
    assert t.participating_list()[0] is False
    assert t.participating_list()[1] is True


def test_total_wealth_list_sums_bankroll_and_stack() -> None:
    t = Table.default_six_max()
    t.import_stacks([100] * 6)
    t.import_bankrolls([50, 0, 0, 0, 0, 0])
    assert t.total_wealth_list()[0] == 150


def test_reset_like_new_install_restores_defaults() -> None:
    t = Table.default_six_max()
    t.small_blind = 9
    t.players[0].stack_on_table = 1
    t.players[0].participating = False
    t.reset_like_new_install()
    assert t.small_blind == 1 and t.big_blind == 2 and t.street_bet == 4
    assert t.players[0].stack_on_table == 200 and t.players[0].participating is True
    assert t.players[0].strategy.archetype_index == 6


def test_reload_params_from_archetype_matches_bot_strategy_index() -> None:
    t = Table.default_six_max()
    p = t.players[0]
    p.strategy.archetype_index = 8
    p.strategy.reload_params_from_archetype()
    ref = bot_strategy.params_for_index(8)
    assert p.strategy.tuning.preflopExponent == ref.preflop_exponent
