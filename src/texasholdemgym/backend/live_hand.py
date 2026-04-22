"""State for the current deal: cards, board, positions, and per-hand UI strings.

Timers, `HandPotState`, and `HandActionLog` stay on `PokerGame`. This type is the rest of
what changes every hand — the story you would tell looking at the table.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Card = tuple[int, int]


def _fresh_holes_sentinel() -> list[list[Card]]:
    return [[(-1, -1), (-1, -1)] for _ in range(6)]


@dataclass
class LiveHandState:
    hand_seq: int = 0
    button_seat: int = 0
    sb_seat: int = 1
    bb_seat: int = 2
    street: int = 0  # 0 preflop, 1 flop, 2 turn, 3 river
    acting_seat: int = -1
    deck: list[Card] = field(default_factory=list)
    board: list[Card] = field(default_factory=list)
    holes: list[list[Card]] = field(default_factory=_fresh_holes_sentinel)
    in_hand: list[bool] = field(default_factory=lambda: [True] * 6)
    street_action_text: list[str] = field(default_factory=lambda: [""] * 6)
    bb_preflop_option_open: bool = False
    bb_preflop_waiting: bool = False
    showdown: bool = False
    showdown_status_text: str = ""
    in_progress: bool = False
    hand_num_dealt: int = 0
    hand_dealt_mask: list[bool] = field(default_factory=lambda: [False] * 6)
    # Voluntary action taken this betting round (fold / check / call / raise). Used so a
    # check-down round (to_call == 0, no aggressor) is not treated as complete after only one
    # check — `all_called_or_folded` is vacuously true when everyone matches $0.
    street_acted: list[bool] = field(default_factory=lambda: [False] * 6)

    def clear_showdown_banner(self) -> None:
        self.showdown = False
        self.showdown_status_text = ""

    def reset_street_labels(self) -> None:
        self.street_action_text = [""] * 6

    def reset_street_acted(self) -> None:
        self.street_acted = [False] * 6

    def init_street_acted(self, participating: list[bool], in_hand: list[bool], stacks: list[int]) -> None:
        """Start-of-street flags: clear, then mark all-in seats (0 stack) as done for this round."""
        self.reset_street_acted()
        for s in range(min(6, len(participating), len(in_hand), len(stacks))):
            if participating[s] and in_hand[s] and int(stacks[s]) <= 0:
                self.street_acted[s] = True

    def reset_for_new_deal(self) -> None:
        """Clear last hand's showdown line and BB-wait UI flags before dealing."""
        self.clear_showdown_banner()
        self.bb_preflop_waiting = False
