"""Bridges QML to the NLHE backend: `Table` + `LiveHandState` + `NlhHandEngine`, with SQLite for hand logs & KV state."""

from __future__ import annotations

import random
import time
from typing import Any

from PySide6 import QtCore

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.game_screen_sync import sync_game_screen_properties
from texasholdemgym.backend.game_table import Player, StrategyTuning, Table
from texasholdemgym.backend.hand_accounting import HandAccounting
from texasholdemgym.backend.live_hand import LiveHandState
from texasholdemgym.backend.range_manager import RangeManager
from texasholdemgym.backend.street_bet_controller import StreetBetController
from texasholdemgym.backend.table_bot import BotDecision, TableRulesBot
from texasholdemgym.backend import range_notation
from texasholdemgym.backend.hand_history import HandHistory
from texasholdemgym.backend.hand_log_payload import build_hand_log_record
from texasholdemgym.backend.poker_core.cards import new_shuffled_deck
from texasholdemgym.backend.poker_core.hole_grid import hole_to_range_grid_row_col
from texasholdemgym.backend.poker_core.raise_rules import min_raise_increment_chips
from texasholdemgym.backend.poker_core.hand_evaluation import StandardHandEvaluator
from texasholdemgym.backend.game_state_persist import clear_game_and_range_kv, load_table_client_from_db, save_table_client_to_db
from texasholdemgym.backend.nlh_table_engine import NlhHandEngine
from texasholdemgym.backend.session_stats import BankrollSessionStats
from texasholdemgym.backend.sqlite_store import AppDatabase

try:
    from PySide6 import shiboken6  # type: ignore
except ImportError:  # pragma: no cover
    shiboken6 = None  # type: ignore

try:
    from PySide6.QtQml import QQmlProperty
except ImportError:  # pragma: no cover
    QQmlProperty = None  # type: ignore


class PokerGame(QtCore.QObject):
    """Runtime shell for the table UI (QML) and hand lifecycle.

    * **Model:** :class:`~texasholdemgym.backend.game_table.Table` (roster, chips, blinds) and
      :class:`~texasholdemgym.backend.live_hand.LiveHandState` (current deal).
    * **Play:** :class:`~texasholdemgym.backend.nlh_table_engine.NlhHandEngine` mutates the table; this class wires timers, QML sync, and `HandHistory` / SQLite KV.
    """

    HUMAN_HERO_SEAT = int(Table.HERO_SEAT)
    # QML `submitFacingAction(action, amount)` (see `GameScreen` / `submitFacingAction`).
    _FACING_FOLD = 0
    _FACING_CALL = 1
    # action > 1 or raise with amount: treated as a raise-to (chips to add, or 0 = min-raise sizing).

    # `GameScreen.buttonClicked` string ids (shared with `setRootObject` + tests).
    _GAME_SCREEN_BTN_MORE_TIME = "MORE_TIME"
    _GAME_SCREEN_BTN_FOLD = "FOLD"
    _GAME_SCREEN_BTN_CALL = "CALL"
    _GAME_SCREEN_BTN_CHECK = "CHECK"

    interactiveHumanChanged = QtCore.Signal()
    statsSeqChanged = QtCore.Signal()
    botSlowActionsChanged = QtCore.Signal()
    winningHandShowMsChanged = QtCore.Signal()
    botDecisionDelaySecChanged = QtCore.Signal()
    rangeRevisionChanged = QtCore.Signal()
    sessionStatsChanged = QtCore.Signal()
    pot_changed = QtCore.Signal()

    def __init__(self, db: AppDatabase | None = None, hand_history: HandHistory | None = None) -> None:
        super().__init__()
        # --- Persistence & optional hand log ---
        self._db = db
        self._hand_history = hand_history
        # --- QML `GameScreen` root (null when the view is not shown; object may be destroyed) ---
        self._root_obj: QtCore.QObject | None = None
        self._rng = random.Random()
        # --- Setup / display preferences (some persisted in KV) ---
        self._interactive_human = True
        self._bot_slow_actions = True
        self._winning_hand_show_ms = 2500
        self._bot_decision_delay_sec = 2
        self._stats_seq = 0
        # --- Roster, stacks, bankrolls, bot tuning (`Table`) ---
        self._table = Table.default_six_max()
        # --- Current hand: board, holes, button / blinds (`LiveHandState`) ---
        self._live = LiveHandState()
        self._decision_seconds_left = 0
        # --- Timers: 1 Hz decision clock; delayed bot; auto next hand after showdown ---
        self._decision_timer = QtCore.QTimer(self)
        self._decision_timer.setInterval(1000)
        self._bot_timer = QtCore.QTimer(self)
        self._bot_timer.setSingleShot(True)
        self._human_sitting_out = False
        self._human_more_time_available = False
        self._auto_hand_loop = True
        self._next_hand_timer = QtCore.QTimer(self)
        self._next_hand_timer.setSingleShot(True)
        # --- Per-street pot / actions; drives `StreetBetController` ---
        self._hand_accounting = HandAccounting()
        self._street = StreetBetController(
            self._table,
            self._live,
            self._hand_accounting,
            after_chips_sync=self._sync_root,
        )
        self._ranges = RangeManager()
        self._seat_bot = TableRulesBot()
        # In-memory only: charts + leaderboard baselines.
        self._session_stats = BankrollSessionStats()
        # Re-entrancy guard for `sync_game_screen_properties` (avoid nested event-loop pumps).
        self._sync_root_depth: int = 0
        self._hand_evaluator = StandardHandEvaluator()

        for s in range(6):
            self._apply_strategy_preset(s)
        self._engine = NlhHandEngine(self)
        self._decision_timer.timeout.connect(self._engine.tick_decision)
        self._bot_timer.timeout.connect(self._engine.bot_act)
        self._next_hand_timer.timeout.connect(self._engine.run_next_hand_timer_fire)
        self._refresh_session_stats_baseline()

    def _player(self, seat: int) -> Player:
        return self._table.players[int(seat) % 6]

    def _emit_stats_seq_and_session(self) -> None:
        """Increment `statsSeq` and emit `sessionStatsChanged` (bankroll / setup charts in QML)."""
        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()

    def _refresh_session_stats_baseline(self) -> None:
        self._session_stats.refresh_baseline(self._table)

    def _apply_strategy_ranges_from_preset(self, seat: int) -> None:
        """Load default preflop range text + grids for the seat's archetype (`STRATEGY_RANGE_PRESETS`)."""
        if not (0 <= seat < 6):
            return
        self._ranges.load_preset_for_archetype(seat, self._player(seat).strategy.archetype_index)

    def _apply_strategy_preset(self, seat: int) -> None:
        if 0 <= seat < 6:
            self._player(seat).strategy.reload_params_from_archetype()
        self._apply_strategy_ranges_from_preset(seat)

    def _disconnect_game_screen_button(self, obj: QtCore.QObject | None) -> None:
        """Drop `GameScreen.buttonClicked` → `_on_game_screen_button` before replacing the root."""
        if obj is None:
            return
        sig = getattr(obj, "buttonClicked", None)
        if sig is None:
            return
        try:
            sig.disconnect(self._on_game_screen_button)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _unbind_from_game_screen(self, obj: QtCore.QObject | None) -> None:
        """Remove signals from a `game_screen` `QObject` (button + destroyed). Safe if partially connected."""
        if obj is None:
            return
        self._disconnect_game_screen_button(obj)
        try:
            obj.destroyed.disconnect(self._on_root_destroyed)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _connect_to_game_screen(self, obj: QtCore.QObject) -> None:
        """Attach `destroyed` and `buttonClicked` on a new `GameScreen` instance."""
        try:
            obj.destroyed.connect(self._on_root_destroyed)  # type: ignore[attr-defined]
        except Exception:
            pass
        sig = getattr(obj, "buttonClicked", None)
        if sig is not None:
            try:
                sig.connect(self._on_game_screen_button)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _new_shuffled_deck(self) -> list[tuple[int, int]]:
        return new_shuffled_deck(self._rng)

    # --- QML sync ---
    @staticmethod
    def _qobject_alive(obj: QtCore.QObject | None) -> bool:
        if obj is None:
            return False
        if shiboken6 is None:
            return True
        try:
            return bool(shiboken6.isValid(obj))  # type: ignore[attr-defined]
        except Exception:
            return True

    def _root(self) -> QtCore.QObject | None:
        if self._root_obj is None:
            return None
        if not self._qobject_alive(self._root_obj):
            self._on_root_destroyed()
            return None
        return self._root_obj

    def _on_root_destroyed(self) -> None:
        # Drop the QML root only — keep the engine timers running so bots/hands advance off-screen.
        self._root_obj = None

    def _set_root(self, name: str, value: Any) -> None:
        root = self._root()
        if root is None:
            return
        # Prefer QQmlProperty for QML-declared props (more reliable binding updates than raw setProperty).
        if QQmlProperty is not None:
            try:
                qp = QQmlProperty(root, name)
                if qp.isValid() and qp.write(value):
                    return
            except Exception:
                pass
        try:
            root.setProperty(name, value)
        except RuntimeError:
            # Only drop the root when the QML object is actually gone — a bad value must not detach the UI forever.
            if self._root_obj is not None and not self._qobject_alive(self._root_obj):
                self._on_root_destroyed()

    def _count_eligible_for_deal(self) -> int:
        """Count seats eligible for the next deal (idle path; no pending wallet flush)."""
        return self._engine.count_eligible_for_deal()

    def _bootstrap_playable_table(self) -> None:
        self._engine.bootstrap_playable_table()

    def _maybe_begin_hand_after_setup_change(self) -> None:
        self._engine.maybe_begin_hand_after_setup_change()

    def _deferred_begin_new_hand_if_enough_seated(self) -> None:
        """If idle and ≥2 players can be dealt in, `beginNewHand` on the next event-loop tick (avoids re-entrancy)."""
        if not self._live.in_progress and self._count_eligible_for_deal() >= 2:
            QtCore.QTimer.singleShot(0, self._maybe_begin_hand_after_setup_change)

    def _effective_seat_buy_in_chips(self, seat: int) -> int:
        return self._engine.effective_seat_buy_in_chips(seat)

    def _sync_root(self) -> None:
        if self._root() is None:
            return
        self._sync_root_depth += 1
        try:
            self._sync_root_inner()
        finally:
            self._sync_root_depth -= 1

    def _sync_root_inner(self) -> None:
        sync_game_screen_properties(
            self,
            self._root(),
            self._set_root,
            sync_depth=int(self._sync_root_depth),
        )

    def _status_line(self) -> str:
        return Table.format_hud_status_line(
            int(self._live.street),
            int(self._hand_accounting.total_contrib_chips()),
            int(self._live.acting_seat),
            showdown=bool(self._live.showdown),
            showdown_status_text=self._live.showdown_status_text,
            bb_preflop_waiting=bool(self._live.bb_preflop_waiting),
            interactive_human=bool(self._interactive_human),
            hero_seat=int(self.HUMAN_HERO_SEAT),
            bot_names=Table.DEFAULT_BOT_NAMES,
        )

    def _human_hand_line_for_ui(self) -> str:
        hs = int(self.HUMAN_HERO_SEAT)
        h0, h1 = self._live.holes[hs]
        return Table.format_hero_hole_hud_text(
            h0,
            h1,
            hero_in_hand=bool(self._live.in_hand[hs]),
            human_sitting_out=bool(self._human_sitting_out),
        )

    # --- `NlhHandEngine` (single source of street / betting / showdown logic) ---
    # The methods below are thin forwards so tests, timers, and this class can call a stable name.
    def _betting_round_fully_resolved(self) -> bool:
        """True when this street's betting is complete (including a full check-down). Kept for tests / harness."""
        return self._engine.betting_round_fully_resolved()

    def _begin_betting_round(self, first: int, *, fresh_street: bool = True) -> None:
        self._engine.begin_betting_round(first, fresh_street=fresh_street)

    def _all_called_or_folded(self) -> bool:
        """Test hook; delegates to ``NlhHandEngine.all_called_or_folded``."""
        return self._engine.all_called_or_folded()

    def _record_completed_hand(
        self,
        winners: list[int],
        pot_awards: list[int] | None = None,
        *,
        winning_hand_name: str = "",
    ) -> None:
        if self._hand_history is None:
            # No relational log; still persist table + flags so a later launch sees stacks & setup.
            self._save_game_state_kv()
            return
        ended = int(time.time() * 1000)
        payload = build_hand_log_record(
            ended_ms=ended,
            table=self._table,
            live=self._live,
            accounting=self._hand_accounting,
            player=self._player,
            pot_awards=pot_awards,
            winners=winners,
            winning_hand_name=winning_hand_name,
        )
        self._hand_history.record_completed_hand(payload)
        self._session_stats.record_hand_ended(ended, self._table, self._player)
        self._save_game_state_kv()

    def _advance_street_or_showdown(self) -> None:
        self._engine.advance_street_or_showdown()

    def _award_uncontested(self, winner: int) -> None:
        self._engine.award_uncontested(winner)

    def _do_showdown(self) -> None:
        self._engine.do_showdown()

    def _maybe_schedule_bot(self) -> None:
        self._engine.maybe_schedule_bot()

    def _recover_stale_acting_seat(self) -> None:
        self._engine.recover_stale_acting_seat()

    def _apply_bot_decision(self, seat: int, decision: BotDecision) -> None:
        self._engine.apply_bot_decision(seat, decision)

    def _bot_act(self) -> None:
        self._engine.bot_act()

    def _fold(self, seat: int) -> None:
        self._engine.fold(seat)

    def _check(self, seat: int) -> None:
        self._engine.check(seat)

    def _call(self, seat: int) -> None:
        self._engine.call(seat)

    def _raise_to(self, seat: int, to_amount: int) -> None:
        self._engine.raise_to(seat, to_amount)

    def _advance_after_action(self) -> None:
        self._engine.advance_after_action()

    def _maybe_handle_bb_preflop_option(self) -> bool:
        return self._engine.maybe_handle_bb_preflop_option()

    def _finish_bb_preflop_check(self) -> None:
        self._engine.finish_bb_preflop_check()

    def _bb_preflop_add_raise(self, chips_to_add: int) -> None:
        self._engine.bb_preflop_add_raise(chips_to_add)

    def _tick_decision(self) -> None:
        self._engine.tick_decision()

    def _auto_action_timeout(self) -> None:
        self._engine.auto_action_timeout()

    # --- QML: `QtCore.Property` (exposed to bindings) ---

    @QtCore.Property(bool, notify=interactiveHumanChanged)
    def interactiveHuman(self) -> bool:
        return bool(self._interactive_human)

    @QtCore.Property(bool, notify=botSlowActionsChanged)
    def botSlowActions(self) -> bool:
        return bool(self._bot_slow_actions)

    @QtCore.Property(int, notify=winningHandShowMsChanged)
    def winningHandShowMs(self) -> int:
        return int(self._winning_hand_show_ms)

    @QtCore.Property(int, notify=botDecisionDelaySecChanged)
    def botDecisionDelaySec(self) -> int:
        return int(self._bot_decision_delay_sec)

    @QtCore.Property(int, notify=statsSeqChanged)
    def statsSeq(self) -> int:
        return int(self._stats_seq)

    @QtCore.Property(int, notify=rangeRevisionChanged)
    def rangeRevision(self) -> int:
        return int(self._ranges.revision)

    # --- QML: public `Slot`s (use `QObject` for the game screen; `object` is not supported from QML) ---

    @QtCore.Slot(QtCore.QObject)
    def setRootObject(self, obj: QtCore.QObject | None) -> None:
        """Bind to the QML `game_screen` item, or `None` when the view is torn down."""
        if obj is None:
            self._unbind_from_game_screen(self._root_obj)
            self._root_obj = None
            return

        prev = self._root_obj
        if prev is obj:
            self._sync_root()
            return
        if prev is not None:
            self._unbind_from_game_screen(prev)

        self._root_obj = obj
        self._connect_to_game_screen(obj)
        # If a hand already started, push engine state to QML; otherwise `beginNewHand` can no-op
        # while `_live.in_progress` and root is missing.
        self._sync_root()

    @QtCore.Slot(str)
    def _on_game_screen_button(self, button: str) -> None:
        """QML `GameScreen.buttonClicked` — same routing as the app shell used to do in `app.py`."""
        b = str(button)
        if b == self._GAME_SCREEN_BTN_MORE_TIME:
            self.requestMoreTime()
            return
        if b == self._GAME_SCREEN_BTN_FOLD:
            self.submitFacingAction(self._FACING_FOLD, 0)
        elif b == self._GAME_SCREEN_BTN_CALL:
            self.submitFacingAction(self._FACING_CALL, 0)
        elif b == self._GAME_SCREEN_BTN_CHECK:
            self.submitCheckOrBet(True, 0)

    @QtCore.Slot()
    def beginNewHand(self) -> None:
        self._engine.begin_new_hand()

    @staticmethod
    def _hole_to_grid_row_col(h0: tuple[int, int], h1: tuple[int, int]) -> tuple[int, int]:
        """Map two hole cards to 13×13 range-grid indices; see `poker_core.hole_grid` (tests / editor)."""
        return hole_to_range_grid_row_col(h0, h1)

    def _save_game_state_kv(self) -> None:
        if self._db is None:
            return
        save_table_client_to_db(self._db, self)

    def _persist_ranges(self) -> None:
        if self._db is not None:
            self._ranges.save_persisted(self._db)

    # --- Setup / SQLite: table client state + per-seat range bundle (see `game_state_persist`) ---

    @QtCore.Slot()
    def loadPersistedSettings(self) -> None:
        if self._db is None:
            return
        if not load_table_client_from_db(self._db, self):
            return
        self._ranges.load_persisted(self._db)
        for s in range(6):
            self._player(s).strategy.reload_params_from_archetype()
        self._bootstrap_playable_table()
        self._refresh_session_stats_baseline()
        self.rangeRevisionChanged.emit()
        self._emit_stats_seq_and_session()

    @QtCore.Slot()
    def savePersistedSettings(self) -> None:
        self._save_game_state_kv()
        self._persist_ranges()

    @QtCore.Slot(result="QVariantList")
    def strategyDisplayNames(self):
        return list(bot_strategy.STRATEGY_NAMES)

    @QtCore.Slot(int, result="QVariantMap")
    def seatStrategyParams(self, seat: int):
        seat = int(seat)
        p = self._player(seat).strategy.tuning if 0 <= seat < 6 else StrategyTuning()
        return p.__dict__.copy()

    @QtCore.Slot(int, "QVariantMap")
    def setSeatStrategyParams(self, seat: int, m: dict):
        seat = int(seat)
        if not (0 <= seat < 6) or not m:
            return
        p = self._player(seat).strategy.tuning
        for k, v in dict(m).items():
            if hasattr(p, k):
                setattr(p, k, v)
        self._save_game_state_kv()

    @QtCore.Slot(result=bool)
    def gameInProgress(self) -> bool:
        return bool(self._live.in_progress)

    @QtCore.Slot()
    def applySeatBuyInsToStacks(self) -> None:
        cap = int(self._table.buy_in_cap_chips())
        for s in range(6):
            self._player(s).reconcile_stack_with_table_cap(cap)

        self._emit_stats_seq_and_session()
        self._save_game_state_kv()
        self._sync_root()
        self._deferred_begin_new_hand_if_enough_seated()

    @QtCore.Slot(int, str, int, result=bool)
    def applySeatRangeText(self, seat: int, text: str, layer: int) -> bool:
        seat = int(seat)
        layer = int(layer)
        if not (0 <= seat < 6 and 0 <= layer < 3):
            return False
        t = str(text)
        if len(t) > 200000:
            return False
        try:
            g = range_notation.parse_range_to_grid(t)
        except ValueError:
            return False
        self._ranges.apply_parsed_grid(seat, layer, g)
        self._persist_ranges()
        self.rangeRevisionChanged.emit()
        return True

    @QtCore.Slot(int, int, result=str)
    def exportSeatRangeText(self, seat: int, layer: int) -> str:
        seat = int(seat)
        layer = int(layer)
        if not (0 <= seat < 6 and 0 <= layer < 3):
            return ""
        return self._ranges.export_formatted_text(seat, layer)

    @QtCore.Slot(int, result=int)
    def seatStrategyIndex(self, seat: int) -> int:
        seat = int(seat)
        return int(self._player(seat).strategy.archetype_index) if 0 <= seat < 6 else 0

    @QtCore.Slot()
    def factoryResetToDefaultsAndClearHistory(self) -> None:
        """Wipe hand DB, KV, ranges, and table state to a fresh install (QML `Factory reset`)."""
        if self._hand_history is not None:
            self._hand_history.clearAll()
        if self._db is not None:
            clear_game_and_range_kv(self._db)
        self._ranges.clear()
        self._table.reset_like_new_install()
        self._interactive_human = True
        self._human_sitting_out = False
        self._bot_slow_actions = True
        self._winning_hand_show_ms = 2500
        self._bot_decision_delay_sec = 2
        self._live.button_seat = 0
        for s in range(6):
            self._apply_strategy_preset(s)
        self._ranges.touch()
        self.rangeRevisionChanged.emit()
        self._auto_hand_loop = True
        self._hand_accounting.begin_action_log(0)
        self.interactiveHumanChanged.emit()
        self.botSlowActionsChanged.emit()
        self.winningHandShowMsChanged.emit()
        self.botDecisionDelaySecChanged.emit()
        self._emit_stats_seq_and_session()
        self._hand_accounting.clear_for_new_hand()
        self._sync_root()

    # --- Blinds / caps (Setup screen) ---

    @QtCore.Slot(result=int)
    def configuredSmallBlind(self) -> int:
        return int(self._table.small_blind)

    @QtCore.Slot(result=int)
    def configuredBigBlind(self) -> int:
        return int(self._table.big_blind)

    @QtCore.Slot(result=int)
    def configuredStreetBet(self) -> int:
        return int(self._table.street_bet)

    @QtCore.Slot(result=int)
    def configuredMaxOnTableBb(self) -> int:
        return int(self._table.max_on_table_bb)

    @QtCore.Slot(result=int)
    def configuredStartStack(self) -> int:
        return int(self._table.start_stack)

    @QtCore.Slot(result=int)
    def maxBuyInChips(self) -> int:
        return int(self._table.max_buy_in_chips())

    @QtCore.Slot(int, result=bool)
    def canBuyBackIn(self, seat: int) -> bool:
        seat = int(seat)
        hs = int(self.HUMAN_HERO_SEAT)
        if seat != hs or not self._interactive_human:
            return False
        if self._live.in_progress:
            return False
        if self._player(hs).stack_on_table > 0:
            return False
        cap = int(self._table.buy_in_cap_chips())
        need = int(self._effective_seat_buy_in_chips(hs))
        return bool(cap > 0 and int(self._player(hs).bankroll_off_table) >= need)

    @QtCore.Slot(int, result=bool)
    def seatParticipating(self, seat: int) -> bool:
        seat = int(seat)
        return bool(self._player(seat).participating) if 0 <= seat < 6 else False

    @QtCore.Slot(int, bool)
    def setSeatParticipating(self, seat: int, on: bool) -> None:
        seat = int(seat)
        # Only mutates bot seats 1..5 (human seat is not toggled here).
        if not (1 <= seat < 6):
            return
        prev = bool(self._player(seat).participating)
        self._player(seat).participating = bool(on)
        self._save_game_state_kv()
        if on and not prev:
            self._deferred_begin_new_hand_if_enough_seated()
        self._sync_root()

    @QtCore.Slot(int)
    def setMaxOnTableBb(self, bb: int) -> None:
        self._table.max_on_table_bb = int(bb)
        self._save_game_state_kv()

    @QtCore.Slot(int, int, int, int)
    def configure(self, sb: int, bb: int, street_bet: int, start_stack: int) -> None:
        self._table.small_blind = int(sb)
        self._table.big_blind = int(bb)
        self._table.street_bet = int(street_bet)
        self._table.start_stack = int(start_stack)
        self._save_game_state_kv()

    @QtCore.Slot(int)
    def setWinningHandShowMs(self, ms: int) -> None:
        v = int(ms)
        if v != self._winning_hand_show_ms:
            self._winning_hand_show_ms = v
            self.winningHandShowMsChanged.emit()
            self._save_game_state_kv()

    @QtCore.Slot(bool)
    def setBotSlowActions(self, on: bool) -> None:
        v = bool(on)
        if v != self._bot_slow_actions:
            self._bot_slow_actions = v
            self.botSlowActionsChanged.emit()
            self._save_game_state_kv()

    @QtCore.Slot(int)
    def setBotDecisionDelaySec(self, sec: int) -> None:
        v = int(sec)
        if v != self._bot_decision_delay_sec:
            self._bot_decision_delay_sec = v
            self.botDecisionDelaySecChanged.emit()
            self._save_game_state_kv()
            self._sync_root()

    @QtCore.Slot(bool)
    def setAutoHandLoop(self, on: bool) -> None:
        v = bool(on)
        if v != self._auto_hand_loop:
            self._auto_hand_loop = v
            self._save_game_state_kv()

    @QtCore.Slot(int, result=int)
    def seatBankrollTotal(self, seat: int) -> int:
        seat = int(seat)
        return int(self._player(seat).bankroll_off_table + self._player(seat).stack_on_table) if 0 <= seat < 6 else 0

    @QtCore.Slot(int, int)
    def setSeatBankrollTotal(self, seat: int, v: int) -> None:
        seat = int(seat)
        if 0 <= seat < 6:
            total = max(0, int(v))
            on_table = max(0, int(self._player(seat).stack_on_table))
            self._player(seat).bankroll_off_table = max(0, total - on_table)
            self._emit_stats_seq_and_session()
            self._save_game_state_kv()

    @QtCore.Slot(int, result=int)
    def seatBuyIn(self, seat: int) -> int:
        seat = int(seat)
        return int(self._player(seat).stack_on_table) if 0 <= seat < 6 else 0

    @QtCore.Slot(int, int)
    def setSeatBuyIn(self, seat: int, v: int) -> None:
        seat = int(seat)
        if 0 <= seat < 6:
            self._player(seat).set_stack_with_total_preservation(int(v), cap=int(self._table.buy_in_cap_chips()))
            self._emit_stats_seq_and_session()
            self._save_game_state_kv()
            self._sync_root()

    @QtCore.Slot(int, int)
    def setSeatStrategy(self, seat: int, idx: int) -> None:
        seat = int(seat)
        if 0 <= seat < 6:
            self._player(seat).strategy.archetype_index = min(
                bot_strategy.STRATEGY_COUNT - 1, max(0, int(idx))
            )
            self._apply_strategy_preset(seat)
            self._save_game_state_kv()
            self._persist_ranges()
            self._sync_root()
            self._ranges.touch()
            self.rangeRevisionChanged.emit()

    @QtCore.Slot(int, result=str)
    def getStrategySummary(self, idx: int) -> str:
        return bot_strategy.strategy_summary(int(idx))

    @QtCore.Slot(int, result=str)
    def seatPositionLabel(self, seat: int) -> str:
        """BTN / SB / BB / UTG / HJ / CO — delegates to ``Table.seat_position_label``."""
        return Table.seat_position_label(
            int(seat),
            button_seat=int(self._live.button_seat),
            sb_seat=int(self._live.sb_seat),
            bb_seat=int(self._live.bb_seat),
            participating=self._table.participating_list(),
        )

    @QtCore.Slot(bool)
    def setInteractiveHuman(self, on: bool) -> None:
        v = bool(on)
        if v != self._interactive_human:
            self._interactive_human = v
            if not v:
                self._human_sitting_out = False
            self.interactiveHumanChanged.emit()
            self._save_game_state_kv()
            self._sync_root()

    @QtCore.Slot(int)
    def resetSeatRangeFull(self, seat: int) -> None:
        seat = int(seat)
        if not (0 <= seat < 6):
            return
        self._ranges.reset_seat_full_range(seat)
        self._persist_ranges()
        self.rangeRevisionChanged.emit()

    @QtCore.Slot(int, int, result="QVariantList")
    def getRangeGrid(self, seat: int, layer: int):
        seat = int(seat)
        layer = int(layer)
        if not (0 <= seat < 6 and 0 <= layer < 3):
            return [0.0] * (13 * 13)
        return list(self._ranges.ensure_grid(seat, layer))

    @QtCore.Slot(int, int, int, float, int)
    def setRangeCell(self, seat: int, row: int, col: int, w: float, layer: int) -> None:
        seat = int(seat)
        layer = int(layer)
        row = int(row)
        col = int(col)
        if not (0 <= seat < 6 and 0 <= layer < 3 and 0 <= row < 13 and 0 <= col < 13):
            return
        self._ranges.set_cell_weight(seat, layer, row, col, w)
        self._persist_ranges()
        self.rangeRevisionChanged.emit()

    # --- In-memory session stats (bankroll / stacks over time; not in SQLite) ---

    @QtCore.Slot(result="QVariantList")
    def seatRankings(self):
        return self._session_stats.seat_ranking_rows(self._table)

    @QtCore.Slot(result="QVariantList")
    def bankrollSnapshotTimesMs(self):
        return [int(x) for x in self._session_stats.snapshot_times_ms]

    @QtCore.Slot(result=int)
    def bankrollSnapshotCount(self) -> int:
        return int(len(self._session_stats.snapshot_times_ms))

    @QtCore.Slot(int, result="QVariantList")
    def tableStackSeries(self, seat: int):
        seat = int(seat)
        if not (0 <= seat < 6):
            return []
        return [int(snap[seat]) for snap in self._session_stats.snapshot_table_stacks]

    @QtCore.Slot(int, result="QVariantList")
    def bankrollSeries(self, seat: int):
        seat = int(seat)
        if not (0 <= seat < 6):
            return []
        return [int(snap[seat]) for snap in self._session_stats.snapshot_totals]

    @QtCore.Slot()
    def resetBankrollSession(self) -> None:
        self._session_stats.reset()
        self._refresh_session_stats_baseline()
        self._emit_stats_seq_and_session()

    # --- Hero: facing bet, donk, BB option (slots call into `NlhHandEngine` above) ---

    @QtCore.Slot(int)
    def submitBbPreflopRaise(self, amount: int) -> None:
        if not self._live.bb_preflop_waiting:
            return
        self._bb_preflop_add_raise(int(amount))

    @QtCore.Slot(int, int)
    def submitFacingAction(self, action: int, amount: int) -> None:
        """Hero in-position: ``action`` is ``_FACING_FOLD`` / ``_FACING_CALL`` / else raise (``amount`` = extra chips, 0 = min-raise)."""
        if self._live.bb_preflop_waiting:
            return
        hs = int(self.HUMAN_HERO_SEAT)
        if self._live.acting_seat != hs:
            return
        act = int(action)
        if act == self._FACING_FOLD:
            self._human_more_time_available = False
            self._fold(hs)
        elif act == self._FACING_CALL:
            self._human_more_time_available = False
            self._call(hs)
        else:
            need = self._hand_accounting.chips_needed_to_call(hs)
            inc = min_raise_increment_chips(self._table.big_blind, self._hand_accounting.last_raise_increment)
            stack0 = int(self._player(hs).stack_on_table)
            chips = int(amount)
            if chips <= 0:
                chips = int(need + inc)
            chips = min(chips, stack0)
            target = int(self._hand_accounting.street_put_in_at(hs) + chips)
            self._human_more_time_available = False
            self._raise_to(hs, target)

    @QtCore.Slot(bool, int)
    def submitCheckOrBet(self, check: bool, amount: int) -> None:
        """``check=True`` → check (or call if there is a bet to match); ``check=False`` → open/raise (amount = chip size from UI)."""
        if self._live.bb_preflop_waiting:
            if bool(check):
                self._finish_bb_preflop_check()
            return
        hs = int(self.HUMAN_HERO_SEAT)
        if self._live.acting_seat != hs:
            return
        if not bool(check):
            stack0 = int(self._player(hs).stack_on_table)
            sb_open = int(self._table.street_bet)
            min_open = sb_open if stack0 >= sb_open else max(1, stack0)
            chips = int(max(min_open, min(int(amount), stack0)))
            self._street.apply_contribution(hs, chips, label="Raise")
            self._hand_accounting.bump_to_call_with_seat_street(hs)
            self._hand_accounting.last_raise_increment = int(chips)
            if self._live.street == 0 and self._hand_accounting.to_call > self._hand_accounting.preflop_blind_level:
                self._live.bb_preflop_option_open = False
            self._human_more_time_available = False
            self._advance_after_action()
            return
        need = self._hand_accounting.chips_needed_to_call(hs)
        self._human_more_time_available = False
        if need > 0:
            self._call(hs)
        else:
            self._check(hs)

    @QtCore.Slot(bool)
    def setHumanSitOut(self, on: bool) -> None:
        prev = bool(self._human_sitting_out)
        self._human_sitting_out = bool(on)
        if self._human_sitting_out:
            if self._live.bb_preflop_waiting:
                self._finish_bb_preflop_check()
            elif self._live.acting_seat == self.HUMAN_HERO_SEAT and self._interactive_human:
                hs = int(self.HUMAN_HERO_SEAT)
                need = self._hand_accounting.chips_needed_to_call(hs)
                if need > 0:
                    self.submitFacingAction(self._FACING_FOLD, 0)
                else:
                    # Facing no bet: the UI still routes "fold" here — force a fold to leave the hand.
                    self.submitFoldFromCheck()
        elif prev:
            # Just sat back in: maybe start a new hand on the next tick.
            self._deferred_begin_new_hand_if_enough_seated()
        self._save_game_state_kv()
        self._sync_root()

    @QtCore.Slot()
    def requestMoreTime(self) -> None:
        if not self._human_more_time_available:
            return
        if not (self._live.acting_seat == self.HUMAN_HERO_SEAT or self._live.bb_preflop_waiting):
            return
        self._human_more_time_available = False
        self._decision_seconds_left = min(int(self._decision_seconds_left) + 20, 120)
        self._sync_root()

    @QtCore.Slot()
    def submitFoldFromCheck(self) -> None:
        if self._live.bb_preflop_waiting:
            return
        hs = int(self.HUMAN_HERO_SEAT)
        if self._live.acting_seat != hs:
            return
        self._human_more_time_available = False
        self._fold(hs)

    @QtCore.Slot(int)
    def tryBuyBackIn(self, seat: int) -> None:
        seat = int(seat)
        if not (0 <= seat < 6):
            return
        if seat == self.HUMAN_HERO_SEAT and not self._interactive_human:
            return
        if self._player(seat).stack_on_table > 0:
            return
        if self._player(seat).bankroll_off_table <= 0:
            return
        cap = int(self._table.buy_in_cap_chips())
        br = int(self._player(seat).bankroll_off_table)
        add = min(br, cap if cap > 0 else br)
        if add <= 0:
            return
        self._player(seat).transfer_from_bankroll_to_table(add)
        self._emit_stats_seq_and_session()
        self._save_game_state_kv()
        self._sync_root()
