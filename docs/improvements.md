# Improvements & technical notes

This document combines **test coverage gaps**, **UI and engine suggestions**, and **timer/HUD behavior** that affects how “stuck” the table can feel. Use it as the single backlog for quality work outside day-to-day bugfixes.

---

## Test coverage

All current tests pass (`pytest tests/ -v`). The following areas are **not** fully locked in by automated tests.

### Covered today

| Module | What it exercises |
|--------|-------------------|
| `tests/test_poker_engine_expectations.py` | Timer/HUD/recovery on `PokerGame` (delegates to `NlhHandEngine` for betting); no QML. |
| `tests/test_qml_integration.py` | Headless load of `qrc:/Main.qml`, `findChild(..., "game_screen")`, `setRootObject` + `actingSeat`/`pot` sync, attach-root after off-screen `beginNewHand`. |
| `tests/test_poker_game.py` | `PokerGame` setup, `GameScreen` buttons, `submitCheckOrBet`, `setRootObject`, `statsSeq` bumps, SQLite when DB attached. |
| `tests/test_nlh_table_engine.py` | `NlhHandEngine` on a real `PokerGame` (Qt app via `tests/conftest.py`). |
| `tests/test_game_state_persist.py` | SQLite KV round-trip for `save_table_client_to_db` / `load_table_client_from_db` / `clear_game_and_range_kv`. |
| `tests/test_session_stats.py` | `BankrollSessionStats` snapshots and ranking rows. |
| `tests/test_sqlite_store.py` | `AppDatabase` path, KV, relational `insert_hand_log` / hand list / detail. |
| `tests/test_training_trainer.py` | Trainer question payloads (SVG keys for QML). |
| `tests/test_backend_smoke.py` | `ToyNashSolver` / `PokerSolver` async signals, `SessionStore` without DB, `TrainingStore` defaults. |
| `tests/test_bot_strategy.py` | `bot_strategy` presets and probability helpers. |
| `tests/test_imports.py` | Package imports resolve. |

### Gaps (higher level)

| Area | Gap |
|------|-----|
| **HUD sync drift** | `_decision_seconds_displayed` in `test_poker_engine_expectations.py` mirrors HUD rules from `PokerGame` / `game_screen_sync`; could share a small pure helper. |
| **Human full hand** | No end-to-end with `interactiveHuman=True` and `submitFacingAction` / `buttonClicked` through the full hand in QML. |
| **`app.py` startup** | `_try_bind_game_screen` retry in `app.main` is not covered by a full `main()` integration test (QML smoke uses `qml` tests and manual runs). |
| **BB preflop option** | No dedicated test for `bb_preflop_waiting`, `submitBbPreflopRaise`, BB check timeout. |
| **Next-hand timer** | No test that `_next_hand_timer` fires and starts a second hand with QML bound. |
| **Side pots / showdown** | No assertions on multi-way side-pot chip counts vs a reference vector. |

---

## UI & QML suggestions

Non-binding ideas to improve clarity and parity with the engine. The Python port avoids unnecessary QML churn; treat these as **optional polish**.

### Auto hand loop

The engine persists `autoHandLoop` in game state KV and defaults it **on**. The slot **`pokerGame.setAutoHandLoop(bool)`** exists; QML does not bind it everywhere. Consider:

- A Setup checkbox **“Continuous play / next hand automatically”** wired to `pokerGame.setAutoHandLoop(checked)` (and optionally a `Qt.binding` if an `autoHandLoop` property with `NOTIFY` is added).
- Short help text describing automatic next-hand behavior after the showdown delay.

### Fewer than two players

The engine sets `statusText` when a deal cannot start (need at least two players). Optional QML polish:

- A **dismissible banner** on the table when `actingSeat < 0` and the status message explains that more players are needed.
- On **Bots and pricing**, when the last bot is disabled so only the human remains, a one-line note that the table cannot deal until another player is enabled.

### Setup: seat 0 vs bot toggles

Setup toggles **seats 1–5** only. The human seat is controlled by **Sit out** / **Play as bot** elsewhere. Consider a short caption: *“Seat 0 (You) is controlled with Sit out / Play as bot on the table or in Setup.”*

### `game_screen` binding timing

`app.py` binds `objectName: "game_screen"` after a short delay and retries `findChild`. If the stack ever **defers** `GameScreen` (e.g. `Loader` with `asynchronous: true`), binding can miss until the page exists.

- Prefer keeping **`GameScreen` as a direct `StackLayout` child** (current pattern), **or**
- Emit when the table page becomes `StackLayout.currentItem` and bind the engine root there (small bridge in `app.py`).

### Strategy names

`strategyDisplayNames()` returns the `bot_strategy.STRATEGY_NAMES` list (archetype labels). Wording in Setup can still note that heuristics are not full solver-grade bots.

### Timer / “Act” UI

`GameControls` ties some visibility to `humanStackChips` and `decisionSecondsLeft`. For stricter parity on **bot** turn countdown in the floating HUD, consider separate properties (hero-only vs table-wide actor clock) if product design calls for it.

When adding features, prefer **new properties** and **backward-compatible** defaults so existing SQLite KV rows still load.

---

## Why the table can look “stuck” after the timer

Hands appearing in **Hand history** means completed hands are persisted. A frozen table is usually a **live hand** that never completes, or a **UI/timer display** mismatch.

### 1. QML only shows the hero countdown (`decisionSecondsLeft`)

In `PokerGame._sync_root`, `decisionSecondsLeft` is pushed as:

- **Non-zero** only when the **hero** is acting (interactive, in hand, not sitting out) **or** during BB preflop wait.
- **Zero** on **bot turns**, even though the engine still runs an internal clock and `_tick_decision`.

So on bot turns the HUD can show **`decisionSecondsLeft === 0`** while the hand is still live (`_bot_timer` / `_auto_action_timeout` → `_bot_act()`).

**Relevant QML:** `GameControls.qml` — `humanDecisionActive` also requires `humanStackChips > 0`, so an **all-in hero** may get no action chrome even though timeouts still apply.

**Possible improvement:** separate “hero decision seconds” vs “current actor seconds,” or show the internal clock on the acting seat.

### 2. `_tick_decision` when `actingSeat === -1` with a live hand

If **`_acting_seat < 0`** while **`_in_progress`**, `_tick_decision` may not drive `_auto_action_timeout`. The engine mitigates this in `_begin_betting_round(-1)` by awarding, advancing the street, or assigning the next actor instead of leaving a stranded state.

### 3. Stale `acting_seat`

If **`acting_seat`** pointed at a seat not in `_in_hand`, `_bot_act` could no-op. **`_recover_stale_acting_seat()`** reassigns action or advances street/showdown.

### 4. Human timeout

When the hero’s clock hits 0, `_auto_action_timeout` folds (facing a bet) or checks. Detached QML root or broken `submitFacingAction` paths behave differently from DB persistence.

### 5. SQLite path vs “hands saved”

Default DB is **`./texas-holdem-gym.sqlite` (cwd)** unless **`TEXAS_HOLDEM_GYM_SQLITE`** is set. Running from different directories can point at different files. See **[data-and-sqlite.md](data-and-sqlite.md)**.

**Summary:** The usual **perceived** “timer expired then freeze” with hands still logging is **(1)** no hero countdown on bot turns plus **(2)** optional all-in / `humanStackChips` gating. Engine-side stalls **(2)/(3)** are addressed by recovery logic in `poker_game.py`.

---

## Related documentation

| Document | Contents |
|----------|----------|
| [data-and-sqlite.md](data-and-sqlite.md) | Database location, schema, exporting to Parquet for analysis |
| [README.md](../README.md) | Run from source, tests, layout |
