"""Minimum legal raise sizing (big blind floor, last raise increment)."""


def min_raise_increment_chips(big_blind: int, last_raise_increment: int) -> int:
    """Smallest raise step: at least one big blind, and at least the previous raise size."""
    return int(max(int(big_blind), int(last_raise_increment)))
