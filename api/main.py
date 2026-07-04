"""FastAPI bridge exposing the gated retrieval + generation to the web UI.

Run from the repo root:  python -m uvicorn api.main:app --port 8000
(the `python -m` form puts the repo root on the import path so `api.main` resolves;
needs ANTHROPIC_API_KEY via .env, same as the tagging step.)

- GET  /api/beats?game=hollow_knight  -> the player-checkable progression, grouped
- POST /api/query                      -> a gated, cited answer over the real wiki

Gating note: the beat taxonomy covers every page, but only ability/area/boss beats are checkable, so
non-progression pages (charms, lore, items) are conservatively over-gated. Safe, never leaks; refining
the beat model to progression-only is a follow-up.
"""

import json
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from companion_cube.generate import generate
from companion_cube.models import Mode, PlayerState, SpoilerTolerance
from companion_cube.retrieval import retrieve

ROOT = Path(__file__).resolve().parent.parent
TYPE_GROUP = {"ability": "abilities", "area": "areas", "boss": "bosses"}
INLINE_CITE = re.compile(r"\s*\[[^\]]*::\d+\]")

app = FastAPI(title="CompanionCube API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _indexed(game: str) -> bool:
    return (ROOT / "data" / game / "beats.json").exists()


@app.get("/api/beats")
def beats(game: str = "hollow_knight"):
    if not _indexed(game):
        return {"abilities": [], "areas": [], "bosses": []}
    tax = json.loads((ROOT / "data" / game / "beats.json").read_text())
    out = {"abilities": [], "areas": [], "bosses": []}
    for bid, b in sorted(tax.items(), key=lambda kv: kv[1]["title"]):
        group = TYPE_GROUP.get(b["type"])
        if group:
            out[group].append({"id": bid, "title": b["title"]})
    return out


class Query(BaseModel):
    question: str
    game: str = "hollow_knight"
    mode: str = "hold_my_hand"
    tolerance: str = "none"
    completed_beats: list[str] = []


@app.post("/api/query")
def query(q: Query):
    if not _indexed(q.game):
        return {"answer": "*That kingdom is not yet mapped.*\n\nSilksong hasn't been indexed yet — check back soon.", "citations": []}

    player = PlayerState(completed_beats=set(q.completed_beats))
    tol = SpoilerTolerance(q.tolerance) if q.tolerance in ("none", "light") else SpoilerTolerance.NONE
    mode = Mode(q.mode) if q.mode in ("hold_my_hand", "gently_nudge") else Mode.HOLD_MY_HAND

    try:
        hits = retrieve(q.question, player, tol, game=q.game, k=6)
    except Exception:
        # collection not built yet (e.g. tagged but not embedded)
        return {"answer": "*That kingdom is not yet mapped.*\n\nIts pages are still being indexed — check back soon.", "citations": []}

    answer = INLINE_CITE.sub("", generate(q.question, hits, mode)).strip()

    seen, citations = set(), []
    for h in hits:
        if h["url"] not in seen:
            seen.add(h["url"])
            citations.append({"id": h["chunk_id"], "title": h["doc_title"], "section": h["section"], "url": h["url"]})
    return {"answer": answer, "citations": citations[:4]}
