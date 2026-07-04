"""Domain types.

Progress is a set (completed beats + unlocked abilities), not a linear position — that's what lets
this work for open-world games where the player can be almost anywhere. Spoiler-gating then reduces
to a set-membership check against that progress.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    HOLD_MY_HAND = "hold_my_hand"   # full step-by-step walkthrough
    GENTLY_NUDGE = "gently_nudge"   # a hint that points the way without solving it


class SpoilerLevel(str, Enum):
    MECHANICS = "mechanics"      # how systems work (healing, nail) — safe at any point
    LIGHT = "light"              # location / mini-boss hints
    MAJOR_PLOT = "major_plot"    # story beats, bosses, endings


class SpoilerTolerance(str, Enum):
    NONE = "none"    # never surface beats the player hasn't reached
    LIGHT = "light"  # allow light content slightly ahead


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    region: str
    reveals_beats: frozenset[str]   # beats this excerpt would disclose
    spoiler_level: SpoilerLevel
    entities: frozenset[str]        # named bosses/items — feeds exact-match retrieval
    source: str

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        return cls(
            id=d["id"],
            text=d["text"],
            region=d["region"],
            reveals_beats=frozenset(d.get("reveals_beats", [])),
            spoiler_level=SpoilerLevel(d["spoiler_level"]),
            entities=frozenset(d.get("entities", [])),
            source=d.get("source", "unknown"),
        )


@dataclass
class PlayerState:
    completed_beats: set[str] = field(default_factory=set)
    unlocked_abilities: set[str] = field(default_factory=set)
    current_region: str | None = None
