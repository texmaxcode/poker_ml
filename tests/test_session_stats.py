"""`BankrollSessionStats` — in-memory baselines and leaderboard-style rows."""

from __future__ import annotations

from texasholdemgym.backend.game_table import Table
from texasholdemgym.backend.session_stats import BankrollSessionStats


def _player_accessor(table: Table):
    return lambda s: table.players[s]


def test_session_stats_record_hand_ended_and_reset() -> None:
    t = Table()
    t.players[0].stack_on_table, t.players[0].bankroll_off_table = 50, 1000
    t.players[1].stack_on_table, t.players[1].bankroll_off_table = 80, 0
    stats = BankrollSessionStats()
    stats.refresh_baseline(t)
    t.players[0].stack_on_table = 70
    stats.record_hand_ended(123, t, _player_accessor(t))
    assert stats.snapshot_times_ms == [123]
    assert stats.snapshot_table_stacks[0] == t.stacks_list()
    assert stats.snapshot_totals[0][0] == 70 + 1000
    stats.reset()
    assert stats.snapshot_times_ms == []


def test_seat_ranking_rows_sorts_by_total_then_lower_seat_on_tie() -> None:
    t = Table()
    for s in range(6):
        t.players[s].stack_on_table, t.players[s].bankroll_off_table = 0, 0
    t.players[0].stack_on_table, t.players[0].bankroll_off_table = 10, 90
    t.players[1].stack_on_table, t.players[1].bankroll_off_table = 30, 70
    t.players[2].stack_on_table, t.players[2].bankroll_off_table = 100, 0
    stats = BankrollSessionStats()
    stats.baseline_table[:] = [0, 0, 0, 0, 0, 0]
    stats.baseline_total[:] = [0, 0, 0, 0, 0, 0]
    rows = stats.seat_ranking_rows(t)
    assert [r["seat"] for r in rows[:3]] == [0, 1, 2]
    assert [r["total"] for r in rows[:3]] == [100, 100, 100]
    assert rows[0]["total"] == 100
    assert rows[0]["rank"] == 1


def test_seat_ranking_profit_uses_baseline() -> None:
    t = Table()
    t.players[3].stack_on_table, t.players[3].bankroll_off_table = 40, 0
    stats = BankrollSessionStats()
    stats.baseline_table[3] = 100
    rows = {r["seat"]: r for r in stats.seat_ranking_rows(t)}
    assert rows[3]["profit"] == 40 - 100
