from __future__ import annotations

HUMAN_HERO_SEAT = 0


def count_eligible_for_deal(
    seat_buy_in: list[int],
    human_sitting_out: bool,
    seat_participating: list[bool],
) -> int:
    """Count seats eligible for the next deal (idle path)."""
    n = 0
    for i in range(6):
        if int(seat_buy_in[i]) <= 0:
            continue
        if i == HUMAN_HERO_SEAT and human_sitting_out:
            continue
        if i >= 1 and not seat_participating[i]:
            continue
        n += 1
    return int(n)


def seat_eligible_for_new_hand(
    seat: int,
    seat_buy_in: list[int],
    human_sitting_out: bool,
    seat_participating: list[bool],
) -> bool:
    if not (0 <= seat < 6):
        return False
    if int(seat_buy_in[seat]) <= 0:
        return False
    if seat == HUMAN_HERO_SEAT and human_sitting_out:
        return False
    if seat >= 1 and not seat_participating[seat]:
        return False
    return True


def dealing_mask_for_new_hand(
    seat_buy_in: list[int],
    human_sitting_out: bool,
    seat_participating: list[bool],
) -> list[bool]:
    return [seat_eligible_for_new_hand(i, seat_buy_in, human_sitting_out, seat_participating) for i in range(6)]


def bootstrap_playable_table(
    seat_participating: list[bool],
    seat_buy_in: list[int],
    human_sitting_out: bool,
    start_stack: int,
) -> tuple[list[bool], list[int], bool, bool]:
    """Return updated seat state; last bool is whether anything changed.

    Mirrors `PokerGame._bootstrap_playable_table` without persistence side effects.
    """
    sp = list(seat_participating)
    bi = list(seat_buy_in)
    hso = bool(human_sitting_out)
    ss = max(1, int(start_stack))
    changed = False

    for i in range(6):
        if not sp[i]:
            continue
        if i == HUMAN_HERO_SEAT and hso:
            continue
        if int(bi[i]) <= 0:
            bi[i] = ss
            changed = True

    if count_eligible_for_deal(bi, hso, sp) >= 2:
        return sp, bi, hso, changed

    if hso:
        hso = False
        changed = True
    sp[0] = True
    for i in (1, 2):
        sp[i] = True
        if int(bi[i]) <= 0:
            bi[i] = ss
            changed = True
    if int(bi[0]) <= 0:
        bi[0] = ss
        changed = True

    return sp, bi, hso, changed
