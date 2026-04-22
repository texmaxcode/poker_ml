"""Post-blind check-down: `all_called_or_folded` is vacuous when to_call==0; engine must not end the street early."""

from __future__ import annotations

from PySide6 import QtWidgets

from texasholdemgym.backend.poker_core.betting_navigation import betting_round_fully_resolved
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
        g._live.init_street_acted(g._table.participating_list(), g._live.in_hand, g._table.stacks_list())
        assert g._all_called_or_folded()
        assert not betting_round_fully_resolved(
            g._table.participating_list(),
            g._live.in_hand,
            g._hand_accounting.street_put_in_list(),
            g._table.stacks_list(),
            int(g._hand_accounting.to_call),
            int(g._hand_accounting.last_raiser),
            g._live.street_acted,
        )
        for s in range(6):
            g._street.mark_street_acted(s)
        assert g._betting_round_fully_resolved()
    finally:
        g.deleteLater()
