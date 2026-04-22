from __future__ import annotations

import random
import time
from typing import Any

from PySide6 import QtCore

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend.game_screen_sync import sync_game_screen_properties
from texasholdemgym.backend.game_table import DealPositions, Player, StrategyTuning, Table
from texasholdemgym.backend.hand_accounting import HandAccounting
from texasholdemgym.backend.live_hand import LiveHandState
from texasholdemgym.backend.range_manager import RangeManager
from texasholdemgym.backend.street_bet_controller import StreetBetController
from texasholdemgym.backend.table_bot import BotDecision, BotDecisionKind, SeatBotObservation, TableRulesBot
from texasholdemgym.backend import range_notation
from texasholdemgym.backend.hand_history import HandHistory
from texasholdemgym.backend.poker_core.board_deal import deal_next_community_street, run_out_board_to_river
from texasholdemgym.backend.poker_core.blind_positions import first_postflop_actor, first_preflop_actor
from texasholdemgym.backend.poker_core.betting_navigation import all_called_or_folded, remaining_players
from texasholdemgym.backend.poker_core.cards import card_asset, new_shuffled_deck, pretty_card
from texasholdemgym.backend.poker_core.hole_grid import hole_to_range_grid_row_col
from texasholdemgym.backend.poker_core.raise_rules import min_raise_increment_chips
from texasholdemgym.backend.poker_core.hand_evaluation import (
    StandardHandEvaluator,
    best_rank_7,
    rank_tuple_display_name,
    rank_tuple_to_strength_01,
)
from texasholdemgym.backend.poker_core.pot import compute_pot_slices, distribute_showdown_side_pots
from texasholdemgym.backend.sqlite_store import AppDatabase, _card_tuple_to_wire_int

_GAME_STATE_KV = "poker_game_state_v1"
_RANGES_KV = "seat_ranges_v1"

try:
    from PySide6 import shiboken6  # type: ignore
except ImportError:  # pragma: no cover
    shiboken6 = None  # type: ignore

try:
    from PySide6.QtQml import QQmlProperty
except ImportError:  # pragma: no cover
    QQmlProperty = None  # type: ignore

try:
    from PySide6.QtQuick import QQuickItem
except ImportError:  # pragma: no cover
    QQuickItem = None  # type: ignore


class PokerGame(QtCore.QObject):
    """Qt bridge: `Table`, `LiveHandState`, `HandAccounting`, `StreetBetController`, `RangeManager`, `TableRulesBot`."""

    HUMAN_HERO_SEAT = int(Table.HERO_SEAT)

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
        self._db = db
        self._hand_history = hand_history
        # QML `game_screen` object (may be destroyed when navigating away).
        self._root_obj: QtCore.QObject | None = None
        self._rng = random.Random()

        self._interactive_human = True
        self._bot_slow_actions = True
        self._winning_hand_show_ms = 2500
        self._bot_decision_delay_sec = 2

        self._stats_seq = 0

        # Roster, stacks, bankrolls, and bot archetypes live on `Table`.
        self._table = Table.default_six_max()

        # Current deal: cards, board, positions, street (see `live_hand.LiveHandState`).
        self._live = LiveHandState()
        self._decision_seconds_left = 0
        self._decision_timer = QtCore.QTimer(self)
        self._decision_timer.setInterval(1000)
        self._decision_timer.timeout.connect(self._tick_decision)
        # Parented single-shot timer is more reliable than `QTimer.singleShot` for bot actions.
        self._bot_timer = QtCore.QTimer(self)
        self._bot_timer.setSingleShot(True)
        self._bot_timer.timeout.connect(self._bot_act)

        self._hand_accounting = HandAccounting()
        self._street = StreetBetController(
            self._table,
            self._live,
            self._hand_accounting,
            after_chips_sync=self._sync_root,
        )
        self._ranges = RangeManager()
        self._seat_bot = TableRulesBot()

        # Per-seat opening-range editor (Setup): 3 layers × 13×13 weights + pasted text (`RangeManager`).
        self._human_sitting_out = False
        self._human_more_time_available = False
        # Auto hand loop: deal next hand after showdown delay when idle.
        self._auto_hand_loop = True
        self._next_hand_timer = QtCore.QTimer(self)
        self._next_hand_timer.setSingleShot(True)
        self._next_hand_timer.timeout.connect(self._run_next_hand_timer_fire)

        # Session bankroll snapshots (for StatsScreen charts).
        self._bankroll_snapshots_ms: list[int] = []
        self._bankroll_snapshot_table: list[list[int]] = []
        self._bankroll_snapshot_total: list[list[int]] = []

        # Baselines for Stats leaderboard P/L (on-table) and Δ total vs session start / chart reset.
        self._session_baseline_table: list[int] = [0] * 6
        self._session_baseline_total: list[int] = [0] * 6

        # `_sync_root` re-entrancy: avoid nested `processEvents` (would run the whole bot hand in one pump).
        self._sync_root_depth: int = 0
        self._hand_evaluator = StandardHandEvaluator()

        for s in range(6):
            self._apply_strategy_preset(s)
        self._refresh_session_stats_baseline()

    def _player(self, seat: int) -> Player:
        return self._table.players[int(seat) % 6]

    def _refresh_session_stats_baseline(self) -> None:
        table0, total0 = self._table.session_baseline_snapshot()
        self._session_baseline_table[:] = list(table0)
        self._session_baseline_total[:] = list(total0)

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

    def _max_street_contrib(self) -> int:
        return self._hand_accounting.max_street_contrib()

    def _count_eligible_for_deal(self) -> int:
        """Count seats eligible for the next deal (idle path; no pending wallet flush)."""
        return int(self._table.count_eligible_for_deal_roster(self._human_sitting_out))

    def _bootstrap_playable_table(self) -> None:
        """If persisted Setup/KV left fewer than two funded, participating seats, seed stacks like a fresh table.

        Without this, `beginNewHand` no-ops forever (no pot, no acting seat, HUD looks dead).
        """
        hso, changed = self._table.bootstrap_if_insufficient_players(self._human_sitting_out)
        self._human_sitting_out = hso
        if changed:
            self._save_game_state_kv()

    def _seat_eligible_for_new_hand(self, i: int) -> bool:
        return self._table.seat_eligible_for_deal(int(i), self._human_sitting_out)

    def _schedule_next_hand_if_idle(self) -> None:
        """Schedule the next hand after `complete_hand_idle()` when the table is idle."""
        if not self._auto_hand_loop:
            return
        ms = int(max(500, min(60000, int(self._winning_hand_show_ms))))
        self._next_hand_timer.stop()
        self._next_hand_timer.start(ms)

    def _run_next_hand_timer_fire(self) -> None:
        # Some builds gate on QML root for UI-only nudges; the engine must still advance when QML is not
        # bound yet (startup race) or `game_screen` was not found — otherwise the table never deals again.
        if self._live.in_progress:
            return
        self.beginNewHand()

    def _maybe_begin_hand_after_setup_change(self) -> None:
        """Idle table: queue `beginNewHand` when ≥2 can deal (e.g. after Setup changes)."""
        if self._live.in_progress:
            return
        if self._count_eligible_for_deal() < 2:
            return
        self.beginNewHand()

    def _effective_seat_buy_in_chips(self, seat: int) -> int:
        """Target on-table stack for a seat (delegates to ``Table``)."""
        return int(
            self._table.effective_buy_in_chips(
                int(seat),
                hero_seat=int(self.HUMAN_HERO_SEAT),
                interactive_hero=bool(self._interactive_human),
            )
        )

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

    def _compute_pot_slices(self):
        return compute_pot_slices(self._hand_accounting.contrib_totals_list(), self._live.in_hand)

    # --- Engine core ---
    def _init_street_acted_for_new_round(self) -> None:
        self._live.init_street_acted(self._table.participating_list(), self._live.in_hand, self._table.stacks_list())

    def _mark_street_acted(self, seat: int) -> None:
        self._street.mark_street_acted(seat)

    def _betting_round_fully_resolved(self) -> bool:
        """True when this street's betting is complete (including a full check-down). Kept for tests / harness."""
        return self._street.betting_round_complete()

    def _log_table_action(self, seat: int, kind_label: str, chips: int, *, is_blind: bool = False) -> None:
        self._street.log_street_action(seat, kind_label, chips, is_blind=is_blind)

    def _bet(self, seat: int, amount: int, label: str = "") -> None:
        self._street.apply_contribution(seat, amount, label)

    def _begin_betting_round(self, first: int, *, fresh_street: bool = True) -> None:
        if first < 0:
            self._live.acting_seat = -1
            self._decision_seconds_left = 0
            self._decision_timer.stop()
            # Do not leave `_in_progress` with no actor — `_tick_decision` will never fire
            # `_auto_action_timeout` when `acting_seat < 0` (stall with a live hand).
            if self._live.in_progress:
                alive = self._remaining_players()
                if len(alive) <= 1:
                    self._award_uncontested(alive[0] if alive else -1)
                    return
                # Do **not** treat `_all_called_or_folded()` alone as "advance street" here: after
                # After `_street.reset_street()` a new board street has `to_call == 0` and zero
                # `street_put_in`, so everyone trivially "matches" $0 — the function returns True and would
                # chain-call `_advance_street_or_showdown()` (deal turn/river with no bets, stuck `acting_seat`).
                # `betting_round_complete` also requires a full check-down when there is no bet.
                if self._street.betting_round_complete():
                    if self._maybe_handle_bb_preflop_option():
                        return
                    self._advance_street_or_showdown()
                    return
                pivot = int(self._live.bb_seat) if int(self._live.street) == 0 else int(self._live.button_seat)
                nxt = self._table.next_seat_clockwise_from(pivot, self._live.in_hand, need_chips=True)
                if nxt < 0:
                    nxt = self._table.next_seat_clockwise_from(pivot, self._live.in_hand, need_chips=False)
                if nxt >= 0:
                    self._live.acting_seat = nxt
                    self._decision_seconds_left = 20
                    self._human_more_time_available = True
                    self._decision_timer.start()
                    self._sync_root()
                    self._maybe_schedule_bot()
                    return
                QtCore.qWarning("PokerGame: could not recover first actor after first<0; forcing street/showdown.")
                self._advance_street_or_showdown()
                return
            self._sync_root()
            return
        self._live.acting_seat = first
        if fresh_street:
            self._init_street_acted_for_new_round()
        self._decision_seconds_left = 20
        self._human_more_time_available = True
        self._decision_timer.start()
        self._sync_root()
        self._maybe_schedule_bot()

    def _all_called_or_folded(self) -> bool:
        return all_called_or_folded(
            self._table.participating_list(),
            self._live.in_hand,
            self._hand_accounting.street_put_in_list(),
            self._table.stacks_list(),
            self._hand_accounting.to_call,
        )

    def _remaining_players(self) -> list[int]:
        return remaining_players(self._table.participating_list(), self._live.in_hand)

    def _distribute_showdown_side_pots(self) -> list[int]:
        """Side-pot–aware NLHE distribution by contribution tiers (best hand per slice among contenders)."""
        return distribute_showdown_side_pots(
            self._hand_accounting.contrib_totals_list(),
            self._live.in_hand,
            self._remaining_players(),
            self._live.board,
            self._live.holes,
            self._hand_evaluator,
        )

    def _record_completed_hand(
        self,
        winners: list[int],
        pot_awards: list[int] | None = None,
        *,
        winning_hand_name: str = "",
    ) -> None:
        if self._hand_history is None:
            self._save_game_state_kv()
            return
        ended = int(time.time() * 1000)
        board_display = " ".join(pretty_card(c) for c in self._live.board if c[0] >= 2).strip()
        board_assets = [card_asset(c) for c in self._live.board if c[0] >= 2]
        n_players = int(self._live.hand_num_dealt) if self._live.hand_num_dealt > 0 else sum(
            1 for i in range(6) if self._player(i).participating
        )
        aw = list(pot_awards) if pot_awards is not None else [0] * 6
        players_detail: list[dict[str, Any]] = []
        for s in range(6):
            if self._live.hand_num_dealt > 0:
                if s >= len(self._live.hand_dealt_mask) or not self._live.hand_dealt_mask[s]:
                    continue
            elif not self._player(s).participating:
                continue
            h0, h1 = self._live.holes[s]
            players_detail.append(
                {
                    "seat": int(s),
                    "contrib": int(self._hand_accounting.contrib_at(s)),
                    "won": int(aw[s]),
                    "hole_svg1": card_asset(h0),
                    "hole_svg2": card_asset(h1),
                    "total_bankroll": int(self._player(s).bankroll_off_table + self._player(s).stack_on_table),
                }
            )
        board_codes: list[int] = []
        for i in range(5):
            if i < len(self._live.board):
                r, s = self._live.board[i]
                board_codes.append(_card_tuple_to_wire_int((r, s)))
            else:
                board_codes.append(-1)
        payload: dict[str, Any] = {
            "startedMs": int(self._hand_accounting.history_started_ms()),
            "endedMs": ended,
            "numPlayers": int(n_players),
            "boardDisplay": board_display,
            "boardAssets": board_assets,
            "boardCardCodes": board_codes,
            "winners": [int(x) for x in winners],
            "sbSize": int(self._table.small_blind),
            "bbSize": int(self._table.big_blind),
            "buttonSeat": int(self._live.button_seat),
            "sbSeat": int(self._live.sb_seat),
            "bbSeat": int(self._live.bb_seat),
            "sessionKey": 0,
            "actions": self._hand_accounting.snapshot_actions(),
            "playersDetail": players_detail,
            "totalHandWonChips": int(sum(aw)),
        }
        wh = str(winning_hand_name or "").strip()
        if wh:
            payload["winningHandName"] = wh
        self._hand_history.record_completed_hand(payload)
        # Snapshot stacks for session stats.
        self._bankroll_snapshots_ms.append(int(ended))
        self._bankroll_snapshot_table.append(self._table.stacks_list())
        self._bankroll_snapshot_total.append(
            [int(self._player(i).bankroll_off_table + self._player(i).stack_on_table) for i in range(6)]
        )
        self._save_game_state_kv()

    def _advance_street_or_showdown(self) -> None:
        alive = self._remaining_players()
        if len(alive) <= 1:
            self._award_uncontested(alive[0] if alive else -1)
            return

        # Deal next street
        if self._live.street >= 3:
            self._do_showdown()
            return
        self._live.street = deal_next_community_street(self._live.street, self._live.board, self._live.deck)

        self._street.reset_street()
        first = first_postflop_actor(
            self._live.button_seat,
            self._remaining_players(),
            self._table.stacks_list(),
            lambda need_chips: self._table.next_seat_clockwise_from(
                self._live.button_seat, self._live.in_hand, need_chips=need_chips
            ),
            started_as_heads_up=bool(int(self._live.hand_num_dealt) == 2),
        )
        if first < 0 and len(self._remaining_players()) >= 2:
            # Everyone still in the hand is all-in — no further betting; run out board.
            self._decision_timer.stop()
            self._live.acting_seat = -1
            self._decision_seconds_left = 0
            self._live.street = run_out_board_to_river(self._live.street, self._live.board, self._live.deck)
            self._do_showdown()
            return
        self._begin_betting_round(first)

    def _award_uncontested(self, winner: int) -> None:
        pot = self._hand_accounting.total_contrib_chips()
        aw = [0] * 6
        if winner >= 0:
            aw[winner] = pot
            self._player(winner).receive_from_pot(pot)
        self._live.showdown = True
        self._live.acting_seat = -1
        self._decision_timer.stop()
        self._decision_seconds_left = 0
        win_list = [int(winner)] if winner >= 0 else []
        self._live.showdown_status_text = (
            Table.format_showdown_line(win_list, "Uncontested", bot_names=Table.DEFAULT_BOT_NAMES)
            if winner >= 0
            else "Showdown"
        )
        self._live.in_progress = False
        self._record_completed_hand(win_list, aw, winning_hand_name="Uncontested")
        self._sync_root()
        self._schedule_next_hand_if_idle()

    def _hand_strength_01_seat(self, seat: int) -> float:
        """Upstream `hand_strength_01_cards` — strength of best 5 of hole + board."""
        h0, h1 = self._live.holes[seat]
        if h0[0] < 2 or h1[0] < 2:
            return 0.0
        cards7 = [h0, h1] + [c for c in self._live.board if c[0] >= 2]
        if len(cards7) < 2:
            return 0.0
        return rank_tuple_to_strength_01(best_rank_7(cards7))

    def _seat_bot_observation(self, seat: int, *, context: str) -> SeatBotObservation:
        s = int(seat)
        h0, h1 = self._live.holes[s]
        cw = self._ranges.chart_weights_for_hole(s, h0, h1)
        ppm = self._ranges.play_metric_for_hole(s, h0, h1)
        if self._live.street == 0:
            sig = float(ppm)
            rw = float(cw[1])
        else:
            sig = float(self._hand_strength_01_seat(s))
            rw = float(sig)
        return SeatBotObservation(
            context=str(context),
            seat=s,
            street=int(self._live.street),
            stack=int(self._player(s).stack_on_table),
            archetype_index=int(self._player(s).strategy.archetype_index),
            tuning=self._player(s).strategy.tuning,
            need_to_call=int(self._hand_accounting.chips_needed_to_call(s)),
            to_call=int(self._hand_accounting.to_call),
            street_put_in_at_seat=int(self._hand_accounting.street_put_in_at(s)),
            min_raise_increment=int(
                min_raise_increment_chips(self._table.big_blind, self._hand_accounting.last_raise_increment)
            ),
            preflop_blind_level=int(self._hand_accounting.preflop_blind_level),
            big_blind=int(self._table.big_blind),
            street_bet=int(self._table.street_bet),
            max_street_contrib=int(self._max_street_contrib()),
            signal_continue=float(sig),
            weight_raise_gate=float(rw),
            weight_bet_layer=float(cw[2]),
            preflop_play_metric=float(ppm),
        )

    def _apply_bot_decision(self, seat: int, decision: BotDecision) -> None:
        s = int(seat)
        if decision.kind == BotDecisionKind.FOLD:
            self._fold(s)
        elif decision.kind == BotDecisionKind.CHECK:
            self._check(s)
        elif decision.kind == BotDecisionKind.CALL:
            self._call(s)
        elif decision.kind == BotDecisionKind.RAISE_TO_LEVEL:
            self._raise_to(s, int(decision.raise_to_street_level))
        else:
            QtCore.qWarning("PokerGame: unexpected bot decision kind; checking.")
            self._check(s)

    def _do_showdown(self) -> None:
        alive = self._remaining_players()
        if not alive:
            self._award_uncontested(-1)
            return
        ranks = {}
        for s in alive:
            cards7 = list(self._live.board) + list(self._live.holes[s])
            ranks[s] = best_rank_7(cards7)
        best = max(ranks.values())
        winners = [s for s, r in ranks.items() if r == best]
        wh_name = rank_tuple_display_name(best)
        awards = self._distribute_showdown_side_pots()
        for s in range(6):
            self._player(s).receive_from_pot(awards[s])
        self._live.showdown = True
        self._live.acting_seat = -1
        self._decision_timer.stop()
        self._decision_seconds_left = 0
        win_disp = sorted([s for s in range(6) if awards[s] > 0])
        if not win_disp:
            win_disp = list(winners)
        self._live.showdown_status_text = Table.format_showdown_line(
            win_disp, wh_name, bot_names=Table.DEFAULT_BOT_NAMES
        )
        self._live.in_progress = False
        self._record_completed_hand(win_disp, awards, winning_hand_name=wh_name)
        self._sync_root()
        self._schedule_next_hand_if_idle()

    # --- Decision handling ---
    def _tick_decision(self) -> None:
        # Never stop the decision timer solely because actingSeat is -1 while a hand is still
        # in progress — that stranded games after the first timeout. Idle ends stop elsewhere.
        if self._live.acting_seat < 0:
            if not self._live.in_progress:
                self._decision_timer.stop()
                return
            # A live hand must always have a decision clock target (or be advancing streets). If we
            # ever land on acting_seat == -1 with in_progress True — e.g. a bad first-seat edge case
            # or a partial UI/engine sync — re-run the same recovery path as `first == -1` in
            # `_begin_betting_round` instead of ticking forever with no `_auto_action_timeout`.
            if not self._live.bb_preflop_waiting:
                self._begin_betting_round(-1)
            return
        self._decision_seconds_left = max(0, self._decision_seconds_left - 1)
        self._sync_root()
        if self._decision_seconds_left <= 0:
            self._auto_action_timeout()

    def _auto_action_timeout(self) -> None:
        if self._live.bb_preflop_waiting:
            self._finish_bb_preflop_check()
            return
        seat = self._live.acting_seat
        if seat < 0:
            return
        # Avoid acting twice if `_bot_timer` fires after the decision clock (both can be armed for bots).
        self._bot_timer.stop()
        # Hero seat with interactive HUD uses fold/check timeouts; every other seat is engine‑bot logic.
        # Relying only on `_bot_timer` left the table stuck when that timer never fired (seen on some setups).
        if seat != self.HUMAN_HERO_SEAT or not self._interactive_human:
            self._bot_act()
            return
        need = self._hand_accounting.chips_needed_to_call(seat)
        if need > 0:
            self._fold(seat)
        else:
            self._check(seat)

    def _maybe_schedule_bot(self) -> None:
        s = self._live.acting_seat
        if s < 0:
            return
        if self._live.bb_preflop_waiting:
            return
        is_human = s == self.HUMAN_HERO_SEAT and self._interactive_human
        if is_human:
            return
        self._bot_timer.stop()
        delay_ms = int(max(0, self._bot_decision_delay_sec) * 1000) if self._bot_slow_actions else 0
        self._bot_timer.start(delay_ms)

    def _recover_stale_acting_seat(self) -> None:
        """If `acting_seat` points at a folded/out player, move action or end the street (timer stall fix)."""
        s = self._live.acting_seat
        if s < 0 or not self._live.in_progress:
            return
        nxt = self._table.next_seat_clockwise_from(s, self._live.in_hand, need_chips=True)
        if nxt < 0:
            nxt = self._table.next_seat_clockwise_from(s, self._live.in_hand, need_chips=False)
        if nxt >= 0:
            self._live.acting_seat = nxt
            self._decision_seconds_left = 20
            self._human_more_time_available = True
            self._decision_timer.start()
            self._sync_root()
            self._maybe_schedule_bot()
            return
        if self._street.betting_round_complete():
            if self._maybe_handle_bb_preflop_option():
                return
            self._advance_street_or_showdown()
            return
        alive = self._remaining_players()
        if len(alive) <= 1:
            self._award_uncontested(alive[0] if alive else -1)

    def _bot_act(self) -> None:
        s = self._live.acting_seat
        if s < 0:
            return
        if not self._live.in_hand[s]:
            QtCore.qWarning("PokerGame: _bot_act with folded/out acting seat; recovering.")
            self._recover_stale_acting_seat()
            return
        obs = self._seat_bot_observation(s, context="street")
        decision = self._seat_bot.decide_street_action(obs, self._rng)
        self._apply_bot_decision(s, decision)

    def _fold(self, seat: int) -> None:
        self._live.in_hand[seat] = False
        self._live.street_action_text[seat] = "Fold"
        self._log_table_action(seat, "Fold", 0)
        self._advance_after_action()

    def _check(self, seat: int) -> None:
        self._live.street_action_text[seat] = "Check"
        self._log_table_action(seat, "Check", 0)
        self._mark_street_acted(seat)
        self._advance_after_action()

    def _call(self, seat: int) -> None:
        need = self._hand_accounting.chips_needed_to_call(seat)
        self._bet(seat, need, label="Call" if need > 0 else "Check")
        self._advance_after_action()

    def _raise_to(self, seat: int, to_amount: int) -> None:
        to_amount = int(to_amount)
        if to_amount <= self._hand_accounting.to_call:
            self._call(seat)
            return
        prev_max = int(self._hand_accounting.to_call)
        need = max(0, to_amount - self._hand_accounting.street_put_in_at(seat))
        self._bet(seat, need, label="Raise")
        new_contrib = int(self._hand_accounting.street_put_in_at(seat))
        self._hand_accounting.bump_to_call_with_seat_street(seat)
        if new_contrib > prev_max:
            self._hand_accounting.last_raise_increment = int(new_contrib - prev_max)
        if self._live.street == 0 and self._hand_accounting.to_call > self._hand_accounting.preflop_blind_level:
            self._live.bb_preflop_option_open = False
        self._hand_accounting.last_raiser = seat
        self._advance_after_action()

    def _advance_after_action(self) -> None:
        # If only one left, award and stop.
        alive = self._remaining_players()
        if len(alive) <= 1:
            self._award_uncontested(alive[0] if alive else -1)
            return
        if self._street.betting_round_complete():
            if self._maybe_handle_bb_preflop_option():
                return
            self._advance_street_or_showdown()
            return
        nxt = self._table.next_seat_clockwise_from(self._live.acting_seat, self._live.in_hand, need_chips=True)
        if nxt < 0:
            if self._maybe_handle_bb_preflop_option():
                return
            if self._street.betting_round_complete():
                self._advance_street_or_showdown()
            return
        self._live.acting_seat = nxt
        self._decision_seconds_left = 20
        self._human_more_time_available = True
        self._decision_timer.start()
        self._sync_root()
        self._maybe_schedule_bot()

    def _maybe_handle_bb_preflop_option(self) -> bool:
        """BB preflop branch: returns True if caller must not advance street yet."""
        if self._live.street != 0:
            return False
        mx = self._max_street_contrib()
        if mx != self._hand_accounting.preflop_blind_level or not self._live.bb_preflop_option_open:
            return False
        self._live.bb_preflop_option_open = False
        bb = int(self._live.bb_seat)
        if not (0 <= bb < 6 and self._live.in_hand[bb]):
            return False
        hs = int(self.HUMAN_HERO_SEAT)
        if bb == hs and self._interactive_human and self._root() is not None:
            if self._player(hs).stack_on_table <= 0:
                return False
            self._live.bb_preflop_waiting = True
            self._live.acting_seat = hs
            self._decision_seconds_left = 20
            self._human_more_time_available = True
            self._decision_timer.start()
            self._sync_root()
            return True
        return self._bot_bb_preflop_option(bb)

    def _finish_bb_preflop_check(self) -> None:
        self._live.bb_preflop_waiting = False
        self._decision_timer.stop()
        self._decision_seconds_left = 0
        self._human_more_time_available = False
        bb = int(self._live.bb_seat)
        if 0 <= bb < 6:
            self._live.street_action_text[bb] = "Check"
            self._log_table_action(bb, "Check", 0)
            self._mark_street_acted(bb)
        # Keep actingSeat until the next street begins so _tick_decision does not stop the
        # clock while we are between streets (would strand the hand with no timer).
        self._sync_root()
        self._advance_street_or_showdown()

    def _bb_preflop_add_raise(self, chips_to_add: int) -> None:
        bb = int(self._live.bb_seat)
        if not (0 <= bb < 6 and bb == self.HUMAN_HERO_SEAT):
            return
        inc = min_raise_increment_chips(self._table.big_blind, self._hand_accounting.last_raise_increment)
        if inc <= 0 or self._max_street_contrib() != self._hand_accounting.preflop_blind_level or self._player(bb).stack_on_table <= 0:
            self._finish_bb_preflop_check()
            return
        c = int(max(inc, min(int(chips_to_add), int(self._player(bb).stack_on_table))))
        if c < inc:
            self._finish_bb_preflop_check()
            return
        self._bet(bb, c, label="Raise")
        self._hand_accounting.last_raise_increment = int(c)
        self._hand_accounting.bump_to_call_with_seat_street(bb)
        self._live.bb_preflop_option_open = False
        self._live.bb_preflop_waiting = False
        self._decision_timer.stop()
        self._decision_seconds_left = 0
        self._human_more_time_available = False
        self._sync_root()
        first = self._table.next_seat_clockwise_from(bb, self._live.in_hand, need_chips=True)
        if first < 0:
            first = self._table.next_seat_clockwise_from(bb, self._live.in_hand, need_chips=False)
        self._begin_betting_round(first, fresh_street=False)

    def _bot_bb_preflop_option(self, bb: int) -> bool:
        if self._player(bb).stack_on_table <= 0:
            return False
        obs = self._seat_bot_observation(int(bb), context="bb_preflop_option")
        d = self._seat_bot.decide_bb_preflop_option(obs, self._rng)
        self._decision_timer.stop()
        if d.kind == BotDecisionKind.BB_PREFLOP_RAISE:
            inc = int(d.bb_raise_chips)
            self._bet(bb, inc, label="Raise")
            self._hand_accounting.last_raise_increment = int(inc)
            self._hand_accounting.bump_to_call_with_seat_street(bb)
            self._sync_root()
            first = self._table.next_seat_clockwise_from(bb, self._live.in_hand, need_chips=True)
            if first < 0:
                first = self._table.next_seat_clockwise_from(bb, self._live.in_hand, need_chips=False)
            self._begin_betting_round(first, fresh_street=False)
            return True
        self._live.street_action_text[bb] = "Check"
        self._log_table_action(bb, "Check", 0)
        self._mark_street_acted(bb)
        self._sync_root()
        return False

    # Properties used by QML bindings / Connections
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

    # Methods used by QML
    # `object` breaks QML→Python: GameScreen is a QObject, not a PyObjectWrapper. Use QObject.
    @QtCore.Slot(QtCore.QObject)
    def setRootObject(self, obj: QtCore.QObject | None) -> None:
        # Bind to the QML `game_screen` item; clear safely when QML destroys it.
        if obj is None:
            prev = self._root_obj
            if prev is not None:
                self._disconnect_game_screen_button(prev)
                try:
                    prev.destroyed.disconnect(self._on_root_destroyed)  # type: ignore[attr-defined]
                except Exception:
                    pass
            self._root_obj = None
            return

        prev = self._root_obj
        if prev is obj:
            self._sync_root()
            return
        if prev is not None:
            self._disconnect_game_screen_button(prev)
            try:
                prev.destroyed.disconnect(self._on_root_destroyed)  # type: ignore[attr-defined]
            except Exception:
                pass

        self._root_obj = obj
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
        # Critical when a hand started before QML bound (e.g. `_run_next_hand_timer_fire` with no root):
        # `beginNewHand` may then no-op (`_in_progress` + root) without ever pushing engine state here.
        self._sync_root()

    @QtCore.Slot(str)
    def _on_game_screen_button(self, button: str) -> None:
        """QML `GameScreen.buttonClicked` — same routing as the app shell used to do in `app.py`."""
        b = str(button)
        if b == "MORE_TIME":
            self.requestMoreTime()
            return
        if b == "FOLD":
            self.submitFacingAction(0, 0)
        elif b == "CALL":
            self.submitFacingAction(1, 0)
        elif b == "CHECK":
            self.submitCheckOrBet(True, 0)

    @QtCore.Slot()
    def beginNewHand(self) -> None:
        # Initialize a new hand with simple NLHE rules.
        self._next_hand_timer.stop()
        # Do not stack a new deal on an active table session; if QML root is gone, allow recovery
        # (e.g. page destroyed while a hand was marked in progress).
        if self._live.in_progress and self._root() is not None:
            self._sync_root()
            return
        self._bootstrap_playable_table()
        self._live.reset_for_new_deal()
        self._human_more_time_available = False
        # Who is eligible this hand (do not use `_in_hand` yet — it still holds last hand's folds).
        # Human excluded when sitting out; seats 1–5 respect Setup toggles only.
        dp = DealPositions.from_table(self._table, self._live.button_seat, self._human_sitting_out)
        dealing = dp.dealing
        n_live = dp.n_live
        self._live.hand_dealt_mask = [bool(dealing[i]) for i in range(6)]
        self._live.hand_num_dealt = int(n_live)
        if n_live < 2:
            self._live.in_progress = False
            self._live.acting_seat = -1
            self._decision_timer.stop()
            self._decision_seconds_left = 0
            if self._root() is not None:
                self._set_root(
                    "statusText",
                    "Need at least two players in the hand. Sit in to play or add players.",
                )
            self._sync_root()
            return

        self._live.hand_seq += 1
        self._hand_accounting.begin_action_log(int(time.time() * 1000))
        self._live.in_progress = True
        self._live.street = 0

        self._live.button_seat = dp.button_seat
        self._live.sb_seat, self._live.bb_seat = dp.sb_seat, dp.bb_seat

        self._live.deck = self._new_shuffled_deck()
        self._live.board = []
        self._live.holes = [[self._live.deck.pop(), self._live.deck.pop()] for _ in range(6)]

        self._live.in_hand = dealing
        self._hand_accounting.clear_for_new_hand()
        self._street.reset_street()
        self._street.post_blinds()

        first = first_preflop_actor(
            self._live.bb_seat,
            n_live,
            dealing,
            lambda need_chips: self._table.next_seat_clockwise_from(
                self._live.bb_seat, self._live.in_hand, need_chips=need_chips
            ),
        )
        self._begin_betting_round(first)

    # --- Range editor (Setup) persistence (KV blob) — see `RangeManager` ---
    @staticmethod
    def _hole_to_grid_row_col(h0: tuple[int, int], h1: tuple[int, int]) -> tuple[int, int]:
        """Delegate to `poker_core.hole_grid` (kept on `PokerGame` for tests / call sites)."""
        return hole_to_range_grid_row_col(h0, h1)

    def _persist_ranges_kv(self) -> None:
        if self._db is None:
            return
        self._db.kv_set_json(_RANGES_KV, self._ranges.bundle())

    def _load_ranges_from_kv(self) -> None:
        if self._db is None:
            return
        self._ranges.apply_bundle(self._db.kv_get_json(_RANGES_KV))
        self._ranges.touch()

    def _game_state_dict(self) -> dict[str, Any]:
        return {
            "sb": int(self._table.small_blind),
            "bb": int(self._table.big_blind),
            "streetBet": int(self._table.street_bet),
            "maxTableBb": int(self._table.max_on_table_bb),
            "startStack": int(self._table.start_stack),
            "seatBuyIn": self._table.stacks_list(),
            "seatBankrollTotal": self._table.bankrolls_list(),
            "seatParticipating": self._table.participating_list(),
            "interactiveHuman": bool(self._interactive_human),
            "humanSittingOut": bool(self._human_sitting_out),
            "botSlowActions": bool(self._bot_slow_actions),
            "winningHandShowMs": int(self._winning_hand_show_ms),
            "botDecisionDelaySec": int(self._bot_decision_delay_sec),
            "buttonSeat": int(self._live.button_seat),
            "seatStrategyIdx": [int(p.strategy.archetype_index) for p in self._table.players],
            "autoHandLoop": bool(self._auto_hand_loop),
        }

    def _save_game_state_kv(self) -> None:
        if self._db is None:
            return
        self._db.kv_set_json(_GAME_STATE_KV, self._game_state_dict())

    @QtCore.Slot()
    def loadPersistedSettings(self) -> None:
        if self._db is None:
            return
        m = self._db.kv_get_json(_GAME_STATE_KV)
        if not isinstance(m, dict):
            return
        self._table.small_blind = int(m.get("sb", self._table.small_blind))
        self._table.big_blind = int(m.get("bb", self._table.big_blind))
        self._table.street_bet = int(m.get("streetBet", self._table.street_bet))
        self._table.max_on_table_bb = int(m.get("maxTableBb", self._table.max_on_table_bb))
        self._table.start_stack = int(m.get("startStack", self._table.start_stack))
        sb = m.get("seatBuyIn")
        if isinstance(sb, list) and len(sb) == 6:
            self._table.import_stacks([int(x) for x in sb])
        bt = m.get("seatBankrollTotal")
        if isinstance(bt, list) and len(bt) == 6:
            self._table.import_bankrolls([int(x) for x in bt])
        sp = m.get("seatParticipating")
        if isinstance(sp, list) and len(sp) == 6:
            self._table.import_participating([bool(x) for x in sp])
            self._player(int(self.HUMAN_HERO_SEAT)).participating = True
        if "autoHandLoop" in m:
            self._auto_hand_loop = bool(m["autoHandLoop"])
        if "interactiveHuman" in m:
            nh = bool(m["interactiveHuman"])
            if nh != self._interactive_human:
                self._interactive_human = nh
                self.interactiveHumanChanged.emit()
        if "humanSittingOut" in m:
            self._human_sitting_out = bool(m["humanSittingOut"])
        if "botSlowActions" in m:
            nb = bool(m["botSlowActions"])
            if nb != self._bot_slow_actions:
                self._bot_slow_actions = nb
                self.botSlowActionsChanged.emit()
        if "winningHandShowMs" in m:
            nw = int(m["winningHandShowMs"])
            if nw != self._winning_hand_show_ms:
                self._winning_hand_show_ms = nw
                self.winningHandShowMsChanged.emit()
        if "botDecisionDelaySec" in m:
            nd = int(m["botDecisionDelaySec"])
            if nd != self._bot_decision_delay_sec:
                self._bot_decision_delay_sec = nd
                self.botDecisionDelaySecChanged.emit()
        if "buttonSeat" in m:
            self._live.button_seat = int(m["buttonSeat"]) % 6
        ss = m.get("seatStrategyIdx")
        if isinstance(ss, list) and len(ss) == 6:
            for i, x in enumerate(ss[:6]):
                self._player(i).strategy.archetype_index = min(
                    bot_strategy.STRATEGY_COUNT - 1, max(0, int(x))
                )
        self._load_ranges_from_kv()
        for s in range(6):
            if 0 <= s < 6:
                self._player(s).strategy.reload_params_from_archetype()
        self._bootstrap_playable_table()
        self._refresh_session_stats_baseline()
        self.rangeRevisionChanged.emit()
        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()

    @QtCore.Slot()
    def savePersistedSettings(self) -> None:
        self._save_game_state_kv()
        self._persist_ranges_kv()

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

        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()
        self._save_game_state_kv()
        self._sync_root()
        if not self._live.in_progress and self._count_eligible_for_deal() >= 2:
            QtCore.QTimer.singleShot(0, self._maybe_begin_hand_after_setup_change)

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
        self._persist_ranges_kv()
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
        if self._hand_history is not None:
            self._hand_history.clearAll()
        if self._db is not None:
            self._db.kv_delete(_GAME_STATE_KV)
            self._db.kv_delete(_RANGES_KV)
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
        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()
        self._hand_accounting.clear_for_new_hand()
        self._sync_root()

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
        if on and not prev and not self._live.in_progress and self._count_eligible_for_deal() >= 2:
            QtCore.QTimer.singleShot(0, self._maybe_begin_hand_after_setup_change)
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
            self._stats_seq += 1
            self.statsSeqChanged.emit()
            self.sessionStatsChanged.emit()
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
            self._stats_seq += 1
            self.statsSeqChanged.emit()
            self.sessionStatsChanged.emit()
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
            self._persist_ranges_kv()
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
        self._persist_ranges_kv()
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
        self._persist_ranges_kv()
        self.rangeRevisionChanged.emit()

    # Stats
    @QtCore.Slot(result="QVariantList")
    def seatRankings(self):
        rows: list[dict[str, Any]] = []
        for s in range(6):
            table = int(self._player(s).stack_on_table)
            off = int(self._player(s).bankroll_off_table)
            tot = int(off + table)
            t0 = int(self._session_baseline_table[s])
            tot0 = int(self._session_baseline_total[s])
            rows.append(
                {
                    "seat": s,
                    "table": table,
                    "offTable": off,
                    "total": tot,
                    # QML seat table uses stack / wallet; leaderboard uses profit / totalDelta.
                    "stack": table,
                    "wallet": off,
                    "profit": int(table - t0),
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

    @QtCore.Slot(result="QVariantList")
    def bankrollSnapshotTimesMs(self):
        return [int(x) for x in self._bankroll_snapshots_ms]

    @QtCore.Slot(result=int)
    def bankrollSnapshotCount(self) -> int:
        return int(len(self._bankroll_snapshots_ms))

    @QtCore.Slot(int, result="QVariantList")
    def tableStackSeries(self, seat: int):
        seat = int(seat)
        if not (0 <= seat < 6):
            return []
        return [int(snap[seat]) for snap in self._bankroll_snapshot_table]

    @QtCore.Slot(int, result="QVariantList")
    def bankrollSeries(self, seat: int):
        seat = int(seat)
        if not (0 <= seat < 6):
            return []
        return [int(snap[seat]) for snap in self._bankroll_snapshot_total]

    @QtCore.Slot()
    def resetBankrollSession(self) -> None:
        self._bankroll_snapshots_ms = []
        self._bankroll_snapshot_table = []
        self._bankroll_snapshot_total = []
        self._refresh_session_stats_baseline()
        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()

    @QtCore.Slot(int)
    def submitBbPreflopRaise(self, amount: int) -> None:
        if not self._live.bb_preflop_waiting:
            return
        self._bb_preflop_add_raise(int(amount))

    @QtCore.Slot(int, int)
    def submitFacingAction(self, action: int, amount: int) -> None:
        if self._live.bb_preflop_waiting:
            return
        hs = int(self.HUMAN_HERO_SEAT)
        if self._live.acting_seat != hs:
            return
        act = int(action)
        if act == 0:
            self._human_more_time_available = False
            self._fold(hs)
        elif act == 1:
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
            self._bet(hs, chips, label="Raise")
            self._hand_accounting.bump_to_call_with_seat_street(hs)
            self._hand_accounting.last_raise_increment = int(chips)
            if self._live.street == 0 and self._hand_accounting.to_call > self._hand_accounting.preflop_blind_level:
                self._live.bb_preflop_option_open = False
            self._human_more_time_available = False
            self._advance_after_action()
            return
        need = self._hand_accounting.chips_needed_to_call(hs)
        if need > 0:
            self._human_more_time_available = False
            self._call(hs)
        else:
            self._human_more_time_available = False
            if int(amount) <= 0:
                self._check(hs)
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
                    self.submitFacingAction(0, 0)
                else:
                    self.submitFoldFromCheck()
        elif prev and not self._live.in_progress and self._count_eligible_for_deal() >= 2:
            QtCore.QTimer.singleShot(0, self._maybe_begin_hand_after_setup_change)
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
        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()
        self._save_game_state_kv()
        self._sync_root()
