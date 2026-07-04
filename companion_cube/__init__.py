"""companion-cube — a spoiler-aware, progress-conditioned game guide.

Progress is a set of completed beats + unlocked abilities. Retrieval is gated on that set so the guide
never surfaces content from further ahead than the player actually is.
"""

import os

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # quiet the fastembed fork warning

from .models import Chunk, Mode, PlayerState, SpoilerLevel, SpoilerTolerance

__all__ = ["Chunk", "Mode", "PlayerState", "SpoilerLevel", "SpoilerTolerance"]
