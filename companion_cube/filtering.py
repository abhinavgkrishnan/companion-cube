"""Spoiler gate.

A chunk is retrievable only if it doesn't disclose a beat the player hasn't reached yet. Structurally
this is access control — the player's progress is their permission set. Pure functions, no deps, so the
guarantee is easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Chunk, PlayerState, SpoilerLevel, SpoilerTolerance


@dataclass(frozen=True)
class GateDecision:
    chunk: Chunk
    allowed: bool
    reason: str


def decide(chunk: Chunk, player: PlayerState, tolerance: SpoilerTolerance) -> GateDecision:
    # mechanics never spoil anything
    if chunk.spoiler_level is SpoilerLevel.MECHANICS:
        return GateDecision(chunk, True, "mechanics: always safe")

    # safe if it reveals nothing the player hasn't already seen
    undisclosed = chunk.reveals_beats - player.completed_beats
    if not undisclosed:
        return GateDecision(chunk, True, "reveals only already-completed beats")

    # let an adventurous player peek at light content slightly ahead
    if tolerance is SpoilerTolerance.LIGHT and chunk.spoiler_level is SpoilerLevel.LIGHT:
        return GateDecision(chunk, True, "light content permitted by tolerance")

    return GateDecision(chunk, False, f"would reveal unseen beats: {sorted(undisclosed)}")


def gate(
    chunks: list[Chunk], player: PlayerState, tolerance: SpoilerTolerance
) -> list[GateDecision]:
    return [decide(c, player, tolerance) for c in chunks]
