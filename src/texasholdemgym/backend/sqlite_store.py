from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

# Relational hand-log schema v1 (`hands`, `actions`, `players`).
_HAND_LOG_DDL_V1 = """
CREATE TABLE IF NOT EXISTS players (
 id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
 created_ms INTEGER NOT NULL,
 player_key INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS hands (
 id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
 started_ms INTEGER NOT NULL,
 ended_ms INTEGER NOT NULL DEFAULT 0,
 session_key INTEGER NOT NULL DEFAULT 0,
 button_seat INTEGER NOT NULL,
 sb_seat INTEGER NOT NULL,
 bb_seat INTEGER NOT NULL,
 num_players INTEGER NOT NULL,
 sb_size INTEGER NOT NULL,
 bb_size INTEGER NOT NULL,
 board_c0 INTEGER NOT NULL DEFAULT -1,
 board_c1 INTEGER NOT NULL DEFAULT -1,
 board_c2 INTEGER NOT NULL DEFAULT -1,
 board_c3 INTEGER NOT NULL DEFAULT -1,
 board_c4 INTEGER NOT NULL DEFAULT -1,
 result_flags INTEGER NOT NULL DEFAULT 0,
 players_detail_json TEXT,
 winning_hand_text TEXT
);

CREATE TABLE IF NOT EXISTS actions (
 id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
 hand_id INTEGER NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
 seq INTEGER NOT NULL,
 player_id INTEGER NOT NULL REFERENCES players(id),
 street INTEGER NOT NULL,
 action_kind INTEGER NOT NULL,
 size_chips INTEGER NOT NULL DEFAULT 0,
 facing_size INTEGER NOT NULL DEFAULT 0,
 extra INTEGER NOT NULL DEFAULT 0,
 UNIQUE(hand_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_actions_hand_player ON actions(hand_id, player_id);
CREATE INDEX IF NOT EXISTS idx_actions_hand_seq ON actions(hand_id, seq);
CREATE INDEX IF NOT EXISTS idx_hands_started ON hands(started_ms);
"""

# Stored `action_kind` values (hand log).
_ACTION_KIND_FOLD = 0
_ACTION_KIND_CHECK = 1
_ACTION_KIND_CALL = 2
_ACTION_KIND_BET = 3
_ACTION_KIND_RAISE = 4
_ACTION_KIND_ALLIN = 5

# Python engine (r,s): r in 2..14, s in 0..3 — map to wire 0..51 encoding for DB / QML.
_PY_SUIT_TO_WIRE_SUIT = (0, 3, 2, 1)  # clubs, spades, hearts, diamonds (suit index order)
_WIRE_SUIT_TO_PY_SUIT = (0, 3, 2, 1)  # inverse permutation


def _card_tuple_to_wire_int(card: tuple[int, int]) -> int:
    r, s = int(card[0]), int(card[1])
    if r < 2 or s < 0 or s > 3:
        return -1
    return (r - 2) * 4 + _PY_SUIT_TO_WIRE_SUIT[s]


def _wire_int_to_card_tuple(code: int) -> tuple[int, int]:
    if code < 0 or code > 51:
        return (-1, -1)
    ri = code // 4
    wire_si = code % 4
    return (ri + 2, _WIRE_SUIT_TO_PY_SUIT[wire_si])


def _card_asset_from_tuple(card: tuple[int, int]) -> str:
    """Same asset basename convention as `PokerGame._card_asset`."""
    r, s = card
    if r < 2 or s < 0 or s >= 4:
        return ""
    suit_name = ["clubs", "diamonds", "hearts", "spades"][s]
    rank_name = {11: "jack", 12: "queen", 13: "king", 14: "ace"}.get(r, str(r))
    return f"{suit_name}_{rank_name}.svg"


def _board_codes_from_payload(payload: dict[str, Any]) -> tuple[int, int, int, int, int]:
    raw = payload.get("boardCardCodes")
    if isinstance(raw, list):
        nums = [int(x) for x in raw[:5]]
        while len(nums) < 5:
            nums.append(-1)
        return (nums[0], nums[1], nums[2], nums[3], nums[4])
    return (-1, -1, -1, -1, -1)


def _winners_to_result_flags(winners: list[int]) -> int:
    bits = 0
    for s in winners:
        si = int(s)
        if 0 <= si < 64:
            bits |= 1 << si
    return int(bits)


def _total_hand_won_from_players_detail(players_detail: list[Any]) -> int:
    """Sum of per-seat `won` (chips from the pot this hand), not bankroll."""
    t = 0
    for p in players_detail:
        if isinstance(p, dict):
            t += int(p.get("won") or 0)
    return int(t)


def _result_flags_to_winners(flags: int) -> list[int]:
    out: list[int] = []
    for i in range(64):
        if (int(flags) >> i) & 1:
            out.append(i)
    return out


def _kind_label_to_action_kind(label: str) -> int:
    t = str(label).strip().lower()
    letters = "".join(c for c in t if c.isalpha())
    if "fold" in t or letters == "fold":
        return _ACTION_KIND_FOLD
    if "check" in t or letters == "check":
        return _ACTION_KIND_CHECK
    if "call" in t or letters == "call":
        return _ACTION_KIND_CALL
    if "raise" in t or letters.startswith("raise"):
        return _ACTION_KIND_RAISE
    if "bet" in t and "between" not in t:
        return _ACTION_KIND_BET
    if "all" in t and "in" in t or "allin" in letters:
        return _ACTION_KIND_ALLIN
    return _ACTION_KIND_CALL


def _qml_kind_from_db(
    *,
    action_kind: int,
    extra: int,
    size_chips: int,
    sb_size: int,
    bb_size: int,
    street: int,
) -> tuple[str, bool]:
    """Approximate SB/BB labels for blinds (DB stores kind + extra bit only)."""
    is_blind = bool(extra & 1)
    if is_blind and street == 0:
        if int(size_chips) == int(sb_size):
            return "SB", True
        if int(size_chips) == int(bb_size):
            return "BB", True
        if int(size_chips) > 0:
            return "Post", True
    names = {
        _ACTION_KIND_FOLD: "Fold",
        _ACTION_KIND_CHECK: "Check",
        _ACTION_KIND_CALL: "Call",
        _ACTION_KIND_BET: "Bet",
        _ACTION_KIND_RAISE: "Raise",
        _ACTION_KIND_ALLIN: "All-in",
    }
    return names.get(int(action_kind), "Call"), is_blind


def default_sqlite_path() -> Path:
    """Default DB file: **`texas-holdem-gym.sqlite`** in the process **current working directory**.

    Set **`TEXAS_HOLDEM_GYM_SQLITE`** to use another path (e.g. a copy under
    ``~/.local/share/TexasHoldemGym/`` on Linux).
    """
    override = os.environ.get("TEXAS_HOLDEM_GYM_SQLITE")
    if override:
        return Path(override).expanduser()
    return Path.cwd() / "texas-holdem-gym.sqlite"


class AppDatabase:
    """SQLite KV + relational hand log (`hands`, `actions`, `players`)."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_sqlite_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                k TEXT PRIMARY KEY NOT NULL,
                v TEXT NOT NULL
            )
            """
        )
        # Legacy JSON blob table (older Python builds); kept for migration / clear.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS hands_py (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_ms INTEGER NOT NULL,
                ended_ms INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hands_py_started ON hands_py(started_ms DESC)")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS poker_hands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_ms INTEGER NOT NULL,
                ended_ms INTEGER NOT NULL,
                button_seat INTEGER NOT NULL,
                sb_size INTEGER NOT NULL,
                bb_size INTEGER NOT NULL,
                board_display TEXT NOT NULL,
                board_assets TEXT NOT NULL,
                num_players INTEGER NOT NULL,
                winners_json TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_poker_hands_started ON poker_hands(started_ms DESC)")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS poker_hand_actions (
                hand_id INTEGER NOT NULL,
                seq INTEGER NOT NULL,
                street INTEGER NOT NULL,
                seat INTEGER NOT NULL,
                kind_label TEXT NOT NULL,
                chips INTEGER NOT NULL,
                is_blind INTEGER NOT NULL,
                PRIMARY KEY (hand_id, seq),
                FOREIGN KEY (hand_id) REFERENCES poker_hands(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS poker_hand_players (
                hand_id INTEGER NOT NULL,
                seat INTEGER NOT NULL,
                contrib INTEGER NOT NULL,
                won INTEGER NOT NULL,
                hole_svg1 TEXT NOT NULL,
                hole_svg2 TEXT NOT NULL,
                total_bankroll INTEGER NOT NULL,
                PRIMARY KEY (hand_id, seat),
                FOREIGN KEY (hand_id) REFERENCES poker_hands(id) ON DELETE CASCADE
            )
            """
        )
        self._conn.commit()
        self._ensure_hand_log_schema_v1()

    def _table_exists(self, name: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (name,),
        ).fetchone()
        return row is not None

    def _ensure_hands_players_detail_column(self) -> None:
        """Older DBs: add JSON snapshot of `playersDetail` (upstream-style hole cards / stacks per seat)."""
        if not self._table_exists("hands"):
            return
        names = {str(r[1]) for r in self._conn.execute("PRAGMA table_info(hands)").fetchall()}
        if "players_detail_json" in names:
            return
        self._conn.execute("ALTER TABLE hands ADD COLUMN players_detail_json TEXT")
        self._conn.commit()

    def _ensure_hands_winning_hand_column(self) -> None:
        """Older DBs: persisted label for the winning hand category (showdown / uncontested)."""
        if not self._table_exists("hands"):
            return
        names = {str(r[1]) for r in self._conn.execute("PRAGMA table_info(hands)").fetchall()}
        if "winning_hand_text" in names:
            return
        self._conn.execute("ALTER TABLE hands ADD COLUMN winning_hand_text TEXT")
        self._conn.commit()

    def _ensure_hand_log_schema_v1(self) -> None:
        """Apply relational hand-log DDL if missing."""
        if self._table_exists("hands"):
            try:
                self._conn.execute("PRAGMA user_version = 1")
                self._conn.commit()
            except Exception:
                pass
            self._ensure_hands_players_detail_column()
            self._ensure_hands_winning_hand_column()
            return
        self._conn.executescript(_HAND_LOG_DDL_V1)
        self._conn.execute("PRAGMA user_version = 1")
        self._conn.commit()
        self._ensure_hands_players_detail_column()
        self._ensure_hands_winning_hand_column()

    def kv_get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def kv_set(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO kv(k, v) VALUES(?, ?)
            ON CONFLICT(k) DO UPDATE SET v = excluded.v
            """,
            (key, value),
        )
        self._conn.commit()

    def kv_get_json(self, key: str) -> Any | None:
        raw = self.kv_get(key)
        if raw is None or raw == "":
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def kv_set_json(self, key: str, obj: Any) -> None:
        self.kv_set(key, json.dumps(obj, separators=(",", ":")))

    def kv_delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM kv WHERE k = ?", (key,))
        self._conn.commit()

    def insert_hand_log(self, payload: dict[str, Any]) -> int:
        """Insert one completed hand into `hands` / `actions` / `players`."""
        self._ensure_hand_log_schema_v1()
        started_ms = int(payload.get("startedMs", 0))
        ended_ms = int(payload.get("endedMs", 0))
        session_key = int(payload.get("sessionKey", 0))
        button_seat = int(payload.get("buttonSeat", 0))
        sb_seat = int(payload.get("sbSeat", 0))
        bb_seat = int(payload.get("bbSeat", 0))
        num_players = int(payload.get("numPlayers", 0))
        sb_size = int(payload.get("sbSize", 0))
        bb_size = int(payload.get("bbSize", 0))
        winners = [int(x) for x in (payload.get("winners") or [])]
        result_flags = _winners_to_result_flags(winners)
        b0, b1, b2, b3, b4 = _board_codes_from_payload(payload)
        actions_in = list(payload.get("actions") or [])
        players_detail = list(payload.get("playersDetail") or [])
        wh_raw = payload.get("winningHandName")
        if wh_raw is None:
            wh_raw = payload.get("winningHandText")
        winning_hand_text = (str(wh_raw).strip() if wh_raw is not None else "") or None
        seats_needed: set[int] = set()
        for a in actions_in:
            if isinstance(a, dict) and "seat" in a:
                seats_needed.add(int(a["seat"]))
        for p in players_detail:
            if isinstance(p, dict) and "seat" in p:
                seats_needed.add(int(p["seat"]))
        for tag in (button_seat, sb_seat, bb_seat):
            seats_needed.add(int(tag))
        cur = self._conn.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            seat_to_pid: dict[int, int] = {}
            for seat in sorted(seats_needed):
                pk = session_key * 64 + int(seat)
                cur.execute(
                    "INSERT OR IGNORE INTO players(created_ms, player_key) VALUES(?, ?)",
                    (started_ms, pk),
                )
                prow = cur.execute("SELECT id FROM players WHERE player_key = ?", (pk,)).fetchone()
                if prow is None:
                    raise RuntimeError(f"missing players row for player_key={pk}")
                seat_to_pid[int(seat)] = int(prow["id"])
            pj = json.dumps(players_detail, separators=(",", ":")) if players_detail else None
            cur.execute(
                """
                INSERT INTO hands(
                    started_ms, ended_ms, session_key, button_seat, sb_seat, bb_seat,
                    num_players, sb_size, bb_size, board_c0, board_c1, board_c2, board_c3, board_c4, result_flags,
                    players_detail_json, winning_hand_text
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    started_ms,
                    ended_ms,
                    session_key,
                    button_seat,
                    sb_seat,
                    bb_seat,
                    num_players,
                    sb_size,
                    bb_size,
                    b0,
                    b1,
                    b2,
                    b3,
                    b4,
                    result_flags,
                    pj,
                    winning_hand_text,
                ),
            )
            hid = int(cur.lastrowid)
            for a in actions_in:
                if not isinstance(a, dict):
                    continue
                seat = int(a.get("seat", -1))
                pid = seat_to_pid.get(seat)
                if pid is None:
                    pk = session_key * 64 + seat
                    cur.execute(
                        "INSERT OR IGNORE INTO players(created_ms, player_key) VALUES(?, ?)",
                        (started_ms, pk),
                    )
                    prow = cur.execute("SELECT id FROM players WHERE player_key = ?", (pk,)).fetchone()
                    if prow is None:
                        continue
                    pid = int(prow["id"])
                    seat_to_pid[seat] = pid
                if pid is None:
                    continue
                kind = _kind_label_to_action_kind(str(a.get("kindLabel", "")))
                extra = 1 if a.get("isBlind") else 0
                cur.execute(
                    """
                    INSERT INTO actions(hand_id, seq, player_id, street, action_kind, size_chips, facing_size, extra)
                    VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        hid,
                        int(a.get("seq", 0)),
                        pid,
                        int(a.get("street", 0)),
                        kind,
                        int(a.get("chips", 0)),
                        int(a.get("facingChips", 0)),
                        extra,
                    ),
                )
            self._conn.commit()
            return hid
        except Exception:
            self._conn.rollback()
            raise

    @staticmethod
    def _list_item_from_hand_row(r: sqlite3.Row) -> dict[str, Any]:
        codes = [int(r["board_c0"]), int(r["board_c1"]), int(r["board_c2"]), int(r["board_c3"]), int(r["board_c4"])]
        ranks = "23456789TJQKA"
        disp_parts: list[str] = []
        assets: list[str] = []
        for c in codes:
            if c < 0 or c > 51:
                continue
            rr, ss = _wire_int_to_card_tuple(c)
            disp_parts.append(ranks[rr - 2] + "cdhs"[ss])
            assets.append(_card_asset_from_tuple((rr, ss)))
        wj = _result_flags_to_winners(int(r["result_flags"]))
        return {
            "id": int(r["id"]),
            "startedMs": int(r["started_ms"]),
            "endedMs": int(r["ended_ms"]),
            "numPlayers": int(r["num_players"]),
            "boardDisplay": " ".join(disp_parts),
            "boardAssets": assets,
            "winners": wj,
        }

    def _list_hands_relational(self, cap: int) -> list[dict[str, Any]]:
        if not self._table_exists("hands"):
            return []
        rows = self._conn.execute(
            """
            SELECT id, started_ms, ended_ms, num_players, result_flags,
                   board_c0, board_c1, board_c2, board_c3, board_c4
            FROM hands ORDER BY id DESC LIMIT ?
            """,
            (max(0, int(cap)),),
        ).fetchall()
        return [self._list_item_from_hand_row(r) for r in rows]

    def _list_hands_poker_legacy(self, cap: int) -> list[dict[str, Any]]:
        if not self._table_exists("poker_hands"):
            return []
        rows = self._conn.execute(
            """
            SELECT id, started_ms, ended_ms, board_display, board_assets, num_players, winners_json
            FROM poker_hands ORDER BY id DESC LIMIT ?
            """,
            (max(0, int(cap)),),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                wj = json.loads(r["winners_json"])
            except Exception:
                wj = []
            if not isinstance(wj, list):
                wj = []
            try:
                ba = json.loads(r["board_assets"])
            except Exception:
                ba = []
            if not isinstance(ba, list):
                ba = []
            out.append(
                {
                    "id": int(r["id"]),
                    "startedMs": int(r["started_ms"]),
                    "endedMs": int(r["ended_ms"]),
                    "numPlayers": int(r["num_players"]),
                    "boardDisplay": str(r["board_display"]),
                    "boardAssets": ba,
                    "winners": [int(x) for x in wj],
                }
            )
        return out

    def _list_hands_hands_py(self, cap: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, started_ms, ended_ms, payload FROM hands_py ORDER BY id DESC LIMIT ?",
            (max(0, int(cap)),),
        ).fetchall()
        out2: list[dict[str, Any]] = []
        for r in rows:
            try:
                base = json.loads(r["payload"])
            except Exception:
                base = {}
            if not isinstance(base, dict):
                base = {}
            base.setdefault("id", int(r["id"]))
            base.setdefault("startedMs", int(r["started_ms"]))
            base.setdefault("endedMs", int(r["ended_ms"]))
            out2.append(base)
        return out2

    def list_hands(self, limit: int, offset: int) -> list[dict[str, Any]]:
        lim = max(0, int(limit))
        off = max(0, int(offset))
        need = lim + off
        merged: list[tuple[int, int, dict[str, Any]]] = []
        for x in self._list_hands_relational(need):
            merged.append((int(x.get("id", 0)), 0, x))
        for x in self._list_hands_poker_legacy(need):
            merged.append((int(x.get("id", 0)), 1, x))
        for x in self._list_hands_hands_py(need):
            merged.append((int(x.get("id", 0)), 2, x))
        merged.sort(key=lambda t: (-t[0], t[1]))
        return [t[2] for t in merged[off : off + lim]]

    def _hand_detail_relational(self, hid: int) -> dict[str, Any] | None:
        self._ensure_hands_players_detail_column()
        self._ensure_hands_winning_hand_column()
        row = self._conn.execute(
            """
            SELECT id, started_ms, ended_ms, session_key, button_seat, sb_seat, bb_seat, num_players,
                   sb_size, bb_size, board_c0, board_c1, board_c2, board_c3, board_c4, result_flags,
                   players_detail_json, winning_hand_text
            FROM hands WHERE id = ?
            """,
            (int(hid),),
        ).fetchone()
        if row is None:
            return None
        sk = int(row["session_key"])
        acts = self._conn.execute(
            """
            SELECT a.seq, a.street, a.action_kind, a.size_chips, a.facing_size, a.extra, p.player_key
            FROM actions a
            JOIN players p ON p.id = a.player_id
            WHERE a.hand_id = ?
            ORDER BY a.seq ASC
            """,
            (int(hid),),
        ).fetchall()
        actions: list[dict[str, Any]] = []
        for a in acts:
            pk = int(a["player_key"])
            seat = pk - sk * 64
            kl, blind = _qml_kind_from_db(
                action_kind=int(a["action_kind"]),
                extra=int(a["extra"]),
                size_chips=int(a["size_chips"]),
                sb_size=int(row["sb_size"]),
                bb_size=int(row["bb_size"]),
                street=int(a["street"]),
            )
            actions.append(
                {
                    "seq": int(a["seq"]),
                    "street": int(a["street"]),
                    "seat": int(seat),
                    "kindLabel": kl,
                    "chips": int(a["size_chips"]),
                    "isBlind": blind,
                }
            )
        item = self._list_item_from_hand_row(row)
        pd_raw = row["players_detail_json"]
        players_detail: list[Any] = []
        if pd_raw:
            try:
                loaded = json.loads(str(pd_raw))
                if isinstance(loaded, list):
                    players_detail = loaded
            except Exception:
                players_detail = []
        wh_name = ""
        try:
            wh_name = str(row["winning_hand_text"] or "").strip()
        except (KeyError, IndexError):
            wh_name = ""
        out: dict[str, Any] = {
            **item,
            "buttonSeat": int(row["button_seat"]),
            "sbSeat": int(row["sb_seat"]),
            "bbSeat": int(row["bb_seat"]),
            "sbSize": int(row["sb_size"]),
            "bbSize": int(row["bb_size"]),
            "sessionKey": sk,
            "actions": actions,
            "playersDetail": players_detail,
            "winningHandName": wh_name,
            "totalHandWonChips": _total_hand_won_from_players_detail(players_detail),
        }
        return out

    def _hand_detail_poker_legacy(self, hid: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            """
            SELECT id, started_ms, ended_ms, button_seat, sb_size, bb_size,
                   board_display, board_assets, num_players, winners_json, payload_json
            FROM poker_hands WHERE id = ?
            """,
            (int(hid),),
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        try:
            ba = json.loads(row["board_assets"])
        except Exception:
            ba = []
        try:
            wj = json.loads(row["winners_json"])
        except Exception:
            wj = []
        if not isinstance(wj, list):
            wj = []
        acts = self._conn.execute(
            """
            SELECT seq, street, seat, kind_label, chips, is_blind
            FROM poker_hand_actions WHERE hand_id = ? ORDER BY seq ASC
            """,
            (int(hid),),
        ).fetchall()
        actions = [
            {
                "seq": int(a["seq"]),
                "street": int(a["street"]),
                "seat": int(a["seat"]),
                "kindLabel": str(a["kind_label"]),
                "chips": int(a["chips"]),
                "isBlind": bool(a["is_blind"]),
            }
            for a in acts
        ]
        payload.setdefault("id", int(row["id"]))
        payload.setdefault("startedMs", int(row["started_ms"]))
        payload.setdefault("endedMs", int(row["ended_ms"]))
        payload.setdefault("buttonSeat", int(row["button_seat"]))
        payload.setdefault("sbSize", int(row["sb_size"]))
        payload.setdefault("bbSize", int(row["bb_size"]))
        payload.setdefault("boardDisplay", str(row["board_display"]))
        payload.setdefault("boardAssets", ba if isinstance(ba, list) else [])
        payload.setdefault("numPlayers", int(row["num_players"]))
        payload.setdefault("winners", [int(x) for x in wj])
        payload["actions"] = actions
        pd = payload.get("playersDetail")
        if isinstance(pd, list):
            payload["totalHandWonChips"] = _total_hand_won_from_players_detail(pd)
        return payload

    def hand_by_id(self, hid: int) -> dict[str, Any]:
        d = self._hand_detail_relational(int(hid))
        if d is not None:
            return d
        d2 = self._hand_detail_poker_legacy(int(hid))
        if d2 is not None:
            return d2
        row = self._conn.execute(
            "SELECT id, started_ms, ended_ms, payload FROM hands_py WHERE id = ?",
            (int(hid),),
        ).fetchone()
        if row is None:
            return {}
        try:
            base = json.loads(row["payload"])
        except Exception:
            base = {}
        if not isinstance(base, dict):
            base = {}
        base.setdefault("id", int(row["id"]))
        base.setdefault("startedMs", int(row["started_ms"]))
        base.setdefault("endedMs", int(row["ended_ms"]))
        pd = base.get("playersDetail")
        if isinstance(pd, list) and "totalHandWonChips" not in base:
            base["totalHandWonChips"] = _total_hand_won_from_players_detail(pd)
        return base

    def clear_hands(self) -> None:
        if self._table_exists("actions"):
            self._conn.execute("DELETE FROM actions")
        if self._table_exists("hands"):
            self._conn.execute("DELETE FROM hands")
        if self._table_exists("players"):
            self._conn.execute("DELETE FROM players")
        if self._table_exists("poker_hand_actions"):
            self._conn.execute("DELETE FROM poker_hand_actions")
        if self._table_exists("poker_hand_players"):
            self._conn.execute("DELETE FROM poker_hand_players")
        if self._table_exists("poker_hands"):
            self._conn.execute("DELETE FROM poker_hands")
        self._conn.execute("DELETE FROM hands_py")
        self._conn.commit()
