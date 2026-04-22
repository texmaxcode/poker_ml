"""Setup preflop range matrices (3 layers × 13×13) per seat — parse, edit, persist, chart weights."""

from __future__ import annotations

from typing import Any

from texasholdemgym.backend import bot_strategy, range_notation
from texasholdemgym.backend.poker_core.hole_grid import hole_to_range_grid_row_col


class RangeManager:
    """Owns per-seat range text + weight grids and revision counter for QML invalidation."""

    __slots__ = ("_grid", "_text", "_revision")

    def __init__(self) -> None:
        self._grid: dict[tuple[int, int], list[float]] = {}
        self._text: dict[tuple[int, int], str] = {}
        self._revision: int = 0

    @property
    def revision(self) -> int:
        return int(self._revision)

    def _touch(self) -> None:
        self._revision += 1

    def touch(self) -> None:
        """Increment revision (QML should re-read range grids after bulk preset changes)."""
        self._touch()

    def clear(self) -> None:
        self._grid.clear()
        self._text.clear()

    def ensure_grid(self, seat: int, layer: int) -> list[float]:
        k = (int(seat), int(layer))
        if k not in self._grid:
            self._grid[k] = [1.0] * (13 * 13)
        return self._grid[k]

    def chart_weights_for_hole(
        self, seat: int, h0: tuple[int, int], h1: tuple[int, int]
    ) -> tuple[float, float, float]:
        """Layer 0/1/2 matrix weights at this hole card (call / raise / bet), each in [0, 1]."""
        row, col = hole_to_range_grid_row_col(h0, h1)
        out: list[float] = []
        for layer in range(3):
            g = self._grid.get((int(seat), layer))
            if g is None or len(g) != 13 * 13:
                out.append(1.0)
                continue
            if max(g) <= 0:
                out.append(1.0)
                continue
            w = float(g[row * 13 + col])
            if w > 1.0:
                w = min(1.0, w / 100.0)
            out.append(max(0.0, min(1.0, w)))
        return (out[0], out[1], out[2])

    def play_metric_for_hole(self, seat: int, h0: tuple[int, int], h1: tuple[int, int]) -> float:
        """Max weight across the three range layers (upstream ``play_weight_cards``)."""
        a, b, c = self.chart_weights_for_hole(seat, h0, h1)
        return max(a, b, c)

    def load_preset_for_archetype(self, seat: int, archetype_index: int) -> None:
        """Fill 3 layers from the bot archetype's bundled range notation."""
        idx = int(archetype_index) % bot_strategy.STRATEGY_COUNT
        call_t, raise_t, open_t = bot_strategy.range_presets_for_index(idx)
        for layer, raw in enumerate((call_t, raise_t, open_t)):
            g = range_notation.parse_range_to_grid(raw)
            self._grid[(int(seat), layer)] = g
            self._text[(int(seat), layer)] = range_notation.format_grid_to_range(g)

    def apply_parsed_grid(self, seat: int, layer: int, grid: list[float]) -> None:
        self._grid[(int(seat), int(layer))] = grid
        self._text[(int(seat), int(layer))] = range_notation.format_grid_to_range(grid)
        self._touch()

    def export_formatted_text(self, seat: int, layer: int) -> str:
        g = self.ensure_grid(seat, layer)
        return range_notation.format_grid_to_range(g)

    def reset_seat_full_range(self, seat: int) -> None:
        full = [1.0] * (13 * 13)
        for layer in range(3):
            self._grid[(int(seat), layer)] = list(full)
            self._text[(int(seat), layer)] = "*"
        self._touch()

    def set_cell_weight(self, seat: int, layer: int, row: int, col: int, w: float) -> None:
        g = self.ensure_grid(seat, layer)
        g[int(row) * 13 + int(col)] = float(w)
        self._text[(int(seat), int(layer))] = range_notation.format_grid_to_range(g)
        self._touch()

    def bundle(self) -> dict[str, Any]:
        out: dict[str, Any] = {"text": {}, "grid": {}}
        for (seat, layer), txt in self._text.items():
            out["text"].setdefault(str(seat), {})[str(layer)] = txt
        for (seat, layer), gr in self._grid.items():
            out["grid"].setdefault(str(seat), {})[str(layer)] = list(gr)
        return out

    def apply_bundle(self, m: Any) -> None:
        if not isinstance(m, dict):
            return
        self._text.clear()
        self._grid.clear()
        tx = m.get("text")
        if isinstance(tx, dict):
            for sk, layers in tx.items():
                if not isinstance(layers, dict):
                    continue
                try:
                    si = int(sk)
                except Exception:
                    continue
                for lk, val in layers.items():
                    try:
                        li = int(lk)
                    except Exception:
                        continue
                    self._text[(si, li)] = str(val) if val is not None else ""
        gd = m.get("grid")
        if isinstance(gd, dict):
            for sk, layers in gd.items():
                if not isinstance(layers, dict):
                    continue
                try:
                    si = int(sk)
                except Exception:
                    continue
                for lk, vals in layers.items():
                    try:
                        li = int(lk)
                    except Exception:
                        continue
                    if isinstance(vals, list) and len(vals) == 13 * 13:
                        self._grid[(si, li)] = [float(x) for x in vals]
                    elif isinstance(vals, list):
                        g = [0.0] * (13 * 13)
                        for i, x in enumerate(vals[:169]):
                            g[i] = float(x)
                        self._grid[(si, li)] = g

    def load_persisted(self, db: Any) -> None:
        """Rehydrate grids + text from the app KV (see :mod:`game_state_persist`)."""
        if db is None:
            return
        from texasholdemgym.backend.game_state_persist import RANGES_BUNDLE_KEY

        self.apply_bundle(db.kv_get_json(RANGES_BUNDLE_KEY))
        self._touch()

    def save_persisted(self, db: Any) -> None:
        if db is None:
            return
        from texasholdemgym.backend.game_state_persist import RANGES_BUNDLE_KEY

        db.kv_set_json(RANGES_BUNDLE_KEY, self.bundle())
