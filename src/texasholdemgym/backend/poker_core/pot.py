from __future__ import annotations

from typing import Any

from texasholdemgym.backend.poker_core.protocols import HandStrengthEvaluator


def compute_pot_slices(contrib_total: list[int], in_hand: list[bool]) -> list[dict[str, Any]]:
    """Main + side pot slices from per-seat total contributions this hand."""
    contrib = [c if in_hand[i] or c > 0 else 0 for i, c in enumerate(contrib_total)]
    levels = sorted({c for c in contrib if c > 0})
    out: list[dict[str, Any]] = []
    prev = 0
    for lvl in levels:
        eligible = [i for i, c in enumerate(contrib) if c >= lvl]
        slice_amt = (lvl - prev) * len(eligible)
        if slice_amt > 0:
            out.append({"amount": int(slice_amt), "eligible": eligible})
        prev = lvl
    return out


def distribute_showdown_side_pots(
    contrib_total: list[int],
    in_hand: list[bool],
    alive: list[int],
    board: list[tuple[int, int]],
    holes: list[list[tuple[int, int]]],
    evaluator: HandStrengthEvaluator,
) -> list[int]:
    """Side-pot–aware NLHE distribution by contribution tiers (best hand per slice among contenders)."""
    contrib = [int(contrib_total[i]) for i in range(6)]
    awards = [0] * 6
    if not alive:
        return awards
    idxs = [i for i in range(6) if contrib[i] > 0]
    if not idxs:
        return awards
    levels = sorted({contrib[i] for i in idxs})
    prev = 0
    for lvl in levels:
        participants = [i for i in range(6) if contrib[i] >= lvl]
        pot_slice = (lvl - prev) * len(participants)
        contenders = [i for i in participants if in_hand[i]]
        prev = lvl
        if pot_slice <= 0:
            continue
        if not contenders:
            if alive:
                awards[min(alive)] += pot_slice
            continue
        best = None
        win_subset: list[int] = []
        for s in contenders:
            cards7 = list(board) + list(holes[s])
            rk = evaluator.best_rank_7(cards7)
            if best is None or rk > best:
                best = rk
                win_subset = [s]
            elif rk == best:
                win_subset.append(s)
        win_subset.sort()
        share, rem = divmod(int(pot_slice), len(win_subset))
        for j, w in enumerate(win_subset):
            awards[w] += share + (1 if j < rem else 0)
    return awards
