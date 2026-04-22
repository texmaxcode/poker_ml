"""NLHE hand engine: street flow, action, blind option, timers (``PokerGame`` is Qt + persistence)."""

from __future__ import annotations

import time
from typing import Any

from PySide6 import QtCore

from texasholdemgym.backend.game_table import DealPositions, Table
from texasholdemgym.backend.poker_core.board_deal import deal_next_community_street, run_out_board_to_river
from texasholdemgym.backend.poker_core.blind_positions import first_postflop_actor, first_preflop_actor
from texasholdemgym.backend.poker_core.hand_evaluation import showdown_tied_winners
from texasholdemgym.backend.poker_core.raise_rules import min_raise_increment_chips
from texasholdemgym.backend.table_bot import BotDecision, BotDecisionKind, build_seat_bot_observation


class NlhHandEngine:
    """Drives a single hand; mutates the bound PokerGame (Table, LiveHandState, Qt timers)."""

    __slots__ = ("_g",)

    def __init__(self, game: Any) -> None:
        self._g = game

    def count_eligible_for_deal(self) -> int:
        g = self._g
        return int(g._table.count_eligible_for_deal_roster(g._human_sitting_out))

    def bootstrap_playable_table(self) -> None:
        g = self._g
        hso, changed = g._table.bootstrap_if_insufficient_players(g._human_sitting_out)
        g._human_sitting_out = hso
        if changed:
            g._save_game_state_kv()

    def seat_eligible_for_new_hand(self, i: int) -> bool:
        g = self._g
        return g._table.seat_eligible_for_deal(int(i), g._human_sitting_out)

    def schedule_next_hand_if_idle(self) -> None:
        g = self._g
        if not g._auto_hand_loop:
            return
        ms = int(max(500, min(60000, int(g._winning_hand_show_ms))))
        g._next_hand_timer.stop()
        g._next_hand_timer.start(ms)

    def run_next_hand_timer_fire(self) -> None:
        g = self._g
        if g._live.in_progress:
            return
        self.begin_new_hand()

    def maybe_begin_hand_after_setup_change(self) -> None:
        g = self._g
        if g._live.in_progress:
            return
        if self.count_eligible_for_deal() < 2:
            return
        g.beginNewHand()

    def effective_seat_buy_in_chips(self, seat: int) -> int:
        g = self._g
        return int(
            g._table.effective_buy_in_chips(
                int(seat),
                hero_seat=int(g.HUMAN_HERO_SEAT),
                interactive_hero=bool(g._interactive_human),
            )
        )

    def betting_round_fully_resolved(self) -> bool:
        return self._g._street.betting_round_complete()

    def all_called_or_folded(self) -> bool:
        return self._g._street.all_street_bets_matched()

    def begin_betting_round(self, first: int, *, fresh_street: bool = True) -> None:
        g = self._g
        if first < 0:
            g._live.acting_seat = -1
            g._decision_seconds_left = 0
            g._decision_timer.stop()
            if g._live.in_progress:
                alive = g._street.seats_still_in_hand()
                if len(alive) <= 1:
                    self.award_uncontested(alive[0] if alive else -1)
                    return
                if g._street.betting_round_complete():
                    if self.maybe_handle_bb_preflop_option():
                        return
                    self.advance_street_or_showdown()
                    return
                pivot = int(g._live.bb_seat) if int(g._live.street) == 0 else int(g._live.button_seat)
                nxt = g._table.next_seat_clockwise_from(pivot, g._live.in_hand, need_chips=True)
                if nxt < 0:
                    nxt = g._table.next_seat_clockwise_from(pivot, g._live.in_hand, need_chips=False)
                if nxt >= 0:
                    g._live.acting_seat = nxt
                    g._decision_seconds_left = 20
                    g._human_more_time_available = True
                    g._decision_timer.start()
                    g._sync_root()
                    self.maybe_schedule_bot()
                    return
                QtCore.qWarning("PokerGame: could not recover first actor after first<0; forcing street/showdown.")
                self.advance_street_or_showdown()
                return
            g._sync_root()
            return
        g._live.acting_seat = first
        if fresh_street:
            g._live.init_street_acted(
                g._table.participating_list(), g._live.in_hand, g._table.stacks_list()
            )
        g._decision_seconds_left = 20
        g._human_more_time_available = True
        g._decision_timer.start()
        g._sync_root()
        self.maybe_schedule_bot()

    def begin_new_hand(self) -> None:
        g = self._g
        g._next_hand_timer.stop()
        if g._live.in_progress and g._root() is not None:
            g._sync_root()
            return
        self.bootstrap_playable_table()
        g._live.reset_for_new_deal()
        g._human_more_time_available = False
        dp = DealPositions.from_table(g._table, g._live.button_seat, g._human_sitting_out)
        dealing = dp.dealing
        n_live = dp.n_live
        g._live.hand_dealt_mask = [bool(dealing[i]) for i in range(6)]
        g._live.hand_num_dealt = int(n_live)
        if n_live < 2:
            g._live.in_progress = False
            g._live.acting_seat = -1
            g._decision_timer.stop()
            g._decision_seconds_left = 0
            if g._root() is not None:
                g._set_root(
                    "statusText",
                    "Need at least two players in the hand. Sit in to play or add players.",
                )
            g._sync_root()
            return
        g._live.hand_seq += 1
        g._hand_accounting.begin_action_log(int(time.time() * 1000))
        g._live.in_progress = True
        g._live.street = 0
        g._live.button_seat = dp.button_seat
        g._live.sb_seat, g._live.bb_seat = dp.sb_seat, dp.bb_seat
        g._live.deck = g._new_shuffled_deck()
        g._live.board = []
        g._live.holes = [[g._live.deck.pop(), g._live.deck.pop()] for _ in range(6)]
        g._live.in_hand = dealing
        g._hand_accounting.clear_for_new_hand()
        g._street.reset_street()
        g._street.post_blinds()
        first = first_preflop_actor(
            g._live.bb_seat,
            n_live,
            dealing,
            lambda need_chips: g._table.next_seat_clockwise_from(
                g._live.bb_seat, g._live.in_hand, need_chips=need_chips
            ),
        )
        self.begin_betting_round(first)

    def advance_street_or_showdown(self) -> None:
        g = self._g
        alive = g._street.seats_still_in_hand()
        if len(alive) <= 1:
            self.award_uncontested(alive[0] if alive else -1)
            return
        if g._live.street >= 3:
            self.do_showdown()
            return
        g._live.street = deal_next_community_street(g._live.street, g._live.board, g._live.deck)
        g._street.reset_street()
        first = first_postflop_actor(
            g._live.button_seat,
            g._street.seats_still_in_hand(),
            g._table.stacks_list(),
            lambda need_chips: g._table.next_seat_clockwise_from(
                g._live.button_seat, g._live.in_hand, need_chips=need_chips
            ),
            started_as_heads_up=bool(int(g._live.hand_num_dealt) == 2),
        )
        if first < 0 and len(g._street.seats_still_in_hand()) >= 2:
            g._decision_timer.stop()
            g._live.acting_seat = -1
            g._decision_seconds_left = 0
            g._live.street = run_out_board_to_river(g._live.street, g._live.board, g._live.deck)
            self.do_showdown()
            return
        self.begin_betting_round(first)

    def award_uncontested(self, winner: int) -> None:
        g = self._g
        pot = g._hand_accounting.total_contrib_chips()
        aw = [0] * 6
        if winner >= 0:
            aw[winner] = pot
            g._player(winner).receive_from_pot(pot)
        g._live.showdown = True
        g._live.acting_seat = -1
        g._decision_timer.stop()
        g._decision_seconds_left = 0
        win_list = [int(winner)] if winner >= 0 else []
        g._live.showdown_status_text = (
            Table.format_showdown_line(win_list, "Uncontested", bot_names=Table.DEFAULT_BOT_NAMES)
            if winner >= 0
            else "Showdown"
        )
        g._live.in_progress = False
        g._record_completed_hand(win_list, aw, winning_hand_name="Uncontested")
        g._sync_root()
        self.schedule_next_hand_if_idle()

    def apply_bot_decision(self, seat: int, decision: BotDecision) -> None:
        s = int(seat)
        if decision.kind == BotDecisionKind.FOLD:
            self.fold(s)
        elif decision.kind == BotDecisionKind.CHECK:
            self.check(s)
        elif decision.kind == BotDecisionKind.CALL:
            self.call(s)
        elif decision.kind == BotDecisionKind.RAISE_TO_LEVEL:
            self.raise_to(s, int(decision.raise_to_street_level))
        else:
            QtCore.qWarning("PokerGame: unexpected bot decision kind; checking.")
            self.check(s)

    def do_showdown(self) -> None:
        g = self._g
        alive = g._street.seats_still_in_hand()
        if not alive:
            self.award_uncontested(-1)
            return
        winners, wh_name = showdown_tied_winners(alive, g._live.board, g._live.holes)
        awards = g._street.distribute_showdown_payouts(g._hand_evaluator)
        for s in range(6):
            g._player(s).receive_from_pot(awards[s])
        g._live.showdown = True
        g._live.acting_seat = -1
        g._decision_timer.stop()
        g._decision_seconds_left = 0
        win_disp = sorted([s for s in range(6) if awards[s] > 0])
        if not win_disp:
            win_disp = list(winners)
        g._live.showdown_status_text = Table.format_showdown_line(
            win_disp, wh_name, bot_names=Table.DEFAULT_BOT_NAMES
        )
        g._live.in_progress = False
        g._record_completed_hand(win_disp, awards, winning_hand_name=wh_name)
        g._sync_root()
        self.schedule_next_hand_if_idle()

    def tick_decision(self) -> None:
        g = self._g
        if g._live.acting_seat < 0:
            if not g._live.in_progress:
                g._decision_timer.stop()
                return
            if not g._live.bb_preflop_waiting:
                self.begin_betting_round(-1)
            return
        g._decision_seconds_left = max(0, g._decision_seconds_left - 1)
        g._sync_root()
        if g._decision_seconds_left <= 0:
            self.auto_action_timeout()

    def auto_action_timeout(self) -> None:
        g = self._g
        if g._live.bb_preflop_waiting:
            self.finish_bb_preflop_check()
            return
        seat = g._live.acting_seat
        if seat < 0:
            return
        g._bot_timer.stop()
        if seat != g.HUMAN_HERO_SEAT or not g._interactive_human:
            self.bot_act()
            return
        need = g._hand_accounting.chips_needed_to_call(seat)
        if need > 0:
            self.fold(seat)
        else:
            self.check(seat)

    def maybe_schedule_bot(self) -> None:
        g = self._g
        s = g._live.acting_seat
        if s < 0:
            return
        if g._live.bb_preflop_waiting:
            return
        if s == g.HUMAN_HERO_SEAT and g._interactive_human:
            return
        g._bot_timer.stop()
        delay_ms = int(max(0, g._bot_decision_delay_sec) * 1000) if g._bot_slow_actions else 0
        g._bot_timer.start(delay_ms)

    def recover_stale_acting_seat(self) -> None:
        g = self._g
        s = g._live.acting_seat
        if s < 0 or not g._live.in_progress:
            return
        nxt = g._table.next_seat_clockwise_from(s, g._live.in_hand, need_chips=True)
        if nxt < 0:
            nxt = g._table.next_seat_clockwise_from(s, g._live.in_hand, need_chips=False)
        if nxt >= 0:
            g._live.acting_seat = nxt
            g._decision_seconds_left = 20
            g._human_more_time_available = True
            g._decision_timer.start()
            g._sync_root()
            self.maybe_schedule_bot()
            return
        if g._street.betting_round_complete():
            if self.maybe_handle_bb_preflop_option():
                return
            self.advance_street_or_showdown()
            return
        alive = g._street.seats_still_in_hand()
        if len(alive) <= 1:
            self.award_uncontested(alive[0] if alive else -1)

    def bot_act(self) -> None:
        g = self._g
        s = g._live.acting_seat
        if s < 0:
            return
        if not g._live.in_hand[s]:
            QtCore.qWarning("PokerGame: _bot_act with folded/out acting seat; recovering.")
            self.recover_stale_acting_seat()
            return
        obs = build_seat_bot_observation("street", s, g._table, g._live, g._hand_accounting, g._ranges)
        decision = g._seat_bot.decide_street_action(obs, g._rng)
        self.apply_bot_decision(s, decision)

    def fold(self, seat: int) -> None:
        g = self._g
        g._live.in_hand[seat] = False
        g._live.street_action_text[seat] = "Fold"
        g._street.log_street_action(seat, "Fold", 0)
        self.advance_after_action()

    def check(self, seat: int) -> None:
        g = self._g
        g._live.street_action_text[seat] = "Check"
        g._street.log_street_action(seat, "Check", 0)
        g._street.mark_street_acted(seat)
        self.advance_after_action()

    def call(self, seat: int) -> None:
        g = self._g
        need = g._hand_accounting.chips_needed_to_call(seat)
        g._street.apply_contribution(seat, need, label="Call" if need > 0 else "Check")
        self.advance_after_action()

    def raise_to(self, seat: int, to_amount: int) -> None:
        g = self._g
        to_amount = int(to_amount)
        if to_amount <= g._hand_accounting.to_call:
            self.call(seat)
            return
        prev_max = int(g._hand_accounting.to_call)
        need = max(0, to_amount - g._hand_accounting.street_put_in_at(seat))
        g._street.apply_contribution(seat, need, label="Raise")
        new_contrib = int(g._hand_accounting.street_put_in_at(seat))
        g._hand_accounting.bump_to_call_with_seat_street(seat)
        if new_contrib > prev_max:
            g._hand_accounting.last_raise_increment = int(new_contrib - prev_max)
        if g._live.street == 0 and g._hand_accounting.to_call > g._hand_accounting.preflop_blind_level:
            g._live.bb_preflop_option_open = False
        g._hand_accounting.last_raiser = seat
        self.advance_after_action()

    def advance_after_action(self) -> None:
        g = self._g
        alive = g._street.seats_still_in_hand()
        if len(alive) <= 1:
            self.award_uncontested(alive[0] if alive else -1)
            return
        if g._street.betting_round_complete():
            if self.maybe_handle_bb_preflop_option():
                return
            self.advance_street_or_showdown()
            return
        nxt = g._table.next_seat_clockwise_from(g._live.acting_seat, g._live.in_hand, need_chips=True)
        if nxt < 0:
            if self.maybe_handle_bb_preflop_option():
                return
            if g._street.betting_round_complete():
                self.advance_street_or_showdown()
            return
        g._live.acting_seat = nxt
        g._decision_seconds_left = 20
        g._human_more_time_available = True
        g._decision_timer.start()
        g._sync_root()
        self.maybe_schedule_bot()

    def maybe_handle_bb_preflop_option(self) -> bool:
        g = self._g
        if g._live.street != 0:
            return False
        mx = g._hand_accounting.max_street_contrib()
        if mx != g._hand_accounting.preflop_blind_level or not g._live.bb_preflop_option_open:
            return False
        g._live.bb_preflop_option_open = False
        bb = int(g._live.bb_seat)
        if not (0 <= bb < 6 and g._live.in_hand[bb]):
            return False
        hs = int(g.HUMAN_HERO_SEAT)
        if bb == hs and g._interactive_human and g._root() is not None:
            if g._player(hs).stack_on_table <= 0:
                return False
            g._live.bb_preflop_waiting = True
            g._live.acting_seat = hs
            g._decision_seconds_left = 20
            g._human_more_time_available = True
            g._decision_timer.start()
            g._sync_root()
            return True
        return self.bot_bb_preflop_option(bb)

    def finish_bb_preflop_check(self) -> None:
        g = self._g
        g._live.bb_preflop_waiting = False
        g._decision_timer.stop()
        g._decision_seconds_left = 0
        g._human_more_time_available = False
        bb = int(g._live.bb_seat)
        if 0 <= bb < 6:
            g._live.street_action_text[bb] = "Check"
            g._street.log_street_action(bb, "Check", 0)
            g._street.mark_street_acted(bb)
        g._sync_root()
        self.advance_street_or_showdown()

    def bb_preflop_add_raise(self, chips_to_add: int) -> None:
        g = self._g
        bb = int(g._live.bb_seat)
        if not (0 <= bb < 6 and bb == g.HUMAN_HERO_SEAT):
            return
        inc = min_raise_increment_chips(g._table.big_blind, g._hand_accounting.last_raise_increment)
        if inc <= 0 or g._hand_accounting.max_street_contrib() != g._hand_accounting.preflop_blind_level or g._player(bb).stack_on_table <= 0:
            self.finish_bb_preflop_check()
            return
        c = int(max(inc, min(int(chips_to_add), int(g._player(bb).stack_on_table))))
        if c < inc:
            self.finish_bb_preflop_check()
            return
        g._street.apply_contribution(bb, c, label="Raise")
        g._hand_accounting.last_raise_increment = int(c)
        g._hand_accounting.bump_to_call_with_seat_street(bb)
        g._live.bb_preflop_option_open = False
        g._live.bb_preflop_waiting = False
        g._decision_timer.stop()
        g._decision_seconds_left = 0
        g._human_more_time_available = False
        g._sync_root()
        first = g._table.next_seat_clockwise_from(bb, g._live.in_hand, need_chips=True)
        if first < 0:
            first = g._table.next_seat_clockwise_from(bb, g._live.in_hand, need_chips=False)
        self.begin_betting_round(first, fresh_street=False)

    def bot_bb_preflop_option(self, bb: int) -> bool:
        g = self._g
        if g._player(bb).stack_on_table <= 0:
            return False
        obs = build_seat_bot_observation(
            "bb_preflop_option", int(bb), g._table, g._live, g._hand_accounting, g._ranges
        )
        d = g._seat_bot.decide_bb_preflop_option(obs, g._rng)
        g._decision_timer.stop()
        if d.kind == BotDecisionKind.BB_PREFLOP_RAISE:
            inc = int(d.bb_raise_chips)
            g._street.apply_contribution(bb, inc, label="Raise")
            g._hand_accounting.last_raise_increment = int(inc)
            g._hand_accounting.bump_to_call_with_seat_street(bb)
            g._sync_root()
            first = g._table.next_seat_clockwise_from(bb, g._live.in_hand, need_chips=True)
            if first < 0:
                first = g._table.next_seat_clockwise_from(bb, g._live.in_hand, need_chips=False)
            self.begin_betting_round(first, fresh_street=False)
            return True
        g._live.street_action_text[bb] = "Check"
        g._street.log_street_action(bb, "Check", 0)
        g._street.mark_street_acted(bb)
        g._sync_root()
        return False
