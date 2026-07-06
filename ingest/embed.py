"""Embed tagged chunks and upsert them into a local Qdrant collection.

Dense (bge-small) + BM25 sparse vectors via fastembed (ONNX, no torch), stored as named vectors so
retrieval can fuse them (RRF). BM25's IDF is computed by Qdrant at query time. Qdrant runs embedded
against a local path — no Docker. Each chunk's spoiler metadata (reveals_beats, spoiler_level, region)
rides along as payload so the gate can run as a filter inside the search rather than as app-side code.

The embedded text is prefixed with the doc title + section so the vector carries a little context —
a lightweight take on contextual retrieval.

Run:  python ingest/embed.py
"""

import json
import os
import sys
from pathlib import Path
from typing import cast

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, Modifier, PointStruct, SparseVector, SparseVectorParams, VectorParams

ROOT = Path(__file__).resolve().parent.parent
GAME = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("GAME", "hollow_knight")).lower()
CHUNKS = ROOT / "data" / GAME / "chunks_tagged.json"
QDRANT_PATH = ROOT / "data" / "qdrant"             # shared store, one collection per game
COLLECTION = GAME
DENSE_MODEL = "BAAI/bge-small-en-v1.5"   # 384-dim dense, runs offline
SPARSE_MODEL = "Qdrant/bm25"             # lexical sparse for exact boss/item names; IDF at query time
DIM = 384
BATCH = 256


def embed_text(c):
    return f"{c['doc_title']} — {c['section']}\n{c['text']}"


def main():
    chunks = json.loads(CHUNKS.read_text())
    texts = [embed_text(c) for c in chunks]
    dense_model = TextEmbedding(DENSE_MODEL)
    sparse_model = SparseTextEmbedding(SPARSE_MODEL)

    client = QdrantClient(path=str(QDRANT_PATH))
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        COLLECTION,
        vectors_config={"dense": VectorParams(size=DIM, distance=Distance.COSINE)},
        sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
    )

    # embed + upsert in batches: bounded memory, and progress survives if the run is interrupted
    done = 0
    for start in range(0, len(chunks), BATCH):
        batch, btexts = chunks[start:start + BATCH], texts[start:start + BATCH]
        dvs = list(dense_model.embed(btexts, batch_size=64, parallel=0))
        svs = list(sparse_model.embed(btexts, batch_size=64, parallel=0))
        client.upsert(COLLECTION, [
            PointStruct(
                id=start + j,
                vector={
                    "dense": cast("list[float]", dv.tolist()),
                    "bm25": SparseVector(indices=cast("list[int]", sv.indices.tolist()),
                                         values=cast("list[float]", sv.values.tolist())),
                },
                payload={
                    "chunk_id": c["id"], "doc_title": c["doc_title"], "url": c["url"],
                    "section": c["section"], "text": c["text"], "reveals_beats": c["reveals_beats"],
                    "spoiler_level": c["spoiler_level"], "region": c["region"],
                },
            )
            for j, (c, dv, sv) in enumerate(zip(batch, dvs, svs))
        ])
        done += len(batch)
        print(f"  embedded {done}/{len(chunks)}", flush=True)

    print(f"upserted {done} chunks (dense + bm25) into '{COLLECTION}' at {QDRANT_PATH}")
    print("collection count:", client.count(COLLECTION).count)


if __name__ == "__main__":
    main()
