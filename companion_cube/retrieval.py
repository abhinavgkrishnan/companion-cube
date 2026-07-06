"""Hybrid retrieval over Qdrant (dense + BM25, RRF-fused) with a cross-encoder rerank, and the spoiler
gate enforced as a payload filter on both arms.

The gate runs INSIDE the query: Qdrant excludes any chunk that reveals a beat the player hasn't
reached, so a spoiler can't come back even as the closest match. Mechanics chunks are always allowed;
a lenient tolerance also lets light content through. Player progress is supplied by the caller (the
client) — the retrieval layer never infers who may see what.

The filter mirrors the rule in filtering.decide(), expressed as Qdrant conditions: "reveals only
reached beats" becomes "reveals none of the uncompleted beats" (must_not · match-any).
"""

import atexit
import json
import re
from pathlib import Path
from typing import cast

from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Condition, FieldCondition, Filter, Fusion, FusionQuery, MatchAny, MatchValue, Prefetch, SparseVector,
)

from .models import PlayerState, SpoilerTolerance

ROOT = Path(__file__).resolve().parent.parent
QDRANT_PATH = ROOT / "data" / "qdrant"          # shared store, one collection per game
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-12-v2"
DEFAULT_GAME = "hollow_knight"

_dense = None
_sparse = None
_reranker = None
_client = None


def _resources():
    global _dense, _sparse, _reranker, _client
    if _dense is None:
        _dense = TextEmbedding(DENSE_MODEL)
    if _sparse is None:
        _sparse = SparseTextEmbedding(SPARSE_MODEL)
    if _reranker is None:
        _reranker = TextCrossEncoder(RERANK_MODEL)
    if _client is None:
        _client = QdrantClient(path=str(QDRANT_PATH))
        atexit.register(_client.close)   # close before interpreter teardown, not in __del__
    return _dense, _sparse, _reranker, _client


_SUFFIX = re.compile(r"\s*\((?:Hollow Knight|Silksong)\)$")

# true story/ending beats that stay hidden until earned, no matter where the player has reached
PROTECTED = {
    "hollow_knight": {
        "the_radiance", "absolute_radiance", "void_heart", "the_hollow_knight",
        "pure_vessel", "endings_(hollow_knight)",
    },
    "silksong": {
        "grand_mother_silk", "lost_lace", "the_unravelled", "endings_(silksong)",
    },
}


def _taxonomy(game):
    return json.loads((ROOT / "data" / game / "beats.json").read_text())


def gate_filter(player: PlayerState, tolerance: SpoilerTolerance, game: str) -> Filter:
    tax = _taxonomy(game)
    completed = player.completed_beats
    uncompleted = sorted(set(tax) - completed)
    # areas the player has reached -> the region names their content is tagged with
    reached_regions = sorted({
        _SUFFIX.sub("", tax[b]["title"]) for b in completed
        if b in tax and tax[b].get("type") == "area"
    })
    protected_unseen = sorted(PROTECTED.get(game, set()) - completed)

    should = [
        FieldCondition(key="spoiler_level", match=MatchValue(value="mechanics")),   # always safe
        # reveals only beats the player has already reached
        (Filter(must_not=[FieldCondition(key="reveals_beats", match=MatchAny(any=uncompleted))])
         if uncompleted else Filter()),
    ]
    protected_cond: "list[Condition] | None" = (
        [FieldCondition(key="reveals_beats", match=MatchAny(any=protected_unseen))]
        if protected_unseen else None
    )
    # content set in an area the player has reached — but never protected endgame content
    if reached_regions:
        should.append(Filter(
            must=[FieldCondition(key="region", match=MatchAny(any=reached_regions))],
            must_not=protected_cond,
        ))
    # general item/collectible pages carry no region (mask shards, charms) — surface the light ones,
    # never protected endgame content; the guide then tailors what it shows to the player's progress
    should.append(Filter(
        must=[FieldCondition(key="spoiler_level", match=MatchValue(value="light")),
              FieldCondition(key="region", match=MatchValue(value=""))],
        must_not=protected_cond,
    ))
    if tolerance is SpoilerTolerance.LIGHT:
        should.append(FieldCondition(key="spoiler_level", match=MatchValue(value="light")))
    return Filter(should=should)


def retrieve(query, player: PlayerState, tolerance: SpoilerTolerance = SpoilerTolerance.NONE,
             game: str = DEFAULT_GAME, k=5) -> list[dict]:
    """Return up to k gate-allowed payloads: dense + BM25 fused (RRF), then cross-encoder reranked."""
    dense, sparse, reranker, client = _resources()
    gate = gate_filter(player, tolerance, game)
    dvec = cast("list[float]", list(dense.embed([query]))[0].tolist())
    svec = list(sparse.embed([query]))[0]
    fetch = max(4 * k, 20)

    res = client.query_points(
        collection_name=game,
        prefetch=[
            Prefetch(query=dvec, using="dense", filter=gate, limit=fetch),
            Prefetch(query=SparseVector(indices=cast("list[int]", svec.indices.tolist()),
                                        values=cast("list[float]", svec.values.tolist())),
                     using="bm25", filter=gate, limit=fetch),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=fetch,
        with_payload=True,
    )
    payloads = [pt.payload or {} for pt in res.points]
    if not payloads:
        return []

    # cross-encoder rerank the fused candidates, keep the top k
    docs = [f"{p.get('doc_title', '')} — {p.get('section', '')}\n{p.get('text', '')}" for p in payloads]
    scores = list(reranker.rerank(query, docs))
    ranked = [p for _, p in sorted(zip(scores, payloads), key=lambda z: z[0], reverse=True)]
    return ranked[:k]
