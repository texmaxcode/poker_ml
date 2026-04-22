"""Post-blind check-down: `all_called_or_folded` is vacuous when to_call==0; engine must not end the street early."""

from __future__ import annotations

from PySide6 import QtWidgets

from texasholdemgym.backend.poker_game import PokerGame


def test_betting_round_not_resolved_on_check_down_until_all_have_acted() -> None:
    _ = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    g = PokerGame(db=None, hand_history=None)
    try:
        g._live.in_progress = True
        g._live.street = 1
        g._live.in_hand = [True] * 6
        for i in range(6):
            g._player(i).participating = True
            g._player(i).stack_on_table = 100
        g._hand_accounting.clear_for_new_hand()
        g._hand_accounting.reset_street(1, int(g._table.big_blind))
        g._init_street_acted_for_new_round()
        assert g._all_called_or_folded()
        assert not g._betting_round_fully_resolved()
        for s in range(6):
            g._mark_street_acted(s)
        assert g._betting_round_fully_resolved()
    finally:
        g.deleteLater()
