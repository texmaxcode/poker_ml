"""`RangeManager` — 13×13 grids and chart weights for bot / Setup."""

from __future__ import annotations

from texasholdemgym.backend.range_manager import RangeManager


def test_range_manager_play_metric_defaults_full_range() -> None:
    rm = RangeManager()
    # Default grid is full 1.0 weights at any hole.
    h0, h1 = (14, 3), (13, 3)
    assert rm.play_metric_for_hole(0, h0, h1) == 1.0
    a, b, c = rm.chart_weights_for_hole(0, h0, h1)
    assert a == b == c == 1.0


def test_range_manager_touch_increments_revision() -> None:
    rm = RangeManager()
    assert rm.revision == 0
    rm.touch()
    assert rm.revision == 1


def test_range_manager_bundle_roundtrip() -> None:
    rm = RangeManager()
    rm.apply_parsed_grid(2, 1, [0.5] * (13 * 13))
    b = rm.bundle()
    rm2 = RangeManager()
    rm2.apply_bundle(b)
    assert len(rm2.ensure_grid(2, 1)) == 13 * 13
    assert abs(rm2.ensure_grid(2, 1)[0] - 0.5) < 1e-6


def test_range_manager_apply_bundle_ignores_non_dict() -> None:
    rm = RangeManager()
    rm.apply_parsed_grid(0, 0, [1.0] * (13 * 13))
    rm.apply_bundle("not a dict")  # type: ignore[arg-type]
    assert rm.revision == 1


def test_range_manager_load_preset_for_archetype() -> None:
    rm = RangeManager()
    rm.load_preset_for_archetype(4, archetype_index=6)
    assert len(rm.ensure_grid(4, 0)) == 13 * 13


def test_chart_weights_respect_custom_cell() -> None:
    rm = RangeManager()
    g = [0.0] * (13 * 13)
    g[0 * 13 + 1] = 0.25  # AKs cell (row 0, col 1)
    rm.apply_parsed_grid(0, 0, g)
    w0, _, _ = rm.chart_weights_for_hole(0, (14, 3), (13, 3))
    assert abs(w0 - 0.25) < 1e-6
