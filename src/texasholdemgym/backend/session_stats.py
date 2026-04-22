"""In-memory session bankroll baselines and chart snapshots (not persisted to SQLite)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from texasholdemgym.backend.game_table import Player, Table


@dataclass
class BankrollSessionStats:
    """Leaderboard baselines and per-hand stack / total snapshots for the Stats screen."""

    snapshot_times_ms: list[int] = field(default_factory=list)
    snapshot_table_stacks: list[list[int]] = field(default_factory=list)
    snapshot_totals: list[list[int]] = field(default_factory=list)
    baseline_table: list[int] = field(default_factory=lambda: [0] * 6)
    baseline_total: list[int] = field(default_factory=lambda: [0] * 6)

    def refresh_baseline(self, table: Table) -> None:
        t0, tot0 = table.session_baseline_snapshot()
        self.baseline_table[:] = list(t0)
        self.baseline_total[:] = list(tot0)

    def record_hand_ended(
        self,
        ended_ms: int,
        table: Table,
        player: Callable[[int], Player],
    ) -> None:
        self.snapshot_times_ms.append(int(ended_ms))
        self.snapshot_table_stacks.append(table.stacks_list())
        self.snapshot_totals.append(
            [int(player(i).bankroll_off_table + player(i).stack_on_table) for i in range(6)]
        )

    def reset(self) -> None:
        self.snapshot_times_ms.clear()
        self.snapshot_table_stacks.clear()
        self.snapshot_totals.clear()

    def seat_ranking_rows(self, table: Table) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for s in range(6):
            on_table = int(table.players[s].stack_on_table)
            off = int(table.players[s].bankroll_off_table)
            tot = int(off + on_table)
            t0 = int(self.baseline_table[s])
            tot0 = int(self.baseline_total[s])
            rows.append(
                {
                    "seat": s,
                    "table": on_table,
                    "offTable": off,
                    "total": tot,
                    "stack": on_table,
                    "wallet": off,
                    "profit": int(on_table - t0),
                    "totalDelta": int(tot - tot0),
                }
            )
        rows.sort(key=lambda r: (-int(r["total"]), int(r["seat"])))
        out: list[dict[str, Any]] = []
        for i, r in enumerate(rows):
            m = dict(r)
            m["rank"] = i + 1
            out.append(m)
        return out
