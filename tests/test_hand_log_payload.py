"""`build_hand_log_record` — stable JSON shape for :meth:`HandHistory.record_completed_hand` (no Qt)."""

from __future__ import annotations

import pytest

from texasholdemgym.backend.game_table import Table
from texasholdemgym.backend.hand_accounting import HandAccounting
from texasholdemgym.backend.hand_log_payload import build_hand_log_record
from texasholdemgym.backend.live_hand import Card, LiveHandState


def _ok_card(r: int, s: int) -> Card:
    return (r, s)  # rank 2..14, suit 0..3 for wire helpers


def test_hand_log_includes_dealt_seats_only_when_dealt_mask_set() -> None:
    table = Table.default_six_max()
    live = LiveHandState()
    live.button_seat = 0
    live.sb_seat = 1
    live.bb_seat = 2
    live.hand_num_dealt = 2
    live.hand_dealt_mask = [True, True, False, False, False, False]
    for s in range(6):
        live.holes[s] = [_ok_card(14, 0), _ok_card(14, 1)]
    acc = HandAccounting()
    acc.begin_action_log(1_000)
    p = build_hand_log_record(
        ended_ms=2_000,
        table=table,
        live=live,
        accounting=acc,
        player=table.players.__getitem__,
        pot_awards=None,
        winners=[],
    )
    seats = {d["seat"] for d in p["playersDetail"]}
    assert seats == {0, 1}
    assert p["numPlayers"] == 2


def test_hand_log_uses_all_participating_when_hand_num_dealt_zero() -> None:
    table = Table.default_six_max()
    for s in (2, 3, 4, 5):
        table.players[s].participating = False
    live = LiveHandState()
    live.hand_num_dealt = 0
    for s in range(6):
        live.holes[s] = [_ok_card(9, 0), _ok_card(8, 0)]
    acc = HandAccounting()
    acc.begin_action_log(1)
    p = build_hand_log_record(
        ended_ms=2,
        table=table,
        live=live,
        accounting=acc,
        player=table.players.__getitem__,
        pot_awards=[0, 0, 0, 0, 0, 0],
        winners=[],
    )
    assert p["numPlayers"] == 2
    assert len(p["playersDetail"]) == 2


@pytest.mark.parametrize("name,expect_key", [("", False), ("  Two pair  ", True)])
def test_hand_log_winning_name_only_when_non_empty(name: str, expect_key: bool) -> None:
    table = Table()
    live = LiveHandState()
    live.holes = [[_ok_card(10, 0), _ok_card(9, 0)] for _ in range(6)]
    acc = HandAccounting()
    acc.begin_action_log(1)
    p = build_hand_log_record(
        ended_ms=1,
        table=table,
        live=live,
        accounting=acc,
        player=table.players.__getitem__,
        pot_awards=None,
        winners=[],
        winning_hand_name=name,
    )
    assert ("winningHandName" in p) is expect_key
    if expect_key:
        assert p["winningHandName"] == "Two pair"


def test_hand_log_board_fills_five_slots_with_neg_one_padding() -> None:
    table = Table()
    live = LiveHandState()
    live.board = [_ok_card(14, 0), _ok_card(13, 1), _ok_card(12, 2)]
    live.holes = [[_ok_card(2, 0), _ok_card(3, 0)] for _ in range(6)]
    acc = HandAccounting()
    acc.begin_action_log(1)
    p = build_hand_log_record(
        ended_ms=1,
        table=table,
        live=live,
        accounting=acc,
        player=table.players.__getitem__,
        pot_awards=None,
        winners=[],
    )
    assert len(p["boardCardCodes"]) == 5
    assert p["boardCardCodes"][-1] == -1
    assert "boardDisplay" in p and "boardAssets" in p
