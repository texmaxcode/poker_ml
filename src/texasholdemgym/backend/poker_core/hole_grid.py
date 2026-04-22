"""Map hole cards to the 13×13 range grid (same convention as `RangeGrid.qml`)."""


def hole_to_range_grid_row_col(h0: tuple[int, int], h1: tuple[int, int]) -> tuple[int, int]:
    r1, s1 = int(h0[0]), int(h0[1])
    r2, s2 = int(h1[0]), int(h1[1])
    if r1 < 2 or r2 < 2:
        return (0, 0)
    # Row/col 0 = Ace … 12 = Two (`RangeGrid.qml` rankLabels).
    i1, i2 = 14 - r1, 14 - r2
    if i1 == i2:
        return (i1, i1)
    if s1 == s2:
        a, b = (i1, i2) if i1 < i2 else (i2, i1)
        return (a, b)  # row < col → suited
    lo, hi = min(i1, i2), max(i1, i2)
    return (hi, lo)  # row > col → offsuit
