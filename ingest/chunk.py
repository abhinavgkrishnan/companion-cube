"""Split clean docs (data/clean/) into retrieval chunks (data/chunks.json).

One chunk per section; oversized sections split on paragraph boundaries with a little overlap so a
thought straddling the cut still shows up in both. Chunk ids are deterministic, so re-running is
stable. Spoiler metadata (reveals_beats, spoiler_level, region) is added later by the tagging step.

Run:  python ingest/chunk.py
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

GAME = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("GAME", "hollow_knight")).lower()
DATA = Path(__file__).resolve().parent.parent / "data" / GAME
CLEAN = DATA / "clean"
OUT = DATA / "chunks.json"

MAX_CHARS = 1200
OVERLAP_CHARS = 150


def split_long(text):
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) + 2 > MAX_CHARS:
            chunks.append(cur.strip())
            cur = cur[-OVERLAP_CHARS:] + "\n\n" + p        # carry a tail for boundary context
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def chunk_doc(doc):
    slug = doc["title"].replace(" ", "_").replace("/", "-").replace("'", "")
    out, idx = [], 0
    for sec in doc["sections"]:
        pieces = [sec["text"]] if len(sec["text"]) <= MAX_CHARS else split_long(sec["text"])
        for piece in pieces:
            out.append({
                "id": f"{slug}::{idx}",
                "doc_title": doc["title"],
                "url": doc["url"],
                "section": sec["heading"],
                "text": piece,
                "categories": doc.get("categories", []),
                "links": doc.get("links", []),
                "infobox": doc.get("infobox", {}),
            })
            idx += 1
    return out


def main():
    chunks = []
    for path in sorted(CLEAN.glob("*.json")):
        chunks.extend(chunk_doc(json.loads(path.read_text())))
    OUT.write_text(json.dumps(chunks, indent=2, ensure_ascii=False))

    per_doc = Counter(c["doc_title"] for c in chunks)
    print(f"{len(chunks)} chunks from {len(per_doc)} docs -> {OUT.name}")
    for title, n in sorted(per_doc.items()):
        print(f"  {n:>2}  {title}")


if __name__ == "__main__":
    main()
