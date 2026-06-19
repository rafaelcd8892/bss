"""Shared deterministic hashing primitives.

A seeded, stateless hash that maps ``(seed, entity_id, salt)`` to a stable value.
Used wherever the platform needs reproducible pseudo-values without real data:
synthetic player metrics, synthetic team profiles, and the in-game RNG cursor.
"""

from __future__ import annotations

U32_MASK = 0xFFFFFFFF
U32_MAX = 4_294_967_295


def u32_mix(seed: int, entity_id: int, salt: int) -> int:
    mixed = (seed ^ (entity_id * 2_654_435_761) ^ (salt * 2_246_822_519)) & U32_MASK
    return (mixed * 1_664_525 + 1_013_904_223) & U32_MASK


def unit_interval(seed: int, entity_id: int, salt: int) -> float:
    return u32_mix(seed=seed, entity_id=entity_id, salt=salt) / U32_MAX


def scale(
    *,
    seed: int,
    entity_id: int,
    salt: int,
    minimum: float,
    maximum: float,
    decimals: int,
) -> float:
    raw = unit_interval(seed=seed, entity_id=entity_id, salt=salt)
    value = minimum + (maximum - minimum) * raw
    return round(value, decimals)
