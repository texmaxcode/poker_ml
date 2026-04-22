"""Bot archetypes + heuristics aligned with upstream `texmaxcode/poker` (`bot.cpp` / `bot.hpp`)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

# Mirrors `enum class BotStrategy` order in `bot.hpp`.
STRATEGY_NAMES: tuple[str, ...] = (
    "Always call (test)",
    "Rock",
    "Nit",
    "Tight–aggressive",
    "Loose–passive",
    "Loose–aggressive",
    "Balanced",
    "Maniac",
    "GTO (heuristic)",
)

STRATEGY_COUNT = len(STRATEGY_NAMES)

# Default preflop range strings per layer (Call / Raise / Open) when a bot archetype is selected in Setup.
# Parsed by `range_notation.parse_range_to_grid`; stored in `seat_ranges_v1` with the grids.
STRATEGY_RANGE_PRESETS: tuple[tuple[str, str, str], ...] = (
    ("*", "*", "*"),  # Always call (test)
    (
        "TT+,ATs+,KQs+,QJs,JTs,AQo,AKo,99s,88s,77s",
        "QQ+,AKs,AKo",
        "JJ+,ATs+,KQs",
    ),  # Rock
    (
        "JJ+,ATs+,KQs,QJs,AQo,AKo,TTs",
        "QQ+,AKs,AKo",
        "TT+,AKs,AQs",
    ),  # Nit
    (
        "99+,ATs+,KQs+,QJs,AQo,AKo,JTs",
        "TT+,AQs,AKs,AKo",
        "99+,ATs+,KQs",
    ),  # Tight–aggressive
    (
        "22+,A2s+,K9s+,Q9s+,J8s+,T8s+,98s,87s,76s,65s,54s",
        "22+,A8s+,KTs+,QTs+,JTs",
        "55+,A9s+,KQs,QJs",
    ),  # Loose–passive
    (
        "22+,A2s+,K5s+,Q8s+,J8s+,T8s+,98s,87s,76s,65s,54s",
        "22+,A5s+,KTs+,QTs+,J9s+",
        "66+,ATs+,KQs,QJo",
    ),  # Loose–aggressive
    (
        "22+,A2s+,K9s+,QTs+,JTs,T9s,98s,87s,76s,65s,54s",
        "99+,ATs+,KQs,QJs",
        "77+,A9s+,KQs,JTs",
    ),  # Balanced
    (
        "22+,A2s+,K2s+,Q5s+,J7s+,T7s+,97s+,87s,76s,65s,54s,43s",
        "22+,A2s+,K9s+,QTs+",
        "22+,A5s+,JTs+,98s",
    ),  # Maniac
    (
        "22+,A2s+,KTs+,QTs+,JTs,98s+,87s,76s",
        "TT+,ATs+,KQs,QJs",
        "88+,A9s+,KQs,JTs",
    ),  # GTO (heuristic)
)


def range_presets_for_index(idx: int) -> tuple[str, str, str]:
    i = int(idx) % STRATEGY_COUNT
    return STRATEGY_RANGE_PRESETS[i]


@dataclass(frozen=True)
class BotParams:
    preflop_exponent: float
    postflop_exponent: float
    facing_raise_bonus: float
    facing_raise_tight_mul: float
    open_bet_bonus: float
    open_bet_tight_mul: float
    bb_checkraise_bonus: float
    bb_checkraise_tight_mul: float
    buy_in_bb: int


def params_for_index(idx: int) -> BotParams:
    """`BotParams params_for(BotStrategy s)` from upstream `bot.cpp`."""
    i = int(idx)
    if i == 0:  # AlwaysCall
        return BotParams(0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 100)
    if i == 1:  # Rock
        return BotParams(3.2, 2.8, 0.0, 0.35, 0.0, 0.4, 0.0, 0.3, 100)
    if i == 2:  # Nit
        return BotParams(2.6, 2.4, 0.0, 0.35, 0.0, 0.4, 0.0, 0.3, 100)
    if i == 3:  # TightAggressive
        return BotParams(2.0, 0.85, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 100)
    if i == 4:  # LoosePassive
        return BotParams(0.75, 1.8, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 100)
    if i == 5:  # LooseAggressive
        return BotParams(0.55, 0.65, 0.18, 1.0, 0.2, 1.0, 0.22, 1.0, 100)
    if i == 6:  # Balanced
        return BotParams(1.15, 1.1, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 100)
    if i == 7:  # Maniac
        return BotParams(0.35, 0.4, 0.18, 1.0, 0.2, 1.0, 0.22, 1.0, 100)
    if i == 8:  # GTOHeuristic
        return BotParams(1.12, 1.08, 0.09, 0.82, 0.10, 0.78, 0.11, 0.75, 100)
    return BotParams(1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 100)


def apply_bot_params_to_strategy_fields(p: Any, bp: BotParams) -> None:
    """Copy into `StrategyTuning`-style object (camelCase attrs)."""
    p.preflopExponent = float(bp.preflop_exponent)
    p.postflopExponent = float(bp.postflop_exponent)
    p.facingRaiseBonus = float(bp.facing_raise_bonus)
    p.facingRaiseTightMul = float(bp.facing_raise_tight_mul)
    p.openBetBonus = float(bp.open_bet_bonus)
    p.openBetTightMul = float(bp.open_bet_tight_mul)
    p.bbCheckraiseBonus = float(bp.bb_checkraise_bonus)
    p.bbCheckraiseTightMul = float(bp.bb_checkraise_tight_mul)
    p.buyInBb = int(bp.buy_in_bb)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def bot_continue_trial(exponent: float, metric01: float, rng: random.Random) -> bool:
    m = _clamp01(metric01)
    exp = max(1e-6, float(exponent))
    t = math.pow(m, exp)
    return rng.random() < t


def bot_preflop_continue_p(p: Any, range_weight: float, rng: random.Random) -> bool:
    return bot_continue_trial(float(p.preflopExponent), range_weight, rng)


def bot_postflop_continue_p(p: Any, hand_strength01: float, rng: random.Random) -> bool:
    return bot_continue_trial(float(p.postflopExponent), hand_strength01, rng)


def bot_wants_raise_after_continue_p(p: Any, metric01: float, rng: random.Random) -> bool:
    m = _clamp01(metric01)
    prob = 0.08 + 0.35 * m
    prob += float(p.facingRaiseBonus)
    prob *= float(p.facingRaiseTightMul)
    prob = max(0.0, min(0.55, prob))
    return rng.random() < prob


def bot_wants_open_bet_postflop_p(p: Any, hand_strength01: float, rng: random.Random) -> bool:
    h = _clamp01(hand_strength01)
    prob = 0.06 + 0.45 * h
    prob += float(p.openBetBonus)
    prob *= float(p.openBetTightMul)
    prob = max(0.0, min(0.65, prob))
    return rng.random() < prob


def bot_bb_check_or_raise_p(p: Any, range_weight: float, rng: random.Random) -> bool:
    w = _clamp01(range_weight)
    prob = 0.12 + 0.4 * w
    prob += float(p.bbCheckraiseBonus)
    prob *= float(p.bbCheckraiseTightMul)
    prob = max(0.0, min(0.7, prob))
    return rng.random() < prob


def rng_passes_layer_gate(layer_w: float, play_w: float, rng: random.Random) -> bool:
    """Upstream `rng_passes_layer_gate` — raise/bet layer vs max play weight."""
    if play_w <= 1e-15:
        return False
    p = min(1.0, max(0.0, float(layer_w) / float(play_w)))
    return rng.random() < p


def strategy_summary(idx: int) -> str:
    """Short help text for Setup (`getStrategySummary`)."""
    i = int(idx)
    if not (0 <= i < STRATEGY_COUNT):
        return ""
    bp = params_for_index(i)
    name = STRATEGY_NAMES[i]
    lines = [
        name,
        "",
        f"Preflop exponent: {bp.preflop_exponent}",
        "  Continue preflop with probability w^exponent where w is the chart weight for your hole cards.",
        "",
        f"Postflop exponent: {bp.postflop_exponent}",
        "  Uses estimated hand strength h in [0,1]; continue chance is h^exponent.",
        "",
        f"Facing raise: bonus {bp.facing_raise_bonus}, tight × {bp.facing_raise_tight_mul}",
        f"Postflop open (checked to): bonus {bp.open_bet_bonus}, tight × {bp.open_bet_tight_mul}",
        f"BB preflop check-raise: bonus {bp.bb_checkraise_bonus}, tight × {bp.bb_checkraise_tight_mul}",
        "",
        "Editable per seat in Bots & ranges; changing the archetype reloads these defaults.",
    ]
    if i == 8:
        lines.extend(
            [
                "",
                "GTO note: frequency-style heuristic inspired by balanced play — not a full equilibrium solver.",
            ]
        )
    return "\n".join(lines)
