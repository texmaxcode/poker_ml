"""AppDatabase: default path, KV JSON, relational hand log."""

from __future__ import annotations

from texasholdemgym.backend import sqlite_store
from texasholdemgym.backend.sqlite_store import AppDatabase


def test_sqlite_default_path_uses_cwd_when_env_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("TEXAS_HOLDEM_GYM_SQLITE", raising=False)
    monkeypatch.chdir(tmp_path)
    p = sqlite_store.default_sqlite_path()
    assert p == tmp_path / "texas-holdem-gym.sqlite"


def test_sqlite_kv_json_roundtrip_and_relational_hand_log(tmp_path):
    db = AppDatabase(tmp_path / "test.sqlite")
    try:
        db.kv_set_json("probe", {"a": 1, "b": [2, 3]})
        assert db.kv_get_json("probe") == {"a": 1, "b": [2, 3]}

        hid = db.insert_hand_log(
            {
                "startedMs": 100,
                "endedMs": 200,
                "buttonSeat": 0,
                "sbSeat": 1,
                "bbSeat": 2,
                "sessionKey": 0,
                "numPlayers": 2,
                "sbSize": 1,
                "bbSize": 2,
                "boardCardCodes": [-1, -1, -1, -1, -1],
                "winners": [0],
                "winningHandName": "Pair",
                "actions": [
                    {"seq": 1, "street": 0, "seat": 0, "kindLabel": "SB", "chips": 1, "isBlind": True}
                ],
                "playersDetail": [
                    {
                        "seat": 0,
                        "contrib": 1,
                        "won": 4,
                        "hole_svg1": "",
                        "hole_svg2": "",
                        "total_bankroll": 100,
                    }
                ],
            }
        )
        rows = db.list_hands(10, 0)
        assert len(rows) == 1
        assert rows[0]["id"] == hid

        detail = db.hand_by_id(hid)
        assert detail.get("sbSeat") == 1 and detail.get("bbSeat") == 2
        assert detail.get("actions") and detail["actions"][0].get("kindLabel") == "SB"
        pd = detail.get("playersDetail") or []
        assert len(pd) >= 1 and int(pd[0].get("seat", -1)) == 0
        assert detail.get("winningHandName") == "Pair"
        assert detail.get("totalHandWonChips") == 4
    finally:
        db.close()
