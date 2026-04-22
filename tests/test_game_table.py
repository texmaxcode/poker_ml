"""`Table` roster, buy-in, and seat label helpers moved off `PokerGame`."""

from __future__ import annotations

from texasholdemgym.backend.game_table import DealPositions, Player, Table


def test_seat_position_label_btn_sb_bb() -> None:
    part = [True] * 6
    assert Table.seat_position_label(0, button_seat=0, sb_seat=1, bb_seat=2, participating=part) == "BTN"
    assert Table.seat_position_label(1, button_seat=0, sb_seat=1, bb_seat=2, participating=part) == "SB"
    assert Table.seat_position_label(2, button_seat=0, sb_seat=1, bb_seat=2, participating=part) == "BB"


def test_effective_buy_in_uses_strategy_buy_in_bb() -> None:
    t = Table.default_six_max()
    t.big_blind = 2
    t.max_on_table_bb = 100
    t.players[3].strategy.tuning.buyInBb = 50
    chips = t.effective_buy_in_chips(3, hero_seat=0, interactive_hero=False)
    assert chips == 100  # min(50*2, 200 cap)


def test_player_reconcile_stack_moves_overflow_to_bankroll() -> None:
    p = Player(seat=0, stack_on_table=250, bankroll_off_table=10)
    p.reconcile_stack_with_table_cap(200)
    assert p.stack_on_table == 200
    assert p.bankroll_off_table == 60


def test_player_set_stack_preserves_total_and_respects_cap() -> None:
    p = Player(seat=0, stack_on_table=50, bankroll_off_table=50)
    p.set_stack_with_total_preservation(120, cap=80)
    assert p.stack_on_table == 80
    assert p.bankroll_off_table == 20


def test_deal_positions_respects_human_sitting_out() -> None:
    t = Table.default_six_max()
    t.players[0].participating = True
    t.players[0].stack_on_table = 100
    for i in range(1, 6):
        t.players[i].participating = True
        t.players[i].stack_on_table = 100
    dp = DealPositions.from_table(t, prev_button=0, human_sitting_out=True)
    assert dp.n_live <= 5
    assert len(dp.dealing) == 6


def test_table_hud_formatting_delegates_to_table_messages() -> None:
    assert (
        Table.format_hud_status_line(
            0,
            4,
            1,
            showdown=False,
            showdown_status_text="",
            bb_preflop_waiting=False,
            interactive_human=True,
            hero_seat=0,
            bot_names=Table.DEFAULT_BOT_NAMES,
        )
        == "Preflop $4 Peter"
    )
    assert "wins" in Table.format_showdown_line([0], "Trips", bot_names=Table.DEFAULT_BOT_NAMES)
    assert Table.format_hero_hole_hud_text((14, 0), (13, 0), hero_in_hand=True, human_sitting_out=False) != ""


def test_deal_positions_from_table_has_six_mask_and_valid_button() -> None:
    t = Table.default_six_max()
    t.big_blind = 2
    prev = 0
    dp = DealPositions.from_table(t, prev, human_sitting_out=False)
    assert len(dp.dealing) == 6
    assert dp.n_live == int(sum(dp.dealing))
    assert 0 <= dp.button_seat < 6


def test_table_next_live_stack_seat_from_walks_participating_with_chips() -> None:
    t = Table.default_six_max()
    for p in t.players:
        p.participating = False
    t.players[0].participating = True
    t.players[0].stack_on_table = 50
    t.players[3].participating = True
    t.players[3].stack_on_table = 50
    assert t.next_live_stack_seat_from(0) == 3


def test_player_transfer_from_bankroll_to_table() -> None:
    p = Player(seat=0, stack_on_table=0, bankroll_off_table=100)
    moved = p.transfer_from_bankroll_to_table(40)
    assert moved == 40
    assert p.stack_on_table == 40
    assert p.bankroll_off_table == 60


def test_bootstrap_insufficient_seats_returns_changed() -> None:
    t = Table.default_six_max()
    for p in t.players:
        p.participating = False
        p.stack_on_table = 0
    t.players[0].participating = True
    t.players[0].stack_on_table = 100
    hso, changed = t.bootstrap_if_insufficient_players(human_sitting_out=False)
    assert changed is True
    assert sum(1 for p in t.players if p.participating and p.stack_on_table > 0) >= 2
    assert isinstance(hso, bool)
