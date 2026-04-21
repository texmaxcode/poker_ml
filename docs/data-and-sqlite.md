# SQLite data & Parquet export

The app stores settings and hand history in **SQLite** with a **`kv`** table for JSON settings and normalized **`hands`**, **`actions`**, **`players`** tables (`PRAGMA user_version = 1`). Schema DDL and inserts live in `src/texasholdemgym/backend/sqlite_store.py`.

## Bundled export tool (recommended)

Install analysis dependencies once (from the repository root):

```bash
pip install -e '.[analysis]'
```

Export the default database (**`./texas-holdem-gym.sqlite`** in the current working directory) into a folder of Parquet files:

```bash
texas-holdem-parquet-export -o ./parquet_export
```

Use a specific file (for example after copying the DB away from the running app):

```bash
texas-holdem-parquet-export --db /path/to/texas-holdem-gym.sqlite -o ./parquet_export
```

| Flag | Meaning |
|------|---------|
| `-o`, `--output` | Output directory (created if missing; default: `./parquet_export`) |
| `--db` | Path to the `.sqlite` file (default: `TEXAS_HOLDEM_GYM_SQLITE` or `./texas-holdem-gym.sqlite`) |
| `--no-kv` | Skip `kv.parquet` (settings only) |
| `--no-wide` | Skip `actions_with_hands.parquet` (joined hand + action rows) |
| `--legacy` | Also write `poker_hands_legacy.parquet` / `hands_py_legacy.parquet` if those legacy tables exist |

**Files written** (when the relational hand log is present):

| File | Contents |
|------|----------|
| `hands.parquet` | One row per completed hand |
| `actions.parquet` | One row per action; extra columns `action_kind_label`, `street_label` |
| `players.parquet` | Player rows keyed by `player_key` |
| `actions_with_hands.parquet` | Join of actions ↔ hands ↔ players with `seat` derived per hand |
| `kv.parquet` | Settings: columns `key`, `json_text`, `value_json` (parsed JSON where valid) |

Python API (same output as the CLI):

```python
from pathlib import Path
from texasholdemgym.parquet_export import export_sqlite_to_parquet

export_sqlite_to_parquet(Path("texas-holdem-gym.sqlite"), Path("parquet_export"))
```

## Exploration notebook

After exporting, open **`notebooks/hand_history_exploration.ipynb`** in Jupyter or VS Code. Set `EXPORT_DIR` to your Parquet folder (defaults to `../parquet_export` relative to the notebook if you run from `notebooks/`). The notebook demonstrates loading Parquet with pandas, simple time series of hand volume, action and street distributions, and a sample query on the wide table.

## Where the database lives

| Situation | Path |
|-----------|------|
| **Default** | **`./texas-holdem-gym.sqlite`** under the process **current working directory** (where you run `texas-holdem-gym`). |
| **Typical XDG-style location** (other installs) | `~/.local/share/TexasHoldemGym/Texas Hold'em Gym/texas-holdem-gym.sqlite` |
| **Override** | Set **`TEXAS_HOLDEM_GYM_SQLITE`** to an **absolute** path before starting the app or tests. |

The file may have **`…-shm`** and **`…-wal`** sidecars (**[WAL](https://www.sqlite.org/wal.html)**). Copy the **directory** or all three files for a consistent snapshot.

## Before you read: close the app or copy the file

With WAL enabled, readers can still see data, but writers hold locks. For reproducible exports:

1. **Quit the app**, or  
2. **Copy** the `.sqlite` file (and optionally `.sqlite-wal` + `.sqlite-shm`) to a read-only path and point your script at the copy.

If the app falls back to **QSettings** (INI) because the DB could not be opened, there is no relational `hands` / `actions` / `players` data—this guide assumes SQLite is in use.

## What is in the database

### Key–value settings (`kv`)

| Table | Purpose |
|-------|---------|
| **`kv`** | Rows `(k, v)` where **`k`** is a dotted key (e.g. `v1/smallBlind`, `v1/seat0/strategy`) and **`v`** is **JSON text**. |

### Hand log (`user_version = 1`)

#### `players`

| Column | Meaning |
|--------|---------|
| `id` | Surrogate primary key |
| `created_ms` | Epoch ms when first seen |
| `player_key` | Stable logical id (app uses `session_key * 64 + seat`) |

#### `hands`

| Column | Meaning |
|--------|---------|
| `id` | Hand id |
| `started_ms`, `ended_ms` | Wall-clock epoch ms |
| `session_key` | Session bucket for `player_key` |
| `button_seat`, `sb_seat`, `bb_seat` | Seat indices |
| `num_players` | Dealt-in count |
| `sb_size`, `bb_size` | Posted blind sizes (chips) |
| `board_c0` … `board_c4` | Board cards as integers `0..51` or **`-1`** if unused |
| `result_flags` | Bit mask of seats that gained chips vs start-of-hand |

#### `actions`

| Column | Meaning |
|--------|---------|
| `id` | Row id |
| `hand_id` | FK → `hands.id` |
| `seq` | Order within the hand |
| `player_id` | FK → `players.id` |
| `street` | `0` preflop … `4` showdown |
| `action_kind` | `0` fold, `1` check, `2` call, `3` bet, `4` raise, `5` all-in |
| `size_chips` | Chip amount where applicable |
| `facing_size` | Facing bet context (often `0` until fully logged) |
| `extra` | Flags; bit **0** ⇒ blind post |

#### Decoding `board_c*` (0–51)

Encoding matches `_card_tuple_to_wire_int` in `texasholdemgym.backend.sqlite_store`:

- **`rank_index = code // 4`** with ranks from two through ace.
- **`suit_index = code % 4`** with **0 = clubs, 1 = spades, 2 = hearts, 3 = diamonds**.

```python
RANKS = "23456789TJQKA"
SUITS = "♣♠♥♦"

def card_code_to_str(c: int):
    if c is None or c < 0 or c > 51:
        return None
    r, s = divmod(c, 4)
    return f"{RANKS[r]}{SUITS[s]}"
```

## Python environment (analysis)

For the bundled exporter and notebook, install the **`analysis`** extra (pandas, pyarrow, matplotlib):

```bash
pip install -e '.[analysis]'
```

Optional for ad‑hoc SQL: `pip install duckdb sqlalchemy`

## Option A — pandas + SQLAlchemy → Parquet

```python
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

DB = Path.cwd() / "texas-holdem-gym.sqlite"
# Or: DB = Path("/absolute/path/from/TEXAS_HOLDEM_GYM_SQLITE")

engine = create_engine(f"sqlite:///{DB.as_posix()}")

hands = pd.read_sql("SELECT * FROM hands ORDER BY started_ms", engine)
actions = pd.read_sql("SELECT * FROM actions ORDER BY hand_id, seq", engine)
players = pd.read_sql("SELECT * FROM players", engine)

out = Path("~/poker_export").expanduser()
out.mkdir(parents=True, exist_ok=True)
hands.to_parquet(out / "hands.parquet", index=False)
actions.to_parquet(out / "actions.parquet", index=False)
players.to_parquet(out / "players.parquet", index=False)
```

Joined frame (one row per action with hand metadata):

```python
sql = """
SELECT a.*, h.started_ms, h.ended_ms, h.sb_size, h.bb_size, h.button_seat,
       h.board_c0, h.board_c1, h.board_c2, h.board_c3, h.board_c4,
       p.player_key
FROM actions a
JOIN hands h ON h.id = a.hand_id
JOIN players p ON p.id = a.player_id
ORDER BY h.started_ms, a.seq
"""
actions_wide = pd.read_sql(sql, engine)
actions_wide.to_parquet(out / "actions_with_hands.parquet", index=False)
```

## Option B — DuckDB

```sql
INSTALL sqlite;
LOAD sqlite;

ATTACH 'path/to/texas-holdem-gym.sqlite' AS poker (TYPE sqlite);

COPY (SELECT * FROM poker.hands) TO 'hands.parquet' (FORMAT PARQUET);
COPY (SELECT * FROM poker.actions) TO 'actions.parquet' (FORMAT PARQUET);
COPY (SELECT * FROM poker.players) TO 'players.parquet' (FORMAT PARQUET);
```

Shell one-liner (current directory):

```bash
duckdb -c "ATTACH 'texas-holdem-gym.sqlite' AS poker (TYPE sqlite); COPY (SELECT * FROM poker.hands) TO 'hands.parquet' (FORMAT PARQUET);"
```

Example with a home-directory database (escape quotes in paths with spaces):

```bash
duckdb -c "ATTACH '/home/you/.local/share/TexasHoldemGym/Texas Hold''em Gym/texas-holdem-gym.sqlite' AS poker (TYPE sqlite); COPY (SELECT * FROM poker.hands) TO 'hands.parquet' (FORMAT PARQUET);"
```

## Option C — Polars

```python
from pathlib import Path

import polars as pl

db = Path.cwd() / "texas-holdem-gym.sqlite"
uri = f"sqlite:///{db.as_posix()}"
hands = pl.read_database_uri("SELECT * FROM hands", uri)
hands.write_parquet("hands.parquet")
```

If URI handling fails, use pandas `read_sql` then `pl.from_pandas`, or export via DuckDB then `pl.read_parquet`.

## Reading Parquet back

```python
import pandas as pd

hands = pd.read_parquet("hands.parquet")
```

Or in DuckDB: `SELECT count(*) FROM read_parquet('hands.parquet');`

## Settings (`kv`) as Parquet

```python
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

DB = Path.cwd() / "texas-holdem-gym.sqlite"
engine = create_engine(f"sqlite:///{DB.as_posix()}")
kv = pd.read_sql("SELECT k AS key, v AS json_text FROM kv", engine)

def try_parse(s):
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None

kv["value"] = kv["json_text"].map(try_parse)
kv.to_parquet("kv.parquet", index=False)
```

## Related code (Python)

| Area | Files |
|------|-------|
| Schema + inserts | `src/texasholdemgym/backend/sqlite_store.py` |
| Recording | `src/texasholdemgym/backend/poker_game.py` → `HandHistory.record_completed_hand` |
| QML API | `src/texasholdemgym/backend/hand_history.py` |
| Parquet export | `src/texasholdemgym/parquet_export.py`, CLI `texas-holdem-parquet-export` |

---

*If you add columns or tables, bump `PRAGMA user_version` in code and update this file in the same change.*
