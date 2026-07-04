"""Demo: the same question for a mid-game vs late-game player, over real Qdrant retrieval.

    python -m companion_cube.cli
"""

import json
import os
import sys
from pathlib import Path

from .generate import generate
from .models import Mode, PlayerState, SpoilerTolerance
from .retrieval import retrieve

GAME = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("GAME", "hollow_knight")).lower()
ROOT = Path(__file__).resolve().parent.parent
BEATS = ROOT / "data" / GAME / "beats.json"


def _scenario(title, query, player, mode, tolerance=SpoilerTolerance.NONE):
    print("=" * 78)
    print(f"SCENARIO: {title}")
    print(f"  completed_beats={len(player.completed_beats)}  mode={mode.value}  tolerance={tolerance.value}")
    print(f"  Q: {query}")
    hits = retrieve(query, player, tolerance, game=GAME, k=4)
    print(f"  retrieved: {[h['chunk_id'] for h in hits] or 'none (all gated)'}")
    print("  --- answer ---")
    print("  " + generate(query, hits, mode, game=GAME).replace("\n", "\n  "))
    print()


def main():
    all_beats = set(json.loads(BEATS.read_text()))
    # a mid-game player: early abilities + areas, but nothing endgame
    mid = PlayerState(completed_beats={
        "mothwing_cloak", "greenpath", "false_knight", "mantis_claw", "crystal_heart", "crystal_peak",
    })
    late = PlayerState(completed_beats=set(all_beats))

    _scenario("Mid-game player asks how to get a dash",
              "how do I get a dash ability", mid, Mode.HOLD_MY_HAND)
    _scenario("Mid-game player asks about the ending (should be gated)",
              "what happens at the end of the game", mid, Mode.GENTLY_NUDGE)
    _scenario("Late-game player asks about the ending (now unlocked)",
              "what happens at the end of the game", late, Mode.HOLD_MY_HAND)


if __name__ == "__main__":
    main()
