"""Preflop range strings ↔ 13×13 weight grids (`RangeGrid.qml` indices: A…2, row<col suited)."""

from __future__ import annotations

# Strongest … weakest (matches `PokerGame._hole_to_grid_row_col` / `RangeGrid.qml`).
RANK_ORDER = "AKQJT98765432"


def rank_index(ch: str) -> int:
    c = ch.upper()
    if len(c) != 1 or c not in RANK_ORDER:
        raise ValueError(f"bad rank {ch!r}")
    return RANK_ORDER.index(c)


def cell_to_token(row: int, col: int) -> str:
    if not (0 <= row < 13 and 0 <= col < 13):
        return ""
    if row == col:
        r = RANK_ORDER[row]
        return r + r
    if row < col:
        return RANK_ORDER[row] + RANK_ORDER[col] + "s"
    hi, lo = min(row, col), max(row, col)
    return RANK_ORDER[hi] + RANK_ORDER[lo] + "o"


def _set_cell(grid: list[float], row: int, col: int, w: float = 1.0) -> None:
    grid[row * 13 + col] = max(float(grid[row * 13 + col]), float(w))


def _mark_pair(grid: list[float], ri: int) -> None:
    _set_cell(grid, ri, ri)


def _mark_suited(grid: list[float], a: int, b: int) -> None:
    hi, lo = min(a, b), max(a, b)
    if hi == lo:
        _mark_pair(grid, hi)
    else:
        _set_cell(grid, hi, lo)


def _mark_offsuit(grid: list[float], a: int, b: int) -> None:
    hi, lo = min(a, b), max(a, b)
    if hi == lo:
        _mark_pair(grid, hi)
    else:
        _set_cell(grid, lo, hi)


def _expand_pair_plus(grid: list[float], start_idx: int) -> None:
    """`TT+` = TT … AA (stronger pairs = lower rank index)."""
    for i in range(0, start_idx + 1):
        _mark_pair(grid, i)


def _expand_suited_plus_ace(grid: list[float], lo_idx: int) -> None:
    """`ATs+` = ATs … AKs."""
    hi = 0
    for k in range(lo_idx, hi, -1):
        if k > hi:
            _mark_suited(grid, hi, k)


def _expand_suited_plus_non_ace(grid: list[float], hi_idx: int, lo_idx: int) -> None:
    """`KQs+` = KQs … K2s."""
    for k in range(lo_idx, 13):
        if k > hi_idx:
            _mark_suited(grid, hi_idx, k)


def _expand_ace_suited_all(grid: list[float]) -> None:
    """`A2s+` — all Ax suited (A2 … AK)."""
    for k in range(12, 0, -1):
        _mark_suited(grid, 0, k)


def _parse_one_token(tok: str, grid: list[float]) -> None:
    t = tok.strip()
    if not t:
        return
    if t == "*":
        for i in range(13 * 13):
            grid[i] = 1.0
        return

    u = t.upper()
    if u == "A2S+":
        _expand_ace_suited_all(grid)
        return
    # RR+ pairs
    if len(t) == 3 and t[2] == "+" and t[0].upper() == t[1].upper():
        r = rank_index(t[0])
        _expand_pair_plus(grid, r)
        return

    # X2s+ (e.g. K2s+ — K2s … KQs)
    if len(t) == 4 and t[1] == "2" and t[-2:].lower() == "s+":
        hi = rank_index(t[0])
        for k in range(12, hi, -1):
            if k > hi:
                _mark_suited(grid, hi, k)
        return

    # XYs+ (length >= 4, ends with s+)
    if len(t) >= 4 and t[-2:].lower() == "s+":
        a, b = rank_index(t[0]), rank_index(t[1])
        hi, lo = min(a, b), max(a, b)
        if hi == 0:
            _expand_suited_plus_ace(grid, lo)
        else:
            _expand_suited_plus_non_ace(grid, hi, lo)
        return

    # XYs / XYo (exactly 3 chars)
    if len(t) == 3 and t[2].lower() in "so":
        a, b = rank_index(t[0]), rank_index(t[1])
        if a == b:
            _mark_pair(grid, a)
        elif t[2].lower() == "s":
            _mark_suited(grid, a, b)
        else:
            _mark_offsuit(grid, a, b)
        return

    # Pair RR
    if len(t) == 2 and t[0].upper() == t[1].upper():
        r = rank_index(t[0])
        _mark_pair(grid, r)
        return

    raise ValueError(f"bad token: {tok!r}")


def parse_range_to_grid(text: str) -> list[float]:
    """Return 169 weights in [0,1] from a comma-separated range string."""
    raw = str(text).strip()
    if not raw:
        raise ValueError("empty range")
    if raw == "*":
        return [1.0] * (13 * 13)

    grid = [0.0] * (13 * 13)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("empty range")
    for p in parts:
        _parse_one_token(p, grid)
    return grid


def format_grid_to_range(weights: list[float]) -> str:
    """Canonical text for a 13×13 weight list."""
    if len(weights) != 13 * 13:
        return ""
    if all(float(w) >= 0.99 for w in weights):
        return "*"

    toks: list[str] = []
    for r in range(13):
        for c in range(13):
            if float(weights[r * 13 + c]) > 0.5:
                toks.append(cell_to_token(r, c))
    toks = sorted(set(toks), key=lambda s: (len(s), s))
    return ",".join(toks)


def merge_grids_max(*grids: list[float]) -> list[float]:
    out = [0.0] * (13 * 13)
    for g in grids:
        if len(g) != 13 * 13:
            continue
        for i in range(13 * 13):
            out[i] = max(out[i], float(g[i]))
    return out
