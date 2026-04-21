"""Export Texas Hold'em Gym SQLite data to Parquet files for offline analysis.

Requires optional dependencies: ``pip install -e '.[analysis]'`` (pandas, pyarrow).

See ``docs/data-and-sqlite.md`` for database paths and schema.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Mirrors ``sqlite_store`` action_kind integers.
ACTION_KIND_LABELS: dict[int, str] = {
    0: "fold",
    1: "check",
    2: "call",
    3: "bet",
    4: "raise",
    5: "all_in",
}

STREET_LABELS: dict[int, str] = {
    0: "preflop",
    1: "flop",
    2: "turn",
    3: "river",
    4: "showdown",
}


def _connect_sqlite(db_path: Path) -> sqlite3.Connection:
    """Open the DB for reading. Prefer read-only URI (`Path.as_uri()` handles Windows paths); fall back on error."""
    p = db_path.resolve()
    try:
        return sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
    except (OSError, sqlite3.Error):
        # e.g. odd FS / older SQLite builds — still read-only in practice for our SELECTs.
        return sqlite3.connect(str(p))


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _read_kv_parquet(conn: sqlite3.Connection) -> Any:
    import pandas as pd

    df = pd.read_sql_query("SELECT k AS key, v AS json_text FROM kv", conn)
    if df.empty:
        return df

    def try_parse(s: str) -> Any:
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    df["value_json"] = df["json_text"].map(try_parse)
    return df


SQL_ACTIONS_WIDE = """
SELECT
  a.id AS action_row_id,
  a.hand_id,
  a.seq,
  a.street,
  a.action_kind,
  a.size_chips,
  a.facing_size,
  a.extra,
  (a.extra & 1) != 0 AS is_blind_post,
  h.started_ms,
  h.ended_ms,
  h.session_key,
  h.button_seat,
  h.sb_seat,
  h.bb_seat,
  h.num_players,
  h.sb_size,
  h.bb_size,
  h.board_c0,
  h.board_c1,
  h.board_c2,
  h.board_c3,
  h.board_c4,
  h.result_flags,
  h.winning_hand_text,
  p.id AS player_row_id,
  p.player_key,
  (p.player_key - h.session_key * 64) AS seat
FROM actions a
JOIN hands h ON h.id = a.hand_id
JOIN players p ON p.id = a.player_id
ORDER BY h.started_ms, a.seq
"""


def _enrich_actions_wide(df: Any) -> Any:
    import pandas as pd

    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    out = df.copy()
    if "action_kind" in out.columns:
        out["action_kind_label"] = out["action_kind"].map(ACTION_KIND_LABELS).fillna("unknown")
    if "street" in out.columns:
        out["street_label"] = out["street"].map(STREET_LABELS).fillna("unknown")
    return out


def _write_parquet(df: Any, path: Path) -> None:
    """Write a DataFrame to Parquet using pyarrow (matches optional-deps / docs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")


def export_sqlite_to_parquet(
    db_path: Path | None,
    output_dir: Path,
    *,
    include_kv: bool = True,
    include_actions_wide: bool = True,
    legacy_tables: bool = False,
) -> dict[str, Path]:
    """Read a Gym SQLite file and write Parquet datasets under ``output_dir``.

    :param db_path: Path to ``.sqlite`` file, or ``None`` for :func:`texasholdemgym.backend.sqlite_store.default_sqlite_path`.
    :param output_dir: Directory to create (parents are created).
    :param include_kv: Export ``kv`` settings table.
    :param include_actions_wide: Export joined ``actions_with_hands.parquet`` when relational tables exist.
    :param legacy_tables: Also export ``poker_hands`` / ``hands_py`` if present (wide JSON payloads).
    :returns: Map of logical name → output file path for files written.
    """
    import pandas as pd

    from texasholdemgym.backend.sqlite_store import default_sqlite_path

    path = Path(db_path) if db_path is not None else default_sqlite_path()
    if not path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    conn = _connect_sqlite(path)
    try:
        core = ("hands", "actions", "players")
        if all(_table_exists(conn, t) for t in core):
            hands = pd.read_sql_query("SELECT * FROM hands ORDER BY started_ms", conn)
            actions = pd.read_sql_query("SELECT * FROM actions ORDER BY hand_id, seq", conn)
            players = pd.read_sql_query("SELECT * FROM players", conn)
            if "action_kind" in actions.columns:
                actions = actions.copy()
                actions["action_kind_label"] = actions["action_kind"].map(ACTION_KIND_LABELS).fillna("unknown")
            if "street" in actions.columns:
                actions["street_label"] = actions["street"].map(STREET_LABELS).fillna("unknown")

            p_h = output_dir / "hands.parquet"
            p_a = output_dir / "actions.parquet"
            p_p = output_dir / "players.parquet"
            _write_parquet(hands, p_h)
            _write_parquet(actions, p_a)
            _write_parquet(players, p_p)
            written["hands"] = p_h
            written["actions"] = p_a
            written["players"] = p_p

            if include_actions_wide:
                wide = pd.read_sql_query(SQL_ACTIONS_WIDE, conn)
                wide = _enrich_actions_wide(wide)
                p_w = output_dir / "actions_with_hands.parquet"
                _write_parquet(wide, p_w)
                written["actions_with_hands"] = p_w
        else:
            missing = [t for t in core if not _table_exists(conn, t)]
            # Not an error — older DBs may only have legacy blobs.
            if missing:
                pass

        if include_kv and _table_exists(conn, "kv"):
            kv = _read_kv_parquet(conn)
            p_kv = output_dir / "kv.parquet"
            _write_parquet(kv, p_kv)
            written["kv"] = p_kv

        if legacy_tables:
            if _table_exists(conn, "poker_hands"):
                ph = pd.read_sql_query("SELECT * FROM poker_hands ORDER BY started_ms", conn)
                out = output_dir / "poker_hands_legacy.parquet"
                _write_parquet(ph, out)
                written["poker_hands_legacy"] = out
            if _table_exists(conn, "hands_py"):
                hp = pd.read_sql_query("SELECT * FROM hands_py ORDER BY started_ms", conn)
                out = output_dir / "hands_py_legacy.parquet"
                _write_parquet(hp, out)
                written["hands_py_legacy"] = out
    finally:
        conn.close()

    if not written:
        raise RuntimeError(
            f"No exportable tables found in {path}. "
            "Expected relational hand log (hands/actions/players) or enable --legacy if old schema rows exist."
        )
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export texas-holdem-gym.sqlite to Parquet files (hands, actions, players, optional kv)."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to .sqlite file (default: TEXAS_HOLDEM_GYM_SQLITE or ./texas-holdem-gym.sqlite in cwd)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("parquet_export"),
        help="Output directory (created if missing)",
    )
    parser.add_argument("--no-kv", action="store_true", help="Skip kv.parquet")
    parser.add_argument("--no-wide", action="store_true", help="Skip actions_with_hands.parquet")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Include legacy poker_hands / hands_py tables if present",
    )
    args = parser.parse_args(argv)

    try:
        import pandas  # noqa: F401
        import pyarrow  # noqa: F401
    except ImportError:
        print(
            "Missing dependencies. Install with:  pip install -e '.[analysis]'",
            file=sys.stderr,
        )
        return 2

    try:
        written = export_sqlite_to_parquet(
            args.db,
            args.output,
            include_kv=not args.no_kv,
            include_actions_wide=not args.no_wide,
            legacy_tables=args.legacy,
        )
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    for name, p in sorted(written.items()):
        print(f"{name}: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
