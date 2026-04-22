"""Pure table / pot / hand-evaluation helpers split out of `PokerGame` for testing and reuse."""

from texasholdemgym.backend.poker_core.board_deal import deal_next_community_street, run_out_board_to_river
from texasholdemgym.backend.poker_core.blind_positions import (
    advance_button_seat,
    blind_seats_for_hand,
    first_preflop_actor,
)
from texasholdemgym.backend.poker_core.betting_navigation import (
    all_called_or_folded,
    next_live_stack_seat,
    next_seat_clockwise,
    remaining_players,
)
from texasholdemgym.backend.poker_core.cards import card_asset, new_shuffled_deck, pretty_card
from texasholdemgym.backend.poker_core.hand_evaluation import (
    StandardHandEvaluator,
    best_rank_7,
    hand_rank_5,
    rank_tuple_display_name,
    rank_tuple_to_strength_01,
)
from texasholdemgym.backend.poker_core.hand_action_log import HandActionLog
from texasholdemgym.backend.poker_core.hand_pot import HandPotState
from texasholdemgym.backend.poker_core.hole_grid import hole_to_range_grid_row_col
from texasholdemgym.backend.poker_core.pot import compute_pot_slices, distribute_showdown_side_pots
from texasholdemgym.backend.poker_core.raise_rules import min_raise_increment_chips
from texasholdemgym.backend.poker_core.protocols import HandStrengthEvaluator
from texasholdemgym.backend.poker_core.showdown_text import (
    DEFAULT_SEAT_BOT_NAMES,
    format_showdown_line,
    seat_display_name,
)
from texasholdemgym.backend.poker_core.table_roster import (
    bootstrap_playable_table,
    count_eligible_for_deal,
    dealing_mask_for_new_hand,
    seat_eligible_for_new_hand,
)

__all__ = [
    "HandActionLog",
    "HandPotState",
    "advance_button_seat",
    "blind_seats_for_hand",
    "first_preflop_actor",
    "HandStrengthEvaluator",
    "StandardHandEvaluator",
    "all_called_or_folded",
    "bootstrap_playable_table",
    "card_asset",
    "compute_pot_slices",
    "count_eligible_for_deal",
    "DEFAULT_SEAT_BOT_NAMES",
    "deal_next_community_street",
    "dealing_mask_for_new_hand",
    "distribute_showdown_side_pots",
    "format_showdown_line",
    "hole_to_range_grid_row_col",
    "min_raise_increment_chips",
    "next_live_stack_seat",
    "next_seat_clockwise",
    "hand_rank_5",
    "best_rank_7",
    "new_shuffled_deck",
    "pretty_card",
    "rank_tuple_display_name",
    "rank_tuple_to_strength_01",
    "remaining_players",
    "run_out_board_to_river",
    "seat_display_name",
    "seat_eligible_for_new_hand",
]
