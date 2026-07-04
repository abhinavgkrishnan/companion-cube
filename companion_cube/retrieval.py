"""Semantic retrieval over Qdrant with the spoiler gate enforced as a payload filter.

The gate runs INSIDE the query: Qdrant excludes any chunk that reveals a beat the player hasn't
reached, so a spoiler can't come back even as the closest match. Mechanics chunks are always allowed;
a lenient tolerance also lets light content through. Player progress is supplied by the caller (the
client) — the retrieval layer never infers who may see what.

The filter mirrors the rule in filtering.decide(), expressed as Qdrant conditions: "reveals only
reached beats" becomes "reveals none of the uncompleted beats" (must_not · match-any).
"""

import atexit
import json
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from .models import PlayerState, SpoilerTolerance

ROOT = Path(__file__).resolve().parent.parent
QDRANT_PATH = ROOT / "data" / "qdrant"
BEATS = ROOT / "data" / "beats.json"
COLLECTION = "hollow_knight"
MODEL = "BAAI/bge-small-en-v1.5"

_embedder = None
_client = None


def _resources():
    global _embedder, _client
    if _embedder is None:
        _embedder = TextEmbedding(MODEL)
    if _client is None:
        _client = QdrantClient(path=str(QDRANT_PATH))
        atexit.register(_client.close)   # close before interpreter teardown, not in __del__
    return _embedder, _client


def _all_beats():
    return set(json.loads(BEATS.read_text()).keys())


def gate_filter(player: PlayerState, tolerance: SpoilerTolerance) -> Filter:
    uncompleted = sorted(_all_beats() - player.completed_beats)

    # reveals only reached beats  ==  reveals none of the uncompleted beats
    reveals_nothing_unseen = (
        Filter(must_not=[FieldCondition(key="reveals_beats", match=MatchAny(any=uncompleted))])
        if uncompleted else Filter()   # nothing left uncompleted -> everything is fair game
    )

    should = [
        FieldCondition(key="spoiler_level", match=MatchValue(value="mechanics")),  # always safe
        reveals_nothing_unseen,
    ]
    if tolerance is SpoilerTolerance.LIGHT:
        should.append(FieldCondition(key="spoiler_level", match=MatchValue(value="light")))
    return Filter(should=should)


def retrieve(query, player: PlayerState, tolerance: SpoilerTolerance = SpoilerTolerance.NONE, k=5):
    """Return up to k gate-allowed chunk payloads, nearest first."""
    embedder, client = _resources()
    qvec = list(embedder.embed([query]))[0].tolist()
    res = client.query_points(
        collection_name=COLLECTION,
        query=qvec,
        query_filter=gate_filter(player, tolerance),
        limit=k,
        with_payload=True,
    )
    return [pt.payload for pt in res.points]
