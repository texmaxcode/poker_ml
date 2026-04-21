from __future__ import annotations

from dataclasses import dataclass
import itertools
import random
import time
from typing import Any

from PySide6 import QtCore

from texasholdemgym.backend import bot_strategy
from texasholdemgym.backend import range_notation
from texasholdemgym.backend.hand_history import HandHistory
from texasholdemgym.backend.sqlite_store import AppDatabase, _card_tuple_to_wire_int

_GAME_STATE_KV = "poker_game_state_v1"
_RANGES_KV = "seat_ranges_v1"

# `_hand_rank_5` category index → short label for hand history / UI.
_HAND_CATEGORY_DISPLAY_NAMES = (
    "High card",
    "Pair",
    "Two pair",
    "Three of a kind",
    "Straight",
    "Flush",
    "Full house",
    "Four of a kind",
    "Straight flush",
)

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


@dataclass
class _StrategyParams:
    preflopExponent: float = 1.0
    postflopExponent: float = 1.0
    facingRaiseBonus: float = 0.0
    facingRaiseTightMul: float = 1.0
    openBetBonus: float = 0.0
    openBetTightMul: float = 1.0
    bbCheckraiseBonus: float = 0.0
    bbCheckraiseTightMul: float = 1.0
    buyInBb: int = 100


class PokerGame(QtCore.QObject):
    """Seat index driven by QML: `GameScreen` / `Player` wire the hero HUD only to `seatIndex === 0`."""

    HUMAN_HERO_SEAT = 0
    # Match `BotNames.qml` default labels (seat 0 = hero).
    _SEAT_BOT_NAMES = ("Peter", "James", "John", "Andrew", "Philip")

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
        self._range_revision = 0

        self._seat_participating = [True] * 6
        # Default archetype per seat: Balanced (upstream-style casual table).
        self._seat_strategy_idx = [6] * 6
        self._seat_params = [_StrategyParams() for _ in range(6)]
        self._seat_bankroll_total = [0] * 6
        self._seat_buy_in = [200] * 6

        self._small_blind = 1
        self._big_blind = 2
        self._street_bet = 4
        self._max_on_table_bb = 100
        self._start_stack = 200

        # Runtime hand state (minimal engine)
        self._hand_seq = 0
        self._button_seat = 0
        self._sb_seat = 1
        self._bb_seat = 2
        self._street = 0  # 0 pre, 1 flop, 2 turn, 3 river, 4 showdown
        self._acting_seat = -1
        self._decision_seconds_left = 0
        self._decision_timer = QtCore.QTimer(self)
        self._decision_timer.setInterval(1000)
        self._decision_timer.timeout.connect(self._tick_decision)
        # Parented single-shot timer is more reliable than `QTimer.singleShot` for bot actions.
        self._bot_timer = QtCore.QTimer(self)
        self._bot_timer.setSingleShot(True)
        self._bot_timer.timeout.connect(self._bot_act)

        self._hand_log_started_ms = 0
        self._hand_action_seq = 0
        self._hand_actions: list[dict[str, Any]] = []
        self._hand_num_dealt: int = 0
        self._hand_dealt_mask: list[bool] = [False] * 6

        # Per-seat opening-range editor (Setup): 3 layers × 13×13 weights + pasted text.
        self._range_text: dict[tuple[int, int], str] = {}
        self._range_grid: dict[tuple[int, int], list[float]] = {}

        self._deck: list[tuple[int, int]] = []
        self._board: list[tuple[int, int]] = []
        self._hole: list[list[tuple[int, int]]] = [[(-1, -1), (-1, -1)] for _ in range(6)]
        self._in_hand: list[bool] = [True] * 6
        self._street_put_in: list[int] = [0] * 6
        self._contrib_total: list[int] = [0] * 6
        self._street_action_text: list[str] = [""] * 6
        self._to_call = 0
        self._last_raiser = -1
        self._last_raise_increment = 0
        self._preflop_blind_level = 0
        self._bb_preflop_option_open = False
        self._bb_preflop_waiting = False
        self._human_sitting_out = False
        self._human_more_time_available = False
        self._showdown = False
        self._showdown_status_text = ""
        self._in_progress = False
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

        for s in range(6):
            self._apply_strategy_preset(s)
        self._refresh_session_stats_baseline()

    def _refresh_session_stats_baseline(self) -> None:
        for i in range(6):
            self._session_baseline_table[i] = int(self._seat_buy_in[i])
            self._session_baseline_total[i] = int(
                self._seat_bankroll_total[i] + self._seat_buy_in[i]
            )

    def _apply_strategy_params(self, seat: int) -> None:
        """Load `BotParams` defaults for `seatStrategyIdx` into `_seat_params` (upstream `params_for`)."""
        if not (0 <= seat < 6):
            return
        idx = int(self._seat_strategy_idx[seat]) % bot_strategy.STRATEGY_COUNT
        bp = bot_strategy.params_for_index(idx)
        bot_strategy.apply_bot_params_to_strategy_fields(self._seat_params[seat], bp)

    def _apply_strategy_ranges_from_preset(self, seat: int) -> None:
        """Load default preflop range text + grids for the seat's archetype (`STRATEGY_RANGE_PRESETS`)."""
        if not (0 <= seat < 6):
            return
        idx = int(self._seat_strategy_idx[seat]) % bot_strategy.STRATEGY_COUNT
        call_t, raise_t, open_t = bot_strategy.range_presets_for_index(idx)
        for layer, raw in enumerate((call_t, raise_t, open_t)):
            g = range_notation.parse_range_to_grid(raw)
            self._range_grid[(int(seat), layer)] = g
            self._range_text[(int(seat), layer)] = range_notation.format_grid_to_range(g)

    def _apply_strategy_preset(self, seat: int) -> None:
        self._apply_strategy_params(seat)
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

    # --- Helpers: cards / assets ---
    _RANKS = "23456789TJQKA"
    _SUITS = "cdhs"  # clubs, diamonds, hearts, spades

    @classmethod
    def _pretty_card(cls, card: tuple[int, int]) -> str:
        r, s = card
        if r < 2 or s < 0 or s >= 4:
            return ""
        rank = cls._RANKS[r - 2]
        suit = cls._SUITS[s]
        return rank + suit

    @staticmethod
    def _card_asset(card: tuple[int, int]) -> str:
        r, s = card
        if r < 2 or s < 0:
            return ""
        suit_name = ["clubs", "diamonds", "hearts", "spades"][s]
        rank_name = {
            11: "jack",
            12: "queen",
            13: "king",
            14: "ace",
        }.get(r, str(r))
        return f"{suit_name}_{rank_name}.svg"

    def _new_shuffled_deck(self) -> list[tuple[int, int]]:
        d = [(r, s) for s in range(4) for r in range(2, 15)]
        self._rng.shuffle(d)
        return d

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

    @staticmethod
    def _min_raise_increment_chips(big_blind: int, last_raise_increment: int) -> int:
        return int(max(int(big_blind), int(last_raise_increment)))

    def _max_street_contrib(self) -> int:
        return int(max(self._street_put_in) if self._street_put_in else 0)

    def _count_eligible_for_deal(self) -> int:
        """Count seats eligible for the next deal (idle path; no pending wallet flush)."""
        n = 0
        for i in range(6):
            if int(self._seat_buy_in[i]) <= 0:
                continue
            if i == self.HUMAN_HERO_SEAT and self._human_sitting_out:
                continue
            if i >= 1 and not self._seat_participating[i]:
                continue
            n += 1
        return int(n)

    def _bootstrap_playable_table(self) -> None:
        """If persisted Setup/KV left fewer than two funded, participating seats, seed stacks like a fresh table.

        Without this, `beginNewHand` no-ops forever (no pot, no acting seat, HUD looks dead).
        """
        ss = max(1, int(self._start_stack))
        changed = False
        for i in range(6):
            if not self._seat_participating[i]:
                continue
            if i == self.HUMAN_HERO_SEAT and self._human_sitting_out:
                continue
            if int(self._seat_buy_in[i]) <= 0:
                self._seat_buy_in[i] = ss
                changed = True
        if self._count_eligible_for_deal() >= 2:
            if changed:
                self._save_game_state_kv()
            return
        # Need at least two bodies: hero in + two default bots with chips.
        if self._human_sitting_out:
            self._human_sitting_out = False
            changed = True
        self._seat_participating[0] = True
        for i in (1, 2):
            self._seat_participating[i] = True
            if int(self._seat_buy_in[i]) <= 0:
                self._seat_buy_in[i] = ss
                changed = True
        if int(self._seat_buy_in[0]) <= 0:
            self._seat_buy_in[0] = ss
            changed = True
        if changed:
            self._save_game_state_kv()

    def _dealing_mask_for_new_hand(self) -> list[bool]:
        """Who is dealt in this hand — in-hand mask before counting active players."""
        return [self._seat_eligible_for_new_hand(i) for i in range(6)]

    def _seat_eligible_for_new_hand(self, i: int) -> bool:
        if int(self._seat_buy_in[i]) <= 0:
            return False
        if i == self.HUMAN_HERO_SEAT and self._human_sitting_out:
            return False
        if i >= 1 and not self._seat_participating[i]:
            return False
        return True

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
        if self._in_progress:
            return
        self.beginNewHand()

    def _maybe_begin_hand_after_setup_change(self) -> None:
        """Idle table: queue `beginNewHand` when ≥2 can deal (e.g. after Setup changes)."""
        if self._in_progress:
            return
        if self._count_eligible_for_deal() < 2:
            return
        self.beginNewHand()

    def _effective_seat_buy_in_chips(self, seat: int) -> int:
        """Target on-table stack for a seat (effective buy-in chips)."""
        seat = int(seat)
        cap = int(max(0, self._max_on_table_bb * self._big_blind))
        if not (0 <= seat < 6):
            return int(self._start_stack)
        if seat == self.HUMAN_HERO_SEAT and self._interactive_human:
            return int(min(max(0, int(self._seat_buy_in[seat])), cap)) if cap > 0 else int(self._seat_buy_in[seat])
        bb = max(1, int(self._big_blind))
        mult = max(1, int(self._seat_params[seat].buyInBb))
        return int(max(1, min(mult * bb, cap))) if cap > 0 else max(1, mult * bb)

    def _sync_root(self) -> None:
        if self._root() is None:
            return
        self._sync_root_depth += 1
        try:
            self._sync_root_inner()
        finally:
            self._sync_root_depth -= 1

    def _sync_root_inner(self) -> None:
        # Pot / slices (int amounts for QML)
        pot = sum(self._contrib_total)
        self._set_root("pot", int(pot))
        raw_slices = self._compute_pot_slices()
        self._set_root("potSlices", [int(s.get("amount", 0)) if isinstance(s, dict) else int(s) for s in raw_slices])

        # Seats
        self._set_root("seatStacks", [int(x) for x in self._seat_buy_in])
        self._set_root("seatInHand", [bool(x) for x in self._in_hand])
        self._set_root("seatStreetChips", [int(x) for x in self._street_put_in])
        self._set_root("seatStreetActions", list(self._street_action_text))

        c1 = [self._card_asset(h[0]) if self._in_hand[i] else "" for i, h in enumerate(self._hole)]
        c2 = [self._card_asset(h[1]) if self._in_hand[i] else "" for i, h in enumerate(self._hole)]
        self._set_root("seatC1", c1)
        self._set_root("seatC2", c2)

        self._set_root("buttonSeat", int(self._button_seat))
        self._set_root("sbSeat", int(self._sb_seat))
        self._set_root("bbSeat", int(self._bb_seat))
        self._set_root("seatPositionLabels", [self.seatPositionLabel(i) for i in range(6)])
        self._set_root("smallBlind", int(self._small_blind))
        self._set_root("bigBlind", int(self._big_blind))
        self._set_root("maxStreetContrib", int(self._max_street_contrib()))

        # Board
        b = [self._card_asset(c) for c in self._board] + [""] * 5
        self._set_root("board0", b[0])
        self._set_root("board1", b[1])
        self._set_root("board2", b[2])
        self._set_root("board3", b[3])
        self._set_root("board4", b[4])

        self._set_root("handSeq", int(self._hand_seq))
        self._set_root("actingSeat", int(self._acting_seat))
        self._set_root("showdown", bool(self._showdown))
        self._set_root("seatParticipating", [bool(x) for x in self._seat_participating])
        self._set_root("humanSittingOut", bool(self._human_sitting_out))

        # Facing values for human HUD (raise/call/check affordances)
        hs = int(self.HUMAN_HERO_SEAT)
        stack0 = int(self._seat_buy_in[hs])
        human_bb_wait = bool(self._bb_preflop_waiting)
        human_acting = (
            self._acting_seat == hs
            and self._interactive_human
            and self._in_hand[hs]
            and not self._human_sitting_out
        )
        human_facing = bool(human_acting and not human_bb_wait and self._to_call > self._street_put_in[hs])
        human_open_lane = bool(human_acting and not human_bb_wait and self._to_call <= self._street_put_in[hs])

        self._set_root(
            "decisionSecondsLeft",
            int(self._decision_seconds_left if (human_acting or human_bb_wait) else 0),
        )
        more_time = bool(
            (human_facing or human_open_lane or human_bb_wait)
            and self._human_more_time_available
            and (human_acting or human_bb_wait)
        )
        self._set_root("humanMoreTimeAvailable", more_time)

        self._set_root("humanBbPreflopOption", bool(human_bb_wait))
        self._set_root("humanCanCheck", bool(human_open_lane and not human_bb_wait))

        inc = self._min_raise_increment_chips(self._big_blind, self._last_raise_increment)
        need_raw = max(0, self._to_call - self._street_put_in[hs]) if human_facing else 0
        need = min(need_raw, max(0, stack0)) if human_facing else 0
        can_raise_facing = bool(
            human_facing and inc > 0 and stack0 >= need + inc
        )
        self._set_root("humanCanRaiseFacing", can_raise_facing)
        self._set_root("facingNeedChips", int(need))
        self._set_root("facingMinRaiseChips", int(need + inc) if human_facing else 0)
        self._set_root("facingMaxChips", int(stack0) if human_facing else 0)
        self._set_root("facingPotAmount", int(pot))

        if human_open_lane:
            sb_open = int(self._street_bet)
            min_open = sb_open if stack0 >= sb_open else max(1, stack0)
            self._set_root("openRaiseMinChips", int(min_open))
            self._set_root("openRaiseMaxChips", int(stack0))
        else:
            self._set_root("openRaiseMinChips", 0)
            self._set_root("openRaiseMaxChips", 0)

        if human_bb_wait:
            bb_inc = self._min_raise_increment_chips(self._big_blind, self._last_raise_increment)
            self._set_root("bbPreflopMinChips", int(max(1, bb_inc)))
            self._set_root("bbPreflopMaxChips", int(stack0))
            bb_can_raise = bool(
                bb_inc > 0
                and stack0 >= bb_inc
                and self._max_street_contrib() == self._preflop_blind_level
            )
            self._set_root("humanBbCanRaise", bb_can_raise)
        else:
            self._set_root("bbPreflopMinChips", 0)
            self._set_root("bbPreflopMaxChips", 0)
            self._set_root("humanBbCanRaise", False)

        self._set_root("humanStackChips", int(stack0))
        self._set_root("humanHandText", self._human_hand_line_for_ui())
        self._set_root("statusText", self._status_line())
        self._set_root("interactiveHuman", bool(self._interactive_human))
        self._set_root("botDecisionDelaySec", int(self._bot_decision_delay_sec))
        # Match C++ `game_ui_sync.cpp` (`streetPhase` on the table root).
        if self._showdown:
            self._set_root("streetPhase", "Showdown")
        elif 0 <= self._street < 4:
            self._set_root(
                "streetPhase",
                ("Preflop", "Flop", "Turn", "River")[self._street],
            )
        else:
            self._set_root("streetPhase", "Hand")

        cap = int(max(0, self._max_on_table_bb * self._big_blind))
        can_buy = bool(
            not self._in_progress
            and self._interactive_human
            and stack0 <= 0
            and cap > 0
            and int(self._seat_bankroll_total[hs]) >= self._effective_seat_buy_in_chips(hs)
        )
        self._set_root("humanCanBuyBackIn", can_buy)
        self._set_root("buyInChips", int(self._effective_seat_buy_in_chips(hs)))

        self.pot_changed.emit()
        self.sessionStatsChanged.emit()

        # Nudge the scene graph — some stacks/layouts batch repaints until the next polish without this.
        ri = self._root()
        if ri is not None and QQuickItem is not None and isinstance(ri, QQuickItem):
            try:
                ri.update()
                win = ri.window()
                if win is not None:
                    win.update()
            except Exception:
                pass

        # Match C++ `game::flush_ui()` after `sync_ui`: bounded event pump so Quick repaints/layouts run
        # without draining an entire zero-delay bot hand in one call (breaks tests and can recurse badly).
        if self._sync_root_depth == 1:
            app = QtCore.QCoreApplication.instance()
            if app is not None:
                app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 16)

    def _seat_display_name(self, seat: int) -> str:
        s = int(seat)
        if s == 0:
            return "You"
        if 1 <= s <= 5:
            return self._SEAT_BOT_NAMES[s - 1]
        return f"Seat {s}"

    def _format_showdown_line(self, winner_seats: list[int], hand_label: str) -> str:
        seats = [int(s) for s in winner_seats if int(s) >= 0]
        if not seats:
            return "Showdown"
        names = [self._seat_display_name(s) for s in seats]
        label = str(hand_label).strip() or "Showdown"
        if len(names) == 1:
            return f"{names[0]} wins — {label}"
        return f"{', '.join(names)} chop — {label}"

    def _status_line(self) -> str:
        # Short line like upstream table HUD: street, pot, actor (no long em-dash phrases).
        if self._showdown:
            return self._showdown_status_text or "Showdown"
        streets = ["Preflop", "Flop", "Turn", "River"]
        st = streets[self._street] if 0 <= self._street < 4 else "Hand"
        pot = int(sum(self._contrib_total))
        if self._acting_seat < 0 and not self._bb_preflop_waiting:
            return f"{st} ${pot}"
        hs = int(self.HUMAN_HERO_SEAT)
        who = (
            "You"
            if (self._acting_seat == hs or self._bb_preflop_waiting) and self._interactive_human
            else self._seat_display_name(self._acting_seat)
        )
        return f"{st} ${pot} {who}"

    def _human_hand_line_for_ui(self) -> str:
        hs = int(self.HUMAN_HERO_SEAT)
        # Show hero hole cards in the HUD whenever dealt in (including “Play as bot” autoplay).
        if not self._in_hand[hs] or self._human_sitting_out:
            return ""
        h0, h1 = self._hole[hs]
        if h0[0] < 2 or h1[0] < 2:
            return ""
        return f"{self._pretty_card(h0)} {self._pretty_card(h1)}".strip()

    def _compute_pot_slices(self):
        # Create main/side pot slices from contributions.
        contrib = [c if self._in_hand[i] or c > 0 else 0 for i, c in enumerate(self._contrib_total)]
        levels = sorted({c for c in contrib if c > 0})
        out = []
        prev = 0
        for lvl in levels:
            eligible = [i for i, c in enumerate(contrib) if c >= lvl]
            slice_amt = (lvl - prev) * len(eligible)
            if slice_amt > 0:
                out.append({"amount": int(slice_amt), "eligible": eligible})
            prev = lvl
        return out

    # --- Engine core ---
    def _reset_street(self) -> None:
        self._street_put_in = [0] * 6
        self._to_call = 0
        self._last_raiser = -1
        self._street_action_text = [""] * 6
        if self._street >= 1:
            self._last_raise_increment = int(self._big_blind)

    def _post_blinds(self) -> None:
        self._bet(self._sb_seat, self._small_blind, label="SB")
        self._bet(self._bb_seat, self._big_blind, label="BB")
        self._to_call = max(self._street_put_in)
        sb_amt = int(self._street_put_in[self._sb_seat])
        bb_amt = int(self._street_put_in[self._bb_seat])
        self._preflop_blind_level = int(max(sb_amt, bb_amt))
        self._last_raise_increment = int(self._big_blind)
        self._bb_preflop_option_open = True

    def _log_table_action(self, seat: int, kind_label: str, chips: int, *, is_blind: bool = False) -> None:
        self._hand_action_seq += 1
        self._hand_actions.append(
            {
                "seq": int(self._hand_action_seq),
                "street": int(self._street),
                "seat": int(seat),
                "kindLabel": str(kind_label),
                "isBlind": bool(is_blind),
                "chips": int(chips),
            }
        )

    def _bet(self, seat: int, amount: int, label: str = "") -> None:
        if not self._in_hand[seat]:
            return
        amt = max(0, min(int(amount), int(self._seat_buy_in[seat])))
        self._seat_buy_in[seat] -= amt
        self._street_put_in[seat] += amt
        self._contrib_total[seat] += amt
        if label:
            blind = label in ("SB", "BB")
            # Seat HUD line (`seatStreetActions`): amounts for call / raise / blinds posted.
            if amt > 0 and label in ("Call", "Raise", "SB", "BB"):
                self._street_action_text[seat] = f"{label} ${int(amt)}"
            else:
                self._street_action_text[seat] = label
            self._log_table_action(seat, label, int(amt), is_blind=blind)
        # Pot / stacks must refresh as soon as chips move; `_advance_after_action` can branch without
        # another sync until the next actor (or callers assumed UI updated elsewhere).
        self._sync_root()

    def _next_seat_clockwise(self, start: int, *, need_chips: bool) -> int:
        """Next seat from `start` among participating players still in the hand.

        `need_chips=True` skips all-in (0-stack) players so betting does not deadlock when nobody
        can put more money in but `_all_called_or_folded` is still false (short all-ins).
        """
        for k in range(1, 7):
            s = (start + k) % 6
            if not (self._seat_participating[s] and self._in_hand[s]):
                continue
            if need_chips and self._seat_buy_in[s] <= 0:
                continue
            return s
        return -1

    def _next_live_stack_seat(self, start: int) -> int:
        """Next clockwise seat after `start` that will play this hand (participating + table chips).

        Used for button / blind placement. Must not depend on `_in_hand`, which still reflects
        the previous hand's folds until `beginNewHand` assigns a fresh dealing mask.
        """
        for k in range(1, 7):
            s = (int(start) + k) % 6
            if self._seat_participating[s] and self._seat_buy_in[s] > 0:
                return s
        return -1

    def _begin_betting_round(self, first: int) -> None:
        if first < 0:
            self._acting_seat = -1
            self._decision_seconds_left = 0
            self._decision_timer.stop()
            # Do not leave `_in_progress` with no actor — `_tick_decision` will never fire
            # `_auto_action_timeout` when `acting_seat < 0` (stall with a live hand).
            if self._in_progress:
                alive = self._remaining_players()
                if len(alive) <= 1:
                    self._award_uncontested(alive[0] if alive else -1)
                    return
                if self._all_called_or_folded():
                    if self._maybe_handle_bb_preflop_option():
                        return
                    self._advance_street_or_showdown()
                    return
                nxt = self._next_seat_clockwise(self._bb_seat, need_chips=True)
                if nxt < 0:
                    nxt = self._next_seat_clockwise(self._bb_seat, need_chips=False)
                if nxt >= 0:
                    self._acting_seat = nxt
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
        self._acting_seat = first
        self._decision_seconds_left = 20
        self._human_more_time_available = True
        self._decision_timer.start()
        self._sync_root()
        self._maybe_schedule_bot()

    def _all_called_or_folded(self) -> bool:
        # Everyone remaining has put in to_call (or is all-in with less).
        for s in range(6):
            if not (self._seat_participating[s] and self._in_hand[s]):
                continue
            if self._seat_buy_in[s] == 0:
                continue  # all-in
            if self._street_put_in[s] < self._to_call:
                return False
        return True

    def _remaining_players(self) -> list[int]:
        return [s for s in range(6) if self._seat_participating[s] and self._in_hand[s]]

    def _distribute_showdown_side_pots(self) -> list[int]:
        """Side-pot–aware NLHE distribution by contribution tiers (best hand per slice among contenders)."""
        contrib = [int(self._contrib_total[i]) for i in range(6)]
        awards = [0] * 6
        alive = self._remaining_players()
        if not alive:
            return awards
        idxs = [i for i in range(6) if contrib[i] > 0]
        if not idxs:
            return awards
        levels = sorted({contrib[i] for i in idxs})
        prev = 0
        for lvl in levels:
            participants = [i for i in range(6) if contrib[i] >= lvl]
            pot_slice = (lvl - prev) * len(participants)
            contenders = [i for i in participants if self._in_hand[i]]
            prev = lvl
            if pot_slice <= 0:
                continue
            if not contenders:
                # Dead money: assign to lowest-index survivor (rare edge).
                if alive:
                    awards[min(alive)] += pot_slice
                continue
            best = None
            win_subset: list[int] = []
            for s in contenders:
                rk = self._best_rank_7(list(self._board) + list(self._hole[s]))
                if best is None or rk > best:
                    best = rk
                    win_subset = [s]
                elif rk == best:
                    win_subset.append(s)
            win_subset.sort()
            share, rem = divmod(int(pot_slice), len(win_subset))
            for j, w in enumerate(win_subset):
                awards[w] += share + (1 if j < rem else 0)
        return awards

    @staticmethod
    def _rank_tuple_display_name(rank: tuple) -> str:
        if not rank:
            return ""
        cat = int(rank[0])
        if 0 <= cat < len(_HAND_CATEGORY_DISPLAY_NAMES):
            return _HAND_CATEGORY_DISPLAY_NAMES[cat]
        return "Hand"

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
        board_display = " ".join(self._pretty_card(c) for c in self._board if c[0] >= 2).strip()
        board_assets = [self._card_asset(c) for c in self._board if c[0] >= 2]
        n_players = int(self._hand_num_dealt) if self._hand_num_dealt > 0 else sum(
            1 for i in range(6) if self._seat_participating[i]
        )
        aw = list(pot_awards) if pot_awards is not None else [0] * 6
        players_detail: list[dict[str, Any]] = []
        for s in range(6):
            if self._hand_num_dealt > 0:
                if s >= len(self._hand_dealt_mask) or not self._hand_dealt_mask[s]:
                    continue
            elif not self._seat_participating[s]:
                continue
            h0, h1 = self._hole[s]
            players_detail.append(
                {
                    "seat": int(s),
                    "contrib": int(self._contrib_total[s]),
                    "won": int(aw[s]),
                    "hole_svg1": self._card_asset(h0),
                    "hole_svg2": self._card_asset(h1),
                    "total_bankroll": int(self._seat_bankroll_total[s] + self._seat_buy_in[s]),
                }
            )
        board_codes: list[int] = []
        for i in range(5):
            if i < len(self._board):
                r, s = self._board[i]
                board_codes.append(_card_tuple_to_wire_int((r, s)))
            else:
                board_codes.append(-1)
        payload: dict[str, Any] = {
            "startedMs": int(self._hand_log_started_ms),
            "endedMs": ended,
            "numPlayers": int(n_players),
            "boardDisplay": board_display,
            "boardAssets": board_assets,
            "boardCardCodes": board_codes,
            "winners": [int(x) for x in winners],
            "sbSize": int(self._small_blind),
            "bbSize": int(self._big_blind),
            "buttonSeat": int(self._button_seat),
            "sbSeat": int(self._sb_seat),
            "bbSeat": int(self._bb_seat),
            "sessionKey": 0,
            "actions": list(self._hand_actions),
            "playersDetail": players_detail,
            "totalHandWonChips": int(sum(aw)),
        }
        wh = str(winning_hand_name or "").strip()
        if wh:
            payload["winningHandName"] = wh
        self._hand_history.record_completed_hand(payload)
        # Snapshot stacks for session stats.
        self._bankroll_snapshots_ms.append(int(ended))
        self._bankroll_snapshot_table.append([int(x) for x in self._seat_buy_in])
        self._bankroll_snapshot_total.append(
            [int(self._seat_bankroll_total[i] + self._seat_buy_in[i]) for i in range(6)]
        )
        self._save_game_state_kv()

    def _advance_street_or_showdown(self) -> None:
        alive = self._remaining_players()
        if len(alive) <= 1:
            self._award_uncontested(alive[0] if alive else -1)
            return

        # Deal next street
        if self._street == 0:
            self._board.extend([self._deck.pop(), self._deck.pop(), self._deck.pop()])
            self._street = 1
        elif self._street == 1:
            self._board.append(self._deck.pop())
            self._street = 2
        elif self._street == 2:
            self._board.append(self._deck.pop())
            self._street = 3
        else:
            self._do_showdown()
            return

        self._reset_street()
        # First to act postflop is left of button among alive (SB in 6-max), but simplify:
        first = self._next_seat_clockwise(self._button_seat, need_chips=True)
        if first < 0:
            first = self._next_seat_clockwise(self._button_seat, need_chips=False)
        if first < 0 and len(self._remaining_players()) >= 2:
            # Everyone still in the hand is all-in — no further betting; run out board.
            self._decision_timer.stop()
            self._acting_seat = -1
            self._decision_seconds_left = 0
            while self._street < 3:
                if self._street == 0:
                    self._board.extend([self._deck.pop(), self._deck.pop(), self._deck.pop()])
                    self._street = 1
                elif self._street == 1:
                    self._board.append(self._deck.pop())
                    self._street = 2
                elif self._street == 2:
                    self._board.append(self._deck.pop())
                    self._street = 3
            self._do_showdown()
            return
        self._begin_betting_round(first)

    def _award_uncontested(self, winner: int) -> None:
        pot = sum(self._contrib_total)
        aw = [0] * 6
        if winner >= 0:
            aw[winner] = pot
            self._seat_buy_in[winner] += pot
        self._showdown = True
        self._acting_seat = -1
        self._decision_timer.stop()
        self._decision_seconds_left = 0
        win_list = [int(winner)] if winner >= 0 else []
        self._showdown_status_text = (
            self._format_showdown_line(win_list, "Uncontested") if winner >= 0 else "Showdown"
        )
        self._in_progress = False
        self._record_completed_hand(win_list, aw, winning_hand_name="Uncontested")
        self._sync_root()
        self._schedule_next_hand_if_idle()

    @staticmethod
    def _hand_rank_5(cards5: list[tuple[int, int]]):
        # Return sortable tuple: (category, tiebreakers...)
        ranks = sorted([r for r, _ in cards5], reverse=True)
        suits = [s for _, s in cards5]
        counts = {r: ranks.count(r) for r in set(ranks)}
        by_count = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
        is_flush = len(set(suits)) == 1
        uniq = sorted(set(ranks), reverse=True)
        is_straight = len(uniq) == 5 and (uniq[0] - uniq[4] == 4)
        # Wheel A-5
        if set(ranks) == {14, 5, 4, 3, 2}:
            is_straight = True
            uniq = [5, 4, 3, 2, 1]

        if is_straight and is_flush:
            return (8, uniq[0])
        if by_count[0][1] == 4:
            four = by_count[0][0]
            kicker = max(r for r in ranks if r != four)
            return (7, four, kicker)
        if by_count[0][1] == 3 and by_count[1][1] == 2:
            return (6, by_count[0][0], by_count[1][0])
        if is_flush:
            return (5, *ranks)
        if is_straight:
            return (4, uniq[0])
        if by_count[0][1] == 3:
            trip = by_count[0][0]
            kickers = sorted([r for r in ranks if r != trip], reverse=True)
            return (3, trip, *kickers)
        if by_count[0][1] == 2 and by_count[1][1] == 2:
            p1, p2 = by_count[0][0], by_count[1][0]
            kicker = max(r for r in ranks if r not in (p1, p2))
            hi, lo = max(p1, p2), min(p1, p2)
            return (2, hi, lo, kicker)
        if by_count[0][1] == 2:
            pair = by_count[0][0]
            kickers = sorted([r for r in ranks if r != pair], reverse=True)
            return (1, pair, *kickers)
        return (0, *ranks)

    def _best_rank_7(self, cards7: list[tuple[int, int]]):
        best = None
        for comb in itertools.combinations(cards7, 5):
            r = self._hand_rank_5(list(comb))
            if best is None or r > best:
                best = r
        return best or (0,)

    def _rank_tuple_to_strength_01(self, rank: tuple) -> float:
        """Map `_hand_rank_5` tuple to [0,1] like upstream `hand_eval::score_to_01`."""
        if not rank:
            return 0.0
        cat = int(rank[0]) / 8.0
        tail = list(rank[1:])
        if not tail:
            return min(1.0, cat * 0.72)
        kick = 0.0
        for i, v in enumerate(tail[:7], start=1):
            kick += float(v) / (14.0 * float(i))
        kick /= 7.0
        return min(1.0, cat * 0.72 + kick * 0.28)

    def _hand_strength_01_seat(self, seat: int) -> float:
        """Upstream `hand_strength_01_cards` — strength of best 5 of hole + board."""
        h0, h1 = self._hole[seat]
        if h0[0] < 2 or h1[0] < 2:
            return 0.0
        cards7 = [h0, h1] + [c for c in self._board if c[0] >= 2]
        if len(cards7) < 2:
            return 0.0
        return self._rank_tuple_to_strength_01(self._best_rank_7(cards7))

    def _preflop_chart_weights(self, seat: int) -> tuple[float, float, float]:
        """Layer 0/1/2 matrix weights at this hole card (call / raise / bet), each in [0,1]."""
        h0, h1 = self._hole[seat]
        row, col = self._hole_to_grid_row_col(h0, h1)
        out: list[float] = []
        for layer in range(3):
            g = self._range_grid.get((int(seat), layer))
            if g is None or len(g) != 13 * 13:
                out.append(1.0)
                continue
            if max(g) <= 0:
                out.append(1.0)
                continue
            w = float(g[row * 13 + col])
            if w > 1.0:
                w = min(1.0, w / 100.0)
            out.append(max(0.0, min(1.0, w)))
        return (out[0], out[1], out[2])

    def _preflop_play_metric(self, seat: int) -> float:
        """Upstream `play_weight_cards` — max weight across the three range layers."""
        a, b, c = self._preflop_chart_weights(seat)
        return max(a, b, c)

    def _do_showdown(self) -> None:
        alive = self._remaining_players()
        if not alive:
            self._award_uncontested(-1)
            return
        ranks = {}
        for s in alive:
            cards7 = list(self._board) + list(self._hole[s])
            ranks[s] = self._best_rank_7(cards7)
        best = max(ranks.values())
        winners = [s for s, r in ranks.items() if r == best]
        wh_name = self._rank_tuple_display_name(best)
        awards = self._distribute_showdown_side_pots()
        for s in range(6):
            self._seat_buy_in[s] += awards[s]
        self._showdown = True
        self._acting_seat = -1
        self._decision_timer.stop()
        self._decision_seconds_left = 0
        win_disp = sorted([s for s in range(6) if awards[s] > 0])
        if not win_disp:
            win_disp = list(winners)
        self._showdown_status_text = self._format_showdown_line(win_disp, wh_name)
        self._in_progress = False
        self._record_completed_hand(win_disp, awards, winning_hand_name=wh_name)
        self._sync_root()
        self._schedule_next_hand_if_idle()

    # --- Decision handling ---
    def _tick_decision(self) -> None:
        # Never stop the decision timer solely because actingSeat is -1 while a hand is still
        # in progress — that stranded games after the first timeout. Idle ends stop elsewhere.
        if self._acting_seat < 0:
            if not self._in_progress:
                self._decision_timer.stop()
            return
        self._decision_seconds_left = max(0, self._decision_seconds_left - 1)
        self._sync_root()
        if self._decision_seconds_left <= 0:
            self._auto_action_timeout()

    def _auto_action_timeout(self) -> None:
        if self._bb_preflop_waiting:
            self._finish_bb_preflop_check()
            return
        seat = self._acting_seat
        if seat < 0:
            return
        # Avoid acting twice if `_bot_timer` fires after the decision clock (both can be armed for bots).
        self._bot_timer.stop()
        # Hero seat with interactive HUD uses fold/check timeouts; every other seat is engine‑bot logic.
        # Relying only on `_bot_timer` left the table stuck when that timer never fired (seen on some setups).
        if seat != self.HUMAN_HERO_SEAT or not self._interactive_human:
            self._bot_act()
            return
        need = max(0, self._to_call - self._street_put_in[seat])
        if need > 0:
            self._fold(seat)
        else:
            self._check(seat)

    def _maybe_schedule_bot(self) -> None:
        s = self._acting_seat
        if s < 0:
            return
        if self._bb_preflop_waiting:
            return
        is_human = s == self.HUMAN_HERO_SEAT and self._interactive_human
        if is_human:
            return
        self._bot_timer.stop()
        delay_ms = int(max(0, self._bot_decision_delay_sec) * 1000) if self._bot_slow_actions else 0
        self._bot_timer.start(delay_ms)

    def _recover_stale_acting_seat(self) -> None:
        """If `acting_seat` points at a folded/out player, move action or end the street (timer stall fix)."""
        s = self._acting_seat
        if s < 0 or not self._in_progress:
            return
        nxt = self._next_seat_clockwise(s, need_chips=True)
        if nxt < 0:
            nxt = self._next_seat_clockwise(s, need_chips=False)
        if nxt >= 0:
            self._acting_seat = nxt
            self._decision_seconds_left = 20
            self._human_more_time_available = True
            self._decision_timer.start()
            self._sync_root()
            self._maybe_schedule_bot()
            return
        if self._all_called_or_folded():
            if self._maybe_handle_bb_preflop_option():
                return
            self._advance_street_or_showdown()
            return
        alive = self._remaining_players()
        if len(alive) <= 1:
            self._award_uncontested(alive[0] if alive else -1)

    def _bot_act(self) -> None:
        s = self._acting_seat
        if s < 0:
            return
        if not self._in_hand[s]:
            QtCore.qWarning("PokerGame: _bot_act with folded/out acting seat; recovering.")
            self._recover_stale_acting_seat()
            return

        idx = int(self._seat_strategy_idx[s]) % bot_strategy.STRATEGY_COUNT
        p = self._seat_params[s]
        need = max(0, self._to_call - self._street_put_in[s])
        inc = self._min_raise_increment_chips(self._big_blind, self._last_raise_increment)
        rng = self._rng

        # AlwaysCall (test): never fold when calling is possible; never raise.
        if idx == 0:
            if need > 0:
                self._call(s)
            else:
                self._check(s)
            return

        if self._street == 0:
            pw = self._preflop_play_metric(s)
            rw = self._preflop_chart_weights(s)[1]
        else:
            pw = self._hand_strength_01_seat(s)
            rw = pw

        if need > 0:
            if self._street == 0:
                if not bot_strategy.bot_preflop_continue_p(p, pw, rng):
                    self._fold(s)
                    return
            else:
                if not bot_strategy.bot_postflop_continue_p(p, pw, rng):
                    self._fold(s)
                    return
            try_raise = bot_strategy.bot_wants_raise_after_continue_p(p, pw, rng)
            new_level = int(self._to_call + inc)
            chips_needed = new_level - int(self._street_put_in[s])
            if try_raise and chips_needed > 0 and chips_needed <= self._seat_buy_in[s]:
                gate = True
                if self._street == 0:
                    gate = bot_strategy.rng_passes_layer_gate(rw, pw, rng)
                if gate:
                    self._raise_to(s, new_level)
                    return
            self._call(s)
            return

        # need == 0: check or open-raise / limp logic
        if self._street == 0:
            if not bot_strategy.bot_preflop_continue_p(p, pw, rng):
                self._check(s)
                return
            try_raise = bot_strategy.bot_wants_raise_after_continue_p(p, pw, rng)
            if try_raise and inc > 0 and self._seat_buy_in[s] >= inc:
                if bot_strategy.rng_passes_layer_gate(rw, pw, rng):
                    self._raise_to(s, self._to_call + self._big_blind)
                    return
            self._check(s)
            return

        if not bot_strategy.bot_wants_open_bet_postflop_p(p, pw, rng):
            self._check(s)
            return
        _, _, bet_w = self._preflop_chart_weights(s)
        play_triple = self._preflop_play_metric(s)
        if not bot_strategy.rng_passes_layer_gate(bet_w, play_triple, rng):
            self._check(s)
            return
        open_amt = min(int(self._street_bet), int(self._seat_buy_in[s]))
        if open_amt <= 0:
            self._check(s)
            return
        self._raise_to(s, int(self._street_put_in[s]) + open_amt)

    def _fold(self, seat: int) -> None:
        self._in_hand[seat] = False
        self._street_action_text[seat] = "Fold"
        self._log_table_action(seat, "Fold", 0)
        self._advance_after_action()

    def _check(self, seat: int) -> None:
        self._street_action_text[seat] = "Check"
        self._log_table_action(seat, "Check", 0)
        self._advance_after_action()

    def _call(self, seat: int) -> None:
        need = max(0, self._to_call - self._street_put_in[seat])
        self._bet(seat, need, label="Call" if need > 0 else "Check")
        self._advance_after_action()

    def _raise_to(self, seat: int, to_amount: int) -> None:
        to_amount = int(to_amount)
        if to_amount <= self._to_call:
            self._call(seat)
            return
        prev_max = int(self._to_call)
        need = max(0, to_amount - self._street_put_in[seat])
        self._bet(seat, need, label="Raise")
        new_contrib = int(self._street_put_in[seat])
        self._to_call = max(self._to_call, new_contrib)
        if new_contrib > prev_max:
            self._last_raise_increment = int(new_contrib - prev_max)
        if self._street == 0 and self._to_call > self._preflop_blind_level:
            self._bb_preflop_option_open = False
        self._last_raiser = seat
        self._advance_after_action()

    def _advance_after_action(self) -> None:
        # If only one left, award and stop.
        alive = self._remaining_players()
        if len(alive) <= 1:
            self._award_uncontested(alive[0] if alive else -1)
            return
        if self._all_called_or_folded():
            if self._maybe_handle_bb_preflop_option():
                return
            self._advance_street_or_showdown()
            return
        nxt = self._next_seat_clockwise(self._acting_seat, need_chips=True)
        if nxt < 0:
            if self._maybe_handle_bb_preflop_option():
                return
            self._advance_street_or_showdown()
            return
        self._acting_seat = nxt
        self._decision_seconds_left = 20
        self._human_more_time_available = True
        self._decision_timer.start()
        self._sync_root()
        self._maybe_schedule_bot()

    def _maybe_handle_bb_preflop_option(self) -> bool:
        """BB preflop branch: returns True if caller must not advance street yet."""
        if self._street != 0:
            return False
        mx = self._max_street_contrib()
        if mx != self._preflop_blind_level or not self._bb_preflop_option_open:
            return False
        self._bb_preflop_option_open = False
        bb = int(self._bb_seat)
        if not (0 <= bb < 6 and self._in_hand[bb]):
            return False
        hs = int(self.HUMAN_HERO_SEAT)
        if bb == hs and self._interactive_human and self._root() is not None:
            if self._seat_buy_in[hs] <= 0:
                return False
            self._bb_preflop_waiting = True
            self._acting_seat = hs
            self._decision_seconds_left = 20
            self._human_more_time_available = True
            self._decision_timer.start()
            self._sync_root()
            return True
        return self._bot_bb_preflop_option(bb)

    def _finish_bb_preflop_check(self) -> None:
        self._bb_preflop_waiting = False
        self._decision_timer.stop()
        self._decision_seconds_left = 0
        self._human_more_time_available = False
        bb = int(self._bb_seat)
        if 0 <= bb < 6:
            self._street_action_text[bb] = "Check"
            self._log_table_action(bb, "Check", 0)
        # Keep actingSeat until the next street begins so _tick_decision does not stop the
        # clock while we are between streets (would strand the hand with no timer).
        self._sync_root()
        self._advance_street_or_showdown()

    def _bb_preflop_add_raise(self, chips_to_add: int) -> None:
        bb = int(self._bb_seat)
        if not (0 <= bb < 6 and bb == self.HUMAN_HERO_SEAT):
            return
        inc = self._min_raise_increment_chips(self._big_blind, self._last_raise_increment)
        if inc <= 0 or self._max_street_contrib() != self._preflop_blind_level or self._seat_buy_in[bb] <= 0:
            self._finish_bb_preflop_check()
            return
        c = int(max(inc, min(int(chips_to_add), int(self._seat_buy_in[bb]))))
        if c < inc:
            self._finish_bb_preflop_check()
            return
        self._bet(bb, c, label="Raise")
        self._last_raise_increment = int(c)
        self._to_call = max(self._to_call, self._street_put_in[bb])
        self._bb_preflop_option_open = False
        self._bb_preflop_waiting = False
        self._decision_timer.stop()
        self._decision_seconds_left = 0
        self._human_more_time_available = False
        self._sync_root()
        first = self._next_seat_clockwise(bb, need_chips=True)
        if first < 0:
            first = self._next_seat_clockwise(bb, need_chips=False)
        self._begin_betting_round(first)

    def _bot_bb_preflop_option(self, bb: int) -> bool:
        if self._seat_buy_in[bb] <= 0:
            return False
        inc = self._min_raise_increment_chips(self._big_blind, self._last_raise_increment)
        idx = int(self._seat_strategy_idx[bb]) % bot_strategy.STRATEGY_COUNT
        p = self._seat_params[bb]
        pw = self._preflop_play_metric(bb)
        rw = self._preflop_chart_weights(bb)[1]

        self._decision_timer.stop()

        if idx == 0:
            self._street_action_text[bb] = "Check"
            self._log_table_action(bb, "Check", 0)
            self._sync_root()
            return False

        raise_ok = bot_strategy.bot_bb_check_or_raise_p(p, pw, self._rng)
        if (
            raise_ok
            and inc > 0
            and self._seat_buy_in[bb] >= inc
            and self._max_street_contrib() == self._preflop_blind_level
            and bot_strategy.rng_passes_layer_gate(rw, pw, self._rng)
        ):
            self._bet(bb, inc, label="Raise")
            self._last_raise_increment = int(inc)
            self._to_call = max(self._to_call, self._street_put_in[bb])
            self._sync_root()
            first = self._next_seat_clockwise(bb, need_chips=True)
            if first < 0:
                first = self._next_seat_clockwise(bb, need_chips=False)
            self._begin_betting_round(first)
            return True
        self._street_action_text[bb] = "Check"
        self._log_table_action(bb, "Check", 0)
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
        return int(self._range_revision)

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
        if self._in_progress and self._root() is not None:
            self._sync_root()
            return
        self._bootstrap_playable_table()
        self._showdown = False
        self._showdown_status_text = ""
        self._bb_preflop_waiting = False
        self._human_more_time_available = False
        # Who is eligible this hand (do not use `_in_hand` yet — it still holds last hand's folds).
        # Human excluded when sitting out; seats 1–5 respect Setup toggles only.
        dealing = self._dealing_mask_for_new_hand()
        n_live = int(sum(dealing))
        self._hand_dealt_mask = [bool(dealing[i]) for i in range(6)]
        self._hand_num_dealt = int(n_live)
        if n_live < 2:
            self._in_progress = False
            self._acting_seat = -1
            self._decision_timer.stop()
            self._decision_seconds_left = 0
            if self._root() is not None:
                self._set_root(
                    "statusText",
                    "Need at least two players in the hand. Sit in to play or add players.",
                )
            self._sync_root()
            return

        self._hand_seq += 1
        self._hand_log_started_ms = int(time.time() * 1000)
        self._hand_action_seq = 0
        self._hand_actions = []
        self._in_progress = True
        self._street = 0

        # Move button clockwise among seats that are actually playing this hand.
        nxt_btn = self._next_live_stack_seat(self._button_seat)
        if nxt_btn >= 0:
            self._button_seat = nxt_btn
        else:
            self._button_seat = next(i for i in range(6) if dealing[i])

        if n_live == 2:
            # Heads-up: BTN posts SB; BB acts first preflop.
            self._sb_seat = int(self._button_seat)
            self._bb_seat = int(self._next_live_stack_seat(self._button_seat))
            if self._bb_seat < 0:
                self._bb_seat = int(self._button_seat)
        else:
            self._sb_seat = int(self._next_live_stack_seat(self._button_seat))
            if self._sb_seat < 0:
                self._sb_seat = int(self._button_seat)
            self._bb_seat = int(self._next_live_stack_seat(self._sb_seat))
            if self._bb_seat < 0:
                self._bb_seat = int(self._next_live_stack_seat(self._button_seat))

        self._deck = self._new_shuffled_deck()
        self._board = []
        self._hole = [[self._deck.pop(), self._deck.pop()] for _ in range(6)]

        self._in_hand = dealing
        self._street_put_in = [0] * 6
        self._contrib_total = [0] * 6
        self._reset_street()
        self._post_blinds()

        if n_live == 2:
            first = int(self._bb_seat)
        else:
            first = self._next_seat_clockwise(self._bb_seat, need_chips=True)
            if first < 0:
                first = self._next_seat_clockwise(self._bb_seat, need_chips=False)
        if first < 0:
            for s in range(6):
                if dealing[s]:
                    first = int(s)
                    break
        self._begin_betting_round(first)

    # --- Range editor (Setup) persistence (KV blob) ---
    def _ensure_range_grid(self, seat: int, layer: int) -> list[float]:
        k = (int(seat), int(layer))
        if k not in self._range_grid:
            # Default “play everything” until the user edits (matches an empty matrix being full range).
            self._range_grid[k] = [1.0] * (13 * 13)
        return self._range_grid[k]

    @staticmethod
    def _hole_to_grid_row_col(h0: tuple[int, int], h1: tuple[int, int]) -> tuple[int, int]:
        """Map hole cards to (row,col) for the 13×13 matrix (same convention as `RangeGrid.qml`)."""
        r1, s1 = int(h0[0]), int(h0[1])
        r2, s2 = int(h1[0]), int(h1[1])
        if r1 < 2 or r2 < 2:
            return (0, 0)
        # Row/col 0 = Ace … 12 = Two (`RangeGrid.qml` rankLabels).
        i1, i2 = 14 - r1, 14 - r2
        if i1 == i2:
            return (i1, i1)
        if s1 == s2:
            a, b = (i1, i2) if i1 < i2 else (i2, i1)
            return (a, b)  # row < col → suited
        lo, hi = min(i1, i2), max(i1, i2)
        return (hi, lo)  # row > col → offsuit

    def _preflop_range_play_weight(self, seat: int) -> float:
        """Layer 0 matrix weight at this hole card (legacy name; same as upstream call chart)."""
        return self._preflop_chart_weights(seat)[0]

    def _ranges_bundle(self) -> dict[str, Any]:
        out: dict[str, Any] = {"text": {}, "grid": {}}
        for (seat, layer), txt in self._range_text.items():
            out["text"].setdefault(str(seat), {})[str(layer)] = txt
        for (seat, layer), gr in self._range_grid.items():
            out["grid"].setdefault(str(seat), {})[str(layer)] = list(gr)
        return out

    def _apply_ranges_bundle(self, m: Any) -> None:
        if not isinstance(m, dict):
            return
        self._range_text.clear()
        self._range_grid.clear()
        tx = m.get("text")
        if isinstance(tx, dict):
            for sk, layers in tx.items():
                if not isinstance(layers, dict):
                    continue
                try:
                    si = int(sk)
                except Exception:
                    continue
                for lk, val in layers.items():
                    try:
                        li = int(lk)
                    except Exception:
                        continue
                    self._range_text[(si, li)] = str(val) if val is not None else ""
        gd = m.get("grid")
        if isinstance(gd, dict):
            for sk, layers in gd.items():
                if not isinstance(layers, dict):
                    continue
                try:
                    si = int(sk)
                except Exception:
                    continue
                for lk, vals in layers.items():
                    try:
                        li = int(lk)
                    except Exception:
                        continue
                    if isinstance(vals, list) and len(vals) == 13 * 13:
                        self._range_grid[(si, li)] = [float(x) for x in vals]
                    elif isinstance(vals, list):
                        g = [0.0] * (13 * 13)
                        for i, x in enumerate(vals[:169]):
                            g[i] = float(x)
                        self._range_grid[(si, li)] = g

    def _persist_ranges_kv(self) -> None:
        if self._db is None:
            return
        self._db.kv_set_json(_RANGES_KV, self._ranges_bundle())

    def _load_ranges_from_kv(self) -> None:
        if self._db is None:
            return
        self._apply_ranges_bundle(self._db.kv_get_json(_RANGES_KV))

    def _game_state_dict(self) -> dict[str, Any]:
        return {
            "sb": int(self._small_blind),
            "bb": int(self._big_blind),
            "streetBet": int(self._street_bet),
            "maxTableBb": int(self._max_on_table_bb),
            "startStack": int(self._start_stack),
            "seatBuyIn": [int(x) for x in self._seat_buy_in],
            "seatBankrollTotal": [int(x) for x in self._seat_bankroll_total],
            "seatParticipating": [bool(x) for x in self._seat_participating],
            "interactiveHuman": bool(self._interactive_human),
            "humanSittingOut": bool(self._human_sitting_out),
            "botSlowActions": bool(self._bot_slow_actions),
            "winningHandShowMs": int(self._winning_hand_show_ms),
            "botDecisionDelaySec": int(self._bot_decision_delay_sec),
            "buttonSeat": int(self._button_seat),
            "seatStrategyIdx": [int(x) for x in self._seat_strategy_idx],
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
        self._small_blind = int(m.get("sb", self._small_blind))
        self._big_blind = int(m.get("bb", self._big_blind))
        self._street_bet = int(m.get("streetBet", self._street_bet))
        self._max_on_table_bb = int(m.get("maxTableBb", self._max_on_table_bb))
        self._start_stack = int(m.get("startStack", self._start_stack))
        sb = m.get("seatBuyIn")
        if isinstance(sb, list) and len(sb) == 6:
            self._seat_buy_in = [int(x) for x in sb]
        bt = m.get("seatBankrollTotal")
        if isinstance(bt, list) and len(bt) == 6:
            self._seat_bankroll_total = [int(x) for x in bt]
        sp = m.get("seatParticipating")
        if isinstance(sp, list) and len(sp) == 6:
            self._seat_participating = [bool(x) for x in sp]
            self._seat_participating[int(self.HUMAN_HERO_SEAT)] = True
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
            self._button_seat = int(m["buttonSeat"]) % 6
        ss = m.get("seatStrategyIdx")
        if isinstance(ss, list) and len(ss) == 6:
            self._seat_strategy_idx = [
                min(bot_strategy.STRATEGY_COUNT - 1, max(0, int(x))) for x in ss
            ]
        self._load_ranges_from_kv()
        for s in range(6):
            self._apply_strategy_params(s)
        self._bootstrap_playable_table()
        self._refresh_session_stats_baseline()
        self._range_revision += 1
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
        p = self._seat_params[seat] if 0 <= seat < 6 else _StrategyParams()
        return p.__dict__.copy()

    @QtCore.Slot(int, "QVariantMap")
    def setSeatStrategyParams(self, seat: int, m: dict):
        seat = int(seat)
        if not (0 <= seat < 6) or not m:
            return
        p = self._seat_params[seat]
        for k, v in dict(m).items():
            if hasattr(p, k):
                setattr(p, k, v)
        self._save_game_state_kv()

    @QtCore.Slot(result=bool)
    def gameInProgress(self) -> bool:
        return bool(self._in_progress)

    @QtCore.Slot()
    def applySeatBuyInsToStacks(self) -> None:
        cap = int(max(0, self._max_on_table_bb * self._big_blind))
        for s in range(6):
            if self._seat_buy_in[s] > cap:
                overflow = int(self._seat_buy_in[s] - cap)
                self._seat_buy_in[s] = cap
                self._seat_bankroll_total[s] += overflow
            if self._seat_buy_in[s] < 0:
                deficit = -int(self._seat_buy_in[s])
                self._seat_buy_in[s] = 0
                self._seat_bankroll_total[s] = max(0, int(self._seat_bankroll_total[s]) - deficit)

        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()
        self._save_game_state_kv()
        self._sync_root()
        if not self._in_progress and self._count_eligible_for_deal() >= 2:
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
        self._range_grid[(seat, layer)] = g
        self._range_text[(seat, layer)] = range_notation.format_grid_to_range(g)
        self._persist_ranges_kv()
        self._range_revision += 1
        self.rangeRevisionChanged.emit()
        return True

    @QtCore.Slot(int, int, result=str)
    def exportSeatRangeText(self, seat: int, layer: int) -> str:
        seat = int(seat)
        layer = int(layer)
        if not (0 <= seat < 6 and 0 <= layer < 3):
            return ""
        g = self._ensure_range_grid(seat, layer)
        return range_notation.format_grid_to_range(g)

    @QtCore.Slot(int, result=int)
    def seatStrategyIndex(self, seat: int) -> int:
        seat = int(seat)
        return int(self._seat_strategy_idx[seat]) if 0 <= seat < 6 else 0

    @QtCore.Slot()
    def factoryResetToDefaultsAndClearHistory(self) -> None:
        if self._hand_history is not None:
            self._hand_history.clearAll()
        if self._db is not None:
            self._db.kv_delete(_GAME_STATE_KV)
            self._db.kv_delete(_RANGES_KV)
        self._range_text.clear()
        self._range_grid.clear()
        self._seat_bankroll_total = [0] * 6
        self._seat_buy_in = [200] * 6
        self._seat_participating = [True] * 6
        self._small_blind = 1
        self._big_blind = 2
        self._street_bet = 4
        self._max_on_table_bb = 100
        self._start_stack = 200
        self._interactive_human = True
        self._human_sitting_out = False
        self._bot_slow_actions = True
        self._winning_hand_show_ms = 2500
        self._bot_decision_delay_sec = 2
        self._button_seat = 0
        self._seat_strategy_idx = [6] * 6
        for s in range(6):
            self._apply_strategy_preset(s)
        self._auto_hand_loop = True
        self.interactiveHumanChanged.emit()
        self.botSlowActionsChanged.emit()
        self.winningHandShowMsChanged.emit()
        self.botDecisionDelaySecChanged.emit()
        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()
        self._sync_root()

    @QtCore.Slot(result=int)
    def configuredSmallBlind(self) -> int:
        return int(self._small_blind)

    @QtCore.Slot(result=int)
    def configuredBigBlind(self) -> int:
        return int(self._big_blind)

    @QtCore.Slot(result=int)
    def configuredStreetBet(self) -> int:
        return int(self._street_bet)

    @QtCore.Slot(result=int)
    def configuredMaxOnTableBb(self) -> int:
        return int(self._max_on_table_bb)

    @QtCore.Slot(result=int)
    def configuredStartStack(self) -> int:
        return int(self._start_stack)

    @QtCore.Slot(result=int)
    def maxBuyInChips(self) -> int:
        cap = int(max(0, self._max_on_table_bb * self._big_blind))
        return cap if cap > 0 else int(self._start_stack)

    @QtCore.Slot(int, result=bool)
    def canBuyBackIn(self, seat: int) -> bool:
        seat = int(seat)
        hs = int(self.HUMAN_HERO_SEAT)
        if seat != hs or not self._interactive_human:
            return False
        if self._in_progress:
            return False
        if self._seat_buy_in[hs] > 0:
            return False
        cap = int(max(0, self._max_on_table_bb * self._big_blind))
        need = self._effective_seat_buy_in_chips(hs)
        return bool(cap > 0 and int(self._seat_bankroll_total[hs]) >= need)

    @QtCore.Slot(int, result=bool)
    def seatParticipating(self, seat: int) -> bool:
        seat = int(seat)
        return bool(self._seat_participating[seat]) if 0 <= seat < 6 else False

    @QtCore.Slot(int, bool)
    def setSeatParticipating(self, seat: int, on: bool) -> None:
        seat = int(seat)
        # Only mutates bot seats 1..5 (human seat is not toggled here).
        if not (1 <= seat < 6):
            return
        prev = bool(self._seat_participating[seat])
        self._seat_participating[seat] = bool(on)
        self._save_game_state_kv()
        if on and not prev and not self._in_progress and self._count_eligible_for_deal() >= 2:
            QtCore.QTimer.singleShot(0, self._maybe_begin_hand_after_setup_change)
        self._sync_root()

    @QtCore.Slot(int)
    def setMaxOnTableBb(self, bb: int) -> None:
        self._max_on_table_bb = int(bb)
        self._save_game_state_kv()

    @QtCore.Slot(int, int, int, int)
    def configure(self, sb: int, bb: int, street_bet: int, start_stack: int) -> None:
        self._small_blind = int(sb)
        self._big_blind = int(bb)
        self._street_bet = int(street_bet)
        self._start_stack = int(start_stack)
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
        return int(self._seat_bankroll_total[seat] + self._seat_buy_in[seat]) if 0 <= seat < 6 else 0

    @QtCore.Slot(int, int)
    def setSeatBankrollTotal(self, seat: int, v: int) -> None:
        seat = int(seat)
        if 0 <= seat < 6:
            total = max(0, int(v))
            on_table = max(0, int(self._seat_buy_in[seat]))
            self._seat_bankroll_total[seat] = max(0, total - on_table)
            self._stats_seq += 1
            self.statsSeqChanged.emit()
            self.sessionStatsChanged.emit()
            self._save_game_state_kv()

    @QtCore.Slot(int, result=int)
    def seatBuyIn(self, seat: int) -> int:
        seat = int(seat)
        return int(self._seat_buy_in[seat]) if 0 <= seat < 6 else 0

    @QtCore.Slot(int, int)
    def setSeatBuyIn(self, seat: int, v: int) -> None:
        seat = int(seat)
        if 0 <= seat < 6:
            want = max(0, int(v))
            cap = int(max(0, self._max_on_table_bb * self._big_blind))
            want = min(want, cap) if cap > 0 else want
            total = int(self._seat_buy_in[seat] + self._seat_bankroll_total[seat])
            want = min(want, total)
            self._seat_buy_in[seat] = want
            self._seat_bankroll_total[seat] = max(0, total - want)
            self._stats_seq += 1
            self.statsSeqChanged.emit()
            self.sessionStatsChanged.emit()
            self._save_game_state_kv()
            self._sync_root()

    @QtCore.Slot(int, int)
    def setSeatStrategy(self, seat: int, idx: int) -> None:
        seat = int(seat)
        if 0 <= seat < 6:
            self._seat_strategy_idx[seat] = min(
                bot_strategy.STRATEGY_COUNT - 1, max(0, int(idx))
            )
            self._apply_strategy_preset(seat)
            self._save_game_state_kv()
            self._persist_ranges_kv()
            self._sync_root()
            self._range_revision += 1
            self.rangeRevisionChanged.emit()

    @QtCore.Slot(int, result=str)
    def getStrategySummary(self, idx: int) -> str:
        return bot_strategy.strategy_summary(int(idx))

    @QtCore.Slot(int, result=str)
    def seatPositionLabel(self, seat: int) -> str:
        """BTN / SB / BB / UTG / HJ / CO for a seat — same rules as former QML `GameScreen.seatRole`."""
        n = 6
        seat = int(seat)
        btn = int(self._button_seat)
        sb = int(self._sb_seat)
        bb = int(self._bb_seat)
        part = list(self._seat_participating)

        def in_dealing_pool(idx: int) -> bool:
            if idx < 0 or idx >= n:
                return False
            if idx < len(part) and part[idx] is False:
                return False
            return True

        if bb < 0:
            return "—"
        if seat == btn:
            return "BTN"
        if sb >= 0 and seat == sb:
            return "SB"
        if bb >= 0 and seat == bb:
            return "BB"
        order: list[int] = []
        for k in range(1, n):
            s = (bb + k) % n
            if s != btn and s != sb and s != bb and in_dealing_pool(s):
                order.append(s)
        m = len(order)
        if m > 0 and seat == order[0]:
            return "UTG"
        if m >= 2 and seat == order[m - 1]:
            return "CO"
        if m >= 3 and seat == order[m - 2]:
            return "HJ"
        return "—"

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
        full = [1.0] * (13 * 13)
        for layer in range(3):
            self._range_grid[(seat, layer)] = list(full)
            self._range_text[(seat, layer)] = "*"
        self._persist_ranges_kv()
        self._range_revision += 1
        self.rangeRevisionChanged.emit()

    @QtCore.Slot(int, int, result="QVariantList")
    def getRangeGrid(self, seat: int, layer: int):
        seat = int(seat)
        layer = int(layer)
        if not (0 <= seat < 6 and 0 <= layer < 3):
            return [0.0] * (13 * 13)
        return list(self._ensure_range_grid(seat, layer))

    @QtCore.Slot(int, int, int, float, int)
    def setRangeCell(self, seat: int, row: int, col: int, w: float, layer: int) -> None:
        seat = int(seat)
        layer = int(layer)
        row = int(row)
        col = int(col)
        if not (0 <= seat < 6 and 0 <= layer < 3 and 0 <= row < 13 and 0 <= col < 13):
            return
        g = self._ensure_range_grid(seat, layer)
        g[row * 13 + col] = float(w)
        self._range_text[(seat, layer)] = range_notation.format_grid_to_range(g)
        self._persist_ranges_kv()
        self._range_revision += 1
        self.rangeRevisionChanged.emit()

    # Stats
    @QtCore.Slot(result="QVariantList")
    def seatRankings(self):
        rows: list[dict[str, Any]] = []
        for s in range(6):
            table = int(self._seat_buy_in[s])
            off = int(self._seat_bankroll_total[s])
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
        if not self._bb_preflop_waiting:
            return
        self._bb_preflop_add_raise(int(amount))

    @QtCore.Slot(int, int)
    def submitFacingAction(self, action: int, amount: int) -> None:
        if self._bb_preflop_waiting:
            return
        hs = int(self.HUMAN_HERO_SEAT)
        if self._acting_seat != hs:
            return
        act = int(action)
        if act == 0:
            self._human_more_time_available = False
            self._fold(hs)
        elif act == 1:
            self._human_more_time_available = False
            self._call(hs)
        else:
            need = max(0, self._to_call - self._street_put_in[hs])
            inc = self._min_raise_increment_chips(self._big_blind, self._last_raise_increment)
            stack0 = int(self._seat_buy_in[hs])
            chips = int(amount)
            if chips <= 0:
                chips = int(need + inc)
            chips = min(chips, stack0)
            target = int(self._street_put_in[hs] + chips)
            self._human_more_time_available = False
            self._raise_to(hs, target)

    @QtCore.Slot(bool, int)
    def submitCheckOrBet(self, check: bool, amount: int) -> None:
        if self._bb_preflop_waiting:
            if bool(check):
                self._finish_bb_preflop_check()
            return
        hs = int(self.HUMAN_HERO_SEAT)
        if self._acting_seat != hs:
            return
        if not bool(check):
            stack0 = int(self._seat_buy_in[hs])
            sb_open = int(self._street_bet)
            min_open = sb_open if stack0 >= sb_open else max(1, stack0)
            chips = int(max(min_open, min(int(amount), stack0)))
            self._bet(hs, chips, label="Raise")
            self._to_call = max(self._to_call, self._street_put_in[hs])
            self._last_raise_increment = int(chips)
            if self._street == 0 and self._to_call > self._preflop_blind_level:
                self._bb_preflop_option_open = False
            self._human_more_time_available = False
            self._advance_after_action()
            return
        need = max(0, self._to_call - self._street_put_in[hs])
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
            if self._bb_preflop_waiting:
                self._finish_bb_preflop_check()
            elif self._acting_seat == self.HUMAN_HERO_SEAT and self._interactive_human:
                hs = int(self.HUMAN_HERO_SEAT)
                need = max(0, self._to_call - self._street_put_in[hs])
                if need > 0:
                    self.submitFacingAction(0, 0)
                else:
                    self.submitFoldFromCheck()
        elif prev and not self._in_progress and self._count_eligible_for_deal() >= 2:
            QtCore.QTimer.singleShot(0, self._maybe_begin_hand_after_setup_change)
        self._save_game_state_kv()
        self._sync_root()

    @QtCore.Slot()
    def requestMoreTime(self) -> None:
        if not self._human_more_time_available:
            return
        if not (self._acting_seat == self.HUMAN_HERO_SEAT or self._bb_preflop_waiting):
            return
        self._human_more_time_available = False
        self._decision_seconds_left = min(int(self._decision_seconds_left) + 20, 120)
        self._sync_root()

    @QtCore.Slot()
    def submitFoldFromCheck(self) -> None:
        if self._bb_preflop_waiting:
            return
        hs = int(self.HUMAN_HERO_SEAT)
        if self._acting_seat != hs:
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
        if self._seat_buy_in[seat] > 0:
            return
        if self._seat_bankroll_total[seat] <= 0:
            return
        cap = int(max(0, self._max_on_table_bb * self._big_blind))
        add = min(int(self._seat_bankroll_total[seat]), cap if cap > 0 else int(self._seat_bankroll_total[seat]))
        if add <= 0:
            return
        self._seat_buy_in[seat] += add
        self._seat_bankroll_total[seat] -= add
        self._stats_seq += 1
        self.statsSeqChanged.emit()
        self.sessionStatsChanged.emit()
        self._save_game_state_kv()
        self._sync_root()
 
