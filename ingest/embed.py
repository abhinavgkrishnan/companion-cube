"""Embed tagged chunks and upsert them into a local Qdrant collection.

Dense vectors via fastembed (ONNX, no torch). Qdrant runs embedded against a local path — no Docker.
Each chunk's spoiler metadata (reveals_beats, spoiler_level, region) rides along as payload so the
gate can run as a filter inside the search rather than as app-side code.

The embedded text is prefixed with the doc title + section so the vector carries a little context —
a lightweight take on contextual retrieval.

Run:  python ingest/embed.py
"""

import json
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "data" / "chunks_tagged.json"
QDRANT_PATH = ROOT / "data" / "qdrant"
COLLECTION = "hollow_knight"
MODEL = "BAAI/bge-small-en-v1.5"   # 384-dim, small, runs offline
DIM = 384


def embed_text(c):
    return f"{c['doc_title']} — {c['section']}\n{c['text']}"


def main():
    chunks = json.loads(CHUNKS.read_text())

    embedder = TextEmbedding(MODEL)
    vectors = list(embedder.embed([embed_text(c) for c in chunks]))

    client = QdrantClient(path=str(QDRANT_PATH))
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        COLLECTION,
        vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
    )

    points = [
        PointStruct(
            id=i,
            vector=vec.tolist(),
            payload={
                "chunk_id": c["id"],
                "doc_title": c["doc_title"],
                "url": c["url"],
                "section": c["section"],
                "text": c["text"],
                "reveals_beats": c["reveals_beats"],
                "spoiler_level": c["spoiler_level"],
                "region": c["region"],
            },
        )
        for i, (c, vec) in enumerate(zip(chunks, vectors))
    ]
    client.upsert(COLLECTION, points)

    print(f"upserted {len(points)} chunks into '{COLLECTION}' at {QDRANT_PATH}")
    print("collection count:", client.count(COLLECTION).count)


if __name__ == "__main__":
    main()
