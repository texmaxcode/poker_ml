from __future__ import annotations

import itertools

HAND_CATEGORY_DISPLAY_NAMES: tuple[str, ...] = (
    "High card",
    "Pair",
    "Two pair",
    "Three of a kind",
    "Straight",
    "Flush",
    "Full house",
    "Four of a kind",
    "Straight flush",
)


def hand_rank_5(cards5: list[tuple[int, int]]) -> tuple:
    """Return sortable tuple: (category, tiebreakers…)."""
    ranks = sorted([r for r, _ in cards5], reverse=True)
    suits = [s for _, s in cards5]
    counts = {r: ranks.count(r) for r in set(ranks)}
    by_count = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    is_flush = len(set(suits)) == 1
    uniq = sorted(set(ranks), reverse=True)
    is_straight = len(uniq) == 5 and (uniq[0] - uniq[4] == 4)
    # Wheel A-5
    if set(ranks) == {14, 5, 4, 3, 2}:
        is_straight = True
        uniq = [5, 4, 3, 2, 1]

    if is_straight and is_flush:
        return (8, uniq[0])
    if by_count[0][1] == 4:
        four = by_count[0][0]
        kicker = max(r for r in ranks if r != four)
        return (7, four, kicker)
    if by_count[0][1] == 3 and by_count[1][1] == 2:
        return (6, by_count[0][0], by_count[1][0])
    if is_flush:
        return (5, *ranks)
    if is_straight:
        return (4, uniq[0])
    if by_count[0][1] == 3:
        trip = by_count[0][0]
        kickers = sorted([r for r in ranks if r != trip], reverse=True)
        return (3, trip, *kickers)
    if by_count[0][1] == 2 and by_count[1][1] == 2:
        p1, p2 = by_count[0][0], by_count[1][0]
        kicker = max(r for r in ranks if r not in (p1, p2))
        hi, lo = max(p1, p2), min(p1, p2)
        return (2, hi, lo, kicker)
    if by_count[0][1] == 2:
        pair = by_count[0][0]
        kickers = sorted([r for r in ranks if r != pair], reverse=True)
        return (1, pair, *kickers)
    return (0, *ranks)


def best_rank_7(cards7: list[tuple[int, int]]) -> tuple:
    best: tuple | None = None
    for comb in itertools.combinations(cards7, 5):
        r = hand_rank_5(list(comb))
        if best is None or r > best:
            best = r
    return best or (0,)


def rank_tuple_display_name(rank: tuple) -> str:
    if not rank:
        return ""
    cat = int(rank[0])
    if 0 <= cat < len(HAND_CATEGORY_DISPLAY_NAMES):
        return HAND_CATEGORY_DISPLAY_NAMES[cat]
    return "Hand"


def hand_strength_01_hole_board(
    h0: tuple[int, int],
    h1: tuple[int, int],
    board: list[tuple[int, int]],
) -> float:
    """0–1 strength for a seat: best 5 of hole cards + community (bot / HUD signals)."""
    if h0[0] < 2 or h1[0] < 2:
        return 0.0
    cards7 = [h0, h1] + [c for c in board if c[0] >= 2]
    if len(cards7) < 2:
        return 0.0
    return rank_tuple_to_strength_01(best_rank_7(cards7))


def showdown_tied_winners(
    alive_seats: list[int],
    board: list[tuple[int, int]],
    holes: list[list[tuple[int, int]]],
) -> tuple[list[int], str]:
    """Seats sharing the best 7-card hand and a display label (e.g. "Two pair")."""
    if not alive_seats:
        return [], ""
    ranks: dict[int, tuple] = {}
    for s in alive_seats:
        cards7 = list(board) + list(holes[s])
        ranks[s] = best_rank_7(cards7)
    best = max(ranks.values())
    winners = [s for s, r in ranks.items() if r == best]
    return winners, rank_tuple_display_name(best)


def rank_tuple_to_strength_01(rank: tuple) -> float:
    """Map `hand_rank_5` tuple to [0,1] like upstream `hand_eval::score_to_01`."""
    if not rank:
        return 0.0
    cat = int(rank[0]) / 8.0
    tail = list(rank[1:])
    if not tail:
        return min(1.0, cat * 0.72)
    kick = 0.0
    for i, v in enumerate(tail[:7], start=1):
        kick += float(v) / (14.0 * float(i))
    kick /= 7.0
    return min(1.0, cat * 0.72 + kick * 0.28)


class StandardHandEvaluator:
    """Default `HandStrengthEvaluator` implementation."""

    def best_rank_7(self, cards7: list[tuple[int, int]]) -> tuple:
        return best_rank_7(cards7)
