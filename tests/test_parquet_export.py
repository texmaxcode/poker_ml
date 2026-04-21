"""Parquet export (optional pandas/pyarrow)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from texasholdemgym.backend.sqlite_store import AppDatabase
from texasholdemgym.parquet_export import export_sqlite_to_parquet


pytest.importorskip("pandas")
pytest.importorskip("pyarrow")


def test_export_sqlite_to_parquet_writes_core_tables():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "s.sqlite"
        out = Path(td) / "out"
        AppDatabase(db)
        paths = export_sqlite_to_parquet(db, out)
        assert "hands" in paths and paths["hands"].is_file()
        assert "actions" in paths
        assert "players" in paths
        assert "kv" in paths
        assert "actions_with_hands" in paths

        import pandas as pd

        hands = pd.read_parquet(paths["hands"])
        assert list(hands.columns)
        assert len(hands) == 0


def test_export_sqlite_to_parquet_inserts_round_trip(tmp_path):
    db_path = tmp_path / "db.sqlite"
    out = tmp_path / "parquet"
    d = AppDatabase(db_path)
    try:
        hid = d.insert_hand_log(
            {
                "startedMs": 1000,
                "endedMs": 2000,
                "numPlayers": 2,
                "sessionKey": 0,
                "buttonSeat": 0,
                "sbSeat": 1,
                "bbSeat": 0,
                "sbSize": 1,
                "bbSize": 2,
                "boardCardCodes": [-1, -1, -1, -1, -1],
                "winners": [0],
                "actions": [
                    {
                        "seq": 0,
                        "street": 0,
                        "seat": 1,
                        "kindLabel": "Fold",
                        "chips": 0,
                        "facingChips": 0,
                        "isBlind": False,
                    },
                ],
                "playersDetail": [],
            }
        )
        assert hid > 0
    finally:
        d.close()

    paths = export_sqlite_to_parquet(db_path, out)
    import pandas as pd

    hands = pd.read_parquet(paths["hands"])
    assert len(hands) == 1
    actions = pd.read_parquet(paths["actions"])
    assert len(actions) >= 1


def test_parquet_export_cli_smoke(tmp_path):
    """Installed console script end-to-end (same code path users run)."""
    db_path = tmp_path / "cli.sqlite"
    out = tmp_path / "cli_out"
    AppDatabase(db_path)
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "texasholdemgym.parquet_export",
            "--db",
            str(db_path),
            "-o",
            str(out),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert (out / "hands.parquet").is_file()
    assert (out / "kv.parquet").is_file()
    assert "hands:" in r.stdout
