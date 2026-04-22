<p align="center">
  <img src="poker/qml/assets/images/logo.png" alt="Texas Hold’em Gym" width="420" />
</p>

# Texas Hold’em Gym ML

**Texas Hold’em Gym ML** is a desktop app built with **Qt 6 (QML / Qt Quick)**, running on **Qt for Python (PySide6)**.

The **QML UI** is the primary surface; the **Python backend** implements the poker engine, persistence, and Qt object bridges.

## What’s in the box

- **QML UI**: lobby, table screens, setup, solver, trainers, stats, hand history.
- **Python backend**: `PokerGame`, SQLite hand log, training stubs, QML context wiring.

## Repository layout

| Path | Role |
| --- | --- |
| `pyproject.toml` | Python packaging (PySide6 app) |
| `src/texasholdemgym/` | App entrypoint + Qt/QML backend |
| `poker/qml/` | QML UI, assets, and `application.qrc` |

## Run (from source)

Prerequisites:

- Python 3.10+
- Qt 6 with `rcc` on `PATH`, **or** set `QT_RCC=/path/to/rcc` (PySide6 often ships one under `.../PySide6/Qt/libexec/rcc`)

From the repo root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .

texas-holdem-gym
```

### Saved configuration

Game settings, bankroll, ranges, and related JSON live in the SQLite **`kv`** table. By default the app uses **`./texas-holdem-gym.sqlite`** in the **process current working directory**. Set **`TEXAS_HOLDEM_GYM_SQLITE`** to an absolute path to use another file. Completed hands use relational tables **`hands`**, **`actions`**, **`players`** with **`PRAGMA user_version = 1`**.

## Documentation

See **[`docs/README.md`](docs/README.md)** for the index. Main entries:

- **[`docs/improvements.md`](docs/improvements.md)** — test gaps, UI suggestions, timer/HUD behavior, backlog  
- **[`docs/data-and-sqlite.md`](docs/data-and-sqlite.md)** — database location, schema, **`texas-holdem-parquet-export`**, Parquet layout  
- **[`notebooks/hand_history_exploration.ipynb`](notebooks/hand_history_exploration.ipynb)** — example exploration on exported data (`pip install -e '.[analysis]'`)

## Tests

```bash
pip install -e .              # pytest + Coverage.py (`coverage[toml]`, see `pyproject.toml`)
pip install -e '.[test]'      # pandas / pyarrow for Parquet + export tests
```

**`pytest` alone** does not pass **`--cov`** (so it never errors if an older env lacks plugins). For **line + branch** coverage, a **terminal report** (missing lines, `--skip-covered`), and **`fail_under` 80%** from **`pyproject.toml`**, run the packaged helper (from the repo root, or anywhere if `pyproject.toml` + `src/texasholdemgym` are discoverable):

```bash
texas-holdem-gym-test              # same as: coverage run -m pytest -q && coverage report -m --skip-covered
texas-holdem-gym-test --html       # also writes htmlcov/
texas-holdem-gym-test tests/test_foo.py   # optional pytest path / kwargs
```

Equivalent manual invocation from the repository root:

```bash
coverage run -m pytest -q
coverage report -m --skip-covered
```

Quick test runs without coverage:

```bash
pytest -q
pytest -q tests/test_foo.py
```

**What the 80% gate measures:** everything under `src/texasholdemgym/` **except** modules that are mostly integration glue or optional CLIs (see `[tool.coverage.run] omit` in `pyproject.toml`): **`app.py`** (GUI entry), **`backend/poker_game.py`** (large Qt/QML bridge), **`parquet_export.py`** (optional Parquet CLI, also covered by `tests/test_parquet_export.py` when pandas/pyarrow are installed). Adjust `omit` or add tests if you intentionally expand scope.

Optional dead-code scan (requires `pip install -e '.[dev]'`):

```bash
vulture src/texasholdemgym --min-confidence 80
```

CI runs **Ruff** (pyflakes), **byte-compile**, **`texas-holdem-gym-test`** (coverage + report + gate), and **`python -m build`** — see [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Development tools

```bash
pip install -e '.[dev,test]'
ruff check src tests
```

### Export hand history to Parquet (analysis)

```bash
pip install -e '.[analysis]'
texas-holdem-parquet-export -o ./parquet_export
```

See **[`docs/data-and-sqlite.md`](docs/data-and-sqlite.md)** for options and the exploration notebook.
