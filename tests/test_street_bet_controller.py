"""`StreetBetController` — blind posting, contributions, betting-round flag."""

from __future__ import annotations

from texasholdemgym.backend.game_table import Table
from texasholdemgym.backend.hand_accounting import HandAccounting
from texasholdemgym.backend.live_hand import LiveHandState
from texasholdemgym.backend.street_bet_controller import StreetBetController


def test_street_bet_controller_post_blinds_and_sync_callback() -> None:
    syncs: list[int] = []

    def bump() -> None:
        syncs.append(1)

    t = Table.default_six_max()
    t.small_blind = 1
    t.big_blind = 2
    live = LiveHandState()
    live.street = 0
    live.sb_seat = 1
    live.bb_seat = 2
    live.in_hand = [True] * 6
    acct = HandAccounting()
    acct.clear_for_new_hand()
    ctl = StreetBetController(t, live, acct, after_chips_sync=bump)

    ctl.post_blinds()
    assert len(syncs) == 2
    assert acct.total_contrib_chips() == 3
    assert live.bb_preflop_option_open is True
    assert "SB" in live.street_action_text[1]
    assert "BB" in live.street_action_text[2]


def test_apply_contribution_skips_folded_seat() -> None:
    def noop() -> None:
        pass

    t = Table.default_six_max()
    live = LiveHandState()
    live.in_hand = [False, True, True, True, True, True]
    live.street = 0
    acct = HandAccounting()
    acct.clear_for_new_hand()
    ctl = StreetBetController(t, live, acct, after_chips_sync=noop)
    assert ctl.apply_contribution(0, 5, label="Raise") == 0


def test_reset_street_clears_action_labels() -> None:
    def noop() -> None:
        pass

    t = Table.default_six_max()
    live = LiveHandState()
    live.street = 1
    live.street_action_text[0] = "Check"
    acct = HandAccounting()
    acct.clear_for_new_hand()
    ctl = StreetBetController(t, live, acct, after_chips_sync=noop)
    ctl.reset_street()
    assert live.street_action_text[0] == ""


def test_mark_street_acted_ignores_invalid_seat() -> None:
    def noop() -> None:
        pass

    t = Table.default_six_max()
    live = LiveHandState()
    acct = HandAccounting()
    ctl = StreetBetController(t, live, acct, after_chips_sync=noop)
    ctl.mark_street_acted(99)
    assert live.street_acted == [False] * 6


def test_log_street_action_appends_to_hand_log() -> None:
    def noop() -> None:
        pass

    t = Table.default_six_max()
    live = LiveHandState()
    live.street = 1
    acct = HandAccounting()
    acct.begin_action_log(12345)
    ctl = StreetBetController(t, live, acct, after_chips_sync=noop)
    ctl.log_street_action(4, "Check", 0, is_blind=False)
    snaps = acct.snapshot_actions()
    assert snaps and snaps[-1].get("seat") == 4


def test_betting_round_complete_returns_bool() -> None:
    def noop() -> None:
        pass

    t = Table.default_six_max()
    live = LiveHandState()
    live.in_hand = [True] * 6
    acct = HandAccounting()
    acct.clear_for_new_hand()
    ctl = StreetBetController(t, live, acct, after_chips_sync=noop)
    assert isinstance(ctl.betting_round_complete(), bool)
