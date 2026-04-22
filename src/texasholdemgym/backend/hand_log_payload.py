"""Build the JSON-like dict for :meth:`~texasholdemgym.backend.hand_history.HandHistory.record_completed_hand`.

`AppDatabase.insert_hand_log` maps this into relational `hands` / `actions` / `players` rows.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from texasholdemgym.backend.game_table import Player, Table
from texasholdemgym.backend.hand_accounting import HandAccounting
from texasholdemgym.backend.live_hand import LiveHandState
from texasholdemgym.backend.poker_core.cards import card_asset, pretty_card
from texasholdemgym.backend.sqlite_store import _card_tuple_to_wire_int


def build_hand_log_record(
    *,
    ended_ms: int,
    table: Table,
    live: LiveHandState,
    accounting: HandAccounting,
    player: Callable[[int], Player],
    pot_awards: list[int] | None,
    winners: list[int],
    winning_hand_name: str = "",
) -> dict[str, Any]:
    board_display = " ".join(pretty_card(c) for c in live.board if c[0] >= 2).strip()
    board_assets = [card_asset(c) for c in live.board if c[0] >= 2]
    n_players = int(live.hand_num_dealt) if live.hand_num_dealt > 0 else sum(1 for i in range(6) if player(i).participating)
    aw = list(pot_awards) if pot_awards is not None else [0] * 6
    players_detail: list[dict[str, Any]] = []
    for s in range(6):
        if live.hand_num_dealt > 0:
            if s >= len(live.hand_dealt_mask) or not live.hand_dealt_mask[s]:
                continue
        elif not player(s).participating:
            continue
        h0, h1 = live.holes[s]
        pl = player(s)
        players_detail.append(
            {
                "seat": int(s),
                "contrib": int(accounting.contrib_at(s)),
                "won": int(aw[s]),
                "hole_svg1": card_asset(h0),
                "hole_svg2": card_asset(h1),
                "total_bankroll": int(pl.bankroll_off_table + pl.stack_on_table),
            }
        )
    board_codes: list[int] = []
    for i in range(5):
        if i < len(live.board):
            r, s = live.board[i]
            board_codes.append(_card_tuple_to_wire_int((r, s)))
        else:
            board_codes.append(-1)
    payload: dict[str, Any] = {
        "startedMs": int(accounting.history_started_ms()),
        "endedMs": int(ended_ms),
        "numPlayers": int(n_players),
        "boardDisplay": board_display,
        "boardAssets": board_assets,
        "boardCardCodes": board_codes,
        "winners": [int(x) for x in winners],
        "sbSize": int(table.small_blind),
        "bbSize": int(table.big_blind),
        "buttonSeat": int(live.button_seat),
        "sbSeat": int(live.sb_seat),
        "bbSeat": int(live.bb_seat),
        "sessionKey": 0,  # single-table app; `player_key` in DB is derived as session_key*64+seat
        "actions": accounting.snapshot_actions(),
        "playersDetail": players_detail,
        "totalHandWonChips": int(sum(aw)),
    }
    wh = str(winning_hand_name or "").strip()
    if wh:
        payload["winningHandName"] = wh
    return payload
