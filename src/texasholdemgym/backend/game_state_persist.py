"""SQLite KV persistence for table stakes, roster, and `PokerGame` UI / bot flags (not per-hand state)."""

from __future__ import annotations

from typing import Any

from texasholdemgym.backend.sqlite_store import AppDatabase

GAME_STATE_KV_KEY = "poker_game_state_v1"
RANGES_BUNDLE_KEY = "seat_ranges_v1"


def clear_game_and_range_kv(db: AppDatabase) -> None:
    db.kv_delete(GAME_STATE_KV_KEY)
    db.kv_delete(RANGES_BUNDLE_KEY)


def build_table_client_snapshot(game: Any) -> dict[str, Any]:
    t, live = game._table, game._live
    return {
        "sb": int(t.small_blind),
        "bb": int(t.big_blind),
        "streetBet": int(t.street_bet),
        "maxTableBb": int(t.max_on_table_bb),
        "startStack": int(t.start_stack),
        "seatBuyIn": t.stacks_list(),
        "seatBankrollTotal": t.bankrolls_list(),
        "seatParticipating": t.participating_list(),
        "interactiveHuman": bool(game._interactive_human),
        "humanSittingOut": bool(game._human_sitting_out),
        "botSlowActions": bool(game._bot_slow_actions),
        "winningHandShowMs": int(game._winning_hand_show_ms),
        "botDecisionDelaySec": int(game._bot_decision_delay_sec),
        "buttonSeat": int(live.button_seat),
        "seatStrategyIdx": [int(p.strategy.archetype_index) for p in t.players],
        "autoHandLoop": bool(game._auto_hand_loop),
    }


def _apply_client_flags_from_kv(m: dict[str, Any], game: Any) -> None:
    if "autoHandLoop" in m:
        game._auto_hand_loop = bool(m["autoHandLoop"])
    if "interactiveHuman" in m:
        nh = bool(m["interactiveHuman"])
        if nh != game._interactive_human:
            game._interactive_human = nh
            game.interactiveHumanChanged.emit()
    if "humanSittingOut" in m:
        game._human_sitting_out = bool(m["humanSittingOut"])
    if "botSlowActions" in m:
        nb = bool(m["botSlowActions"])
        if nb != game._bot_slow_actions:
            game._bot_slow_actions = nb
            game.botSlowActionsChanged.emit()
    if "winningHandShowMs" in m:
        nw = int(m["winningHandShowMs"])
        if nw != game._winning_hand_show_ms:
            game._winning_hand_show_ms = nw
            game.winningHandShowMsChanged.emit()
    if "botDecisionDelaySec" in m:
        nd = int(m["botDecisionDelaySec"])
        if nd != game._bot_decision_delay_sec:
            game._bot_decision_delay_sec = nd
            game.botDecisionDelaySecChanged.emit()
    if "buttonSeat" in m:
        game._live.button_seat = int(m["buttonSeat"]) % 6


def load_table_client_from_db(db: AppDatabase, game: Any) -> bool:
    """Load GAME_STATE_KV into ``game``'s `Table` and client flags. Returns whether a dict was read."""
    from texasholdemgym.backend import bot_strategy

    m = db.kv_get_json(GAME_STATE_KV_KEY)
    if not isinstance(m, dict):
        return False
    t = game._table
    t.small_blind = int(m.get("sb", t.small_blind))
    t.big_blind = int(m.get("bb", t.big_blind))
    t.street_bet = int(m.get("streetBet", t.street_bet))
    t.max_on_table_bb = int(m.get("maxTableBb", t.max_on_table_bb))
    t.start_stack = int(m.get("startStack", t.start_stack))
    sb = m.get("seatBuyIn")
    if isinstance(sb, list) and len(sb) == 6:
        t.import_stacks([int(x) for x in sb])
    bt = m.get("seatBankrollTotal")
    if isinstance(bt, list) and len(bt) == 6:
        t.import_bankrolls([int(x) for x in bt])
    sp = m.get("seatParticipating")
    if isinstance(sp, list) and len(sp) == 6:
        t.import_participating([bool(x) for x in sp])
        game._player(int(game.HUMAN_HERO_SEAT)).participating = True
    _apply_client_flags_from_kv(m, game)
    ss = m.get("seatStrategyIdx")
    if isinstance(ss, list) and len(ss) == 6:
        for i, x in enumerate(ss[:6]):
            game._player(i).strategy.archetype_index = min(
                bot_strategy.STRATEGY_COUNT - 1, max(0, int(x))
            )
    return True


def save_table_client_to_db(db: AppDatabase, game: Any) -> None:
    db.kv_set_json(GAME_STATE_KV_KEY, build_table_client_snapshot(game))
