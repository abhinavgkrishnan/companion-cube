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
import os
import re
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from companion_cube.generate import build_llm, generate, generate_stream
from companion_cube.models import Mode, PlayerState, SpoilerTolerance

ROOT = Path(__file__).resolve().parent.parent
TYPE_GROUP = {"ability": "abilities", "area": "areas", "boss": "bosses"}
INLINE_CITE = re.compile(r"\s*\[[^\]]*::\d+\]")
SUFFIX = re.compile(r"\s*\((?:Hollow Knight|Silksong)\)$")

# meta / overview / hub pages that aren't checkable progression items
EXCLUDE = {
    "spells and abilities", "areas", "bosses", "enemies", "charms", "items", "updates",
    "achievements", "npcs", "maps", "equipment", "fast travel", "hollow knight", "silksong",
    "the hunter's journal", "combat", "currency",
}

# rough progression order for the main items; anything unlisted falls to the end, alphabetical
ORDER = {
    "hollow_knight": {
        "areas": ["Forgotten Crossroads", "Greenpath", "Fungal Wastes", "Fog Canyon", "City of Tears",
                  "Crystal Peak", "Royal Waterways", "Deepnest", "Ancient Basin", "Kingdom's Edge",
                  "Queen's Gardens", "The Hive", "Colosseum of Fools", "The Abyss", "White Palace", "Godhome"],
        "abilities": ["Vengeful Spirit", "Mothwing Cloak", "Mantis Claw", "Desolate Dive", "Crystal Heart",
                      "Shade Soul", "Isma's Tear", "Monarch Wings", "Dream Nail", "Descending Dark",
                      "Shade Cloak", "Abyss Shriek", "Awoken Dream Nail", "Dream Gate", "King's Brand",
                      "Void Heart", "World Sense"],
        "bosses": ["False Knight", "Gruz Mother", "Vengefly King", "Hornet Protector", "Massive Moss Charger",
                   "Mantis Lords", "Soul Warrior", "Soul Master", "Crystal Guardian", "Dung Defender",
                   "Broken Vessel", "Nosk", "Watcher Knights", "Uumuu", "Hornet Sentinel", "Traitor Lord",
                   "The Collector", "The Hollow Knight", "The Radiance"],
    },
    "silksong": {
        # approximate Act 1 -> 3 progression; unlisted areas fall to the alphabetical tail
        "areas": ["Moss Grotto", "The Marrow", "Deep Docks", "Wormways", "Far Fields", "Greymoor",
                  "Mosslands", "Shellwood", "Bellhart", "Bone Bottom", "Blasted Steps", "Sinner's Road",
                  "Bilewater", "Hunter's March", "The Citadel", "Underworks", "Cogwork Core",
                  "Choral Chambers", "Whispering Vaults", "High Halls", "Grand Gate", "Whiteward",
                  "Memorium", "Putrified Ducts", "Sands of Karak", "The Abyss", "The Cradle", "Mount Fay",
                  "Verdania", "The Mist", "The Slab", "Red Memory", "Weavenest Atla", "Wisp Thicket"],
    },
}

JUNK_DOCS = EXCLUDE | {"gallery", "controls", "completion"}   # meta pages to keep out of retrieval

app = FastAPI(title="CompanionCube API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# warm the models off the request path — the import itself lives here too, since pulling in
# fastembed/onnxruntime takes ~10s on a cold machine and the port must bind before Fly's proxy
# gives up; a request that beats the warmup just waits on the same import + load locks
def _warmup():
    from companion_cube import retrieval
    retrieval._resources()


threading.Thread(target=_warmup, daemon=True).start()

# Per-IP rate limit (in-memory; fine for a single uvicorn worker) to blunt spam.
RATE_PER_MIN = int(os.getenv("RATE_PER_MIN", "15"))
RATE_PER_DAY = int(os.getenv("RATE_PER_DAY", "300"))
_hits: dict[str, deque] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


def _rate_ok(ip: str) -> bool:
    now = time.time()
    dq = _hits.setdefault(ip, deque())
    while dq and dq[0] < now - 86400:
        dq.popleft()
    if len(dq) >= RATE_PER_DAY or sum(ts > now - 60 for ts in dq) >= RATE_PER_MIN:
        return False
    dq.append(now)
    return True


def _indexed(game: str) -> bool:
    return (ROOT / "data" / game / "beats.json").exists()


@app.get("/api/beats")
def beats(game: str = "hollow_knight"):
    if not _indexed(game):
        return {"abilities": [], "areas": [], "bosses": []}
    tax = json.loads((ROOT / "data" / game / "beats.json").read_text())
    out = {"abilities": [], "areas": [], "bosses": []}
    for bid, b in tax.items():
        group = TYPE_GROUP.get(b["type"])
        if not group:
            continue
        title = SUFFIX.sub("", b["title"])
        if title.lower() in EXCLUDE:                 # drop category/overview hub pages
            continue
        out[group].append({"id": bid, "title": title})
    for group, items in out.items():                  # progression order, then alphabetical tail
        rank = {name: i for i, name in enumerate(ORDER.get(game, {}).get(group, []))}
        items.sort(key=lambda it: (rank.get(it["title"], len(rank)), it["title"]))
    return out


class Query(BaseModel):
    question: str
    game: str = "hollow_knight"
    mode: str = "hold_my_hand"
    tolerance: str = "none"
    completed_beats: list[str] = []
    collected_summary: str = ""    # checklist items already gathered — awareness only, never gates retrieval
    history: list[dict] = []       # recent [{role, content}] turns from the client, for context
    provider: str | None = None    # BYOK: anthropic | openai | gemini | openrouter (else server default)
    api_key: str | None = None
    model: str | None = None
    stream: bool = False           # NDJSON token stream instead of a single JSON answer


def _history(turns):
    """Keep the last few turns, alternating and starting with the user (as the model requires)."""
    hist = [{"role": t.get("role"), "content": t.get("content", "")}
            for t in turns if t.get("role") in ("user", "assistant")][-6:]
    if hist and hist[0]["role"] != "user":
        hist = hist[1:]
    return hist


def _progress_summary(game: str, completed: list[str]) -> str:
    """A short, human phrasing of where the player stands, for the guide to tailor its answer."""
    if not completed or not _indexed(game):
        return ""
    tax = json.loads((ROOT / "data" / game / "beats.json").read_text())
    groups = {"area": [], "ability": [], "boss": []}
    for b in completed:
        info = tax.get(b)
        if info and info["type"] in groups:
            groups[info["type"]].append(SUFFIX.sub("", info["title"]))
    parts = []
    if groups["area"]:
        parts.append("reached " + ", ".join(sorted(groups["area"])))
    if groups["ability"]:
        parts.append("wields " + ", ".join(sorted(groups["ability"])))
    if groups["boss"]:
        parts.append("has bested " + ", ".join(sorted(groups["boss"])))
    return "; ".join(parts)


MODEL_ERROR = ("*The words would not come.*\n\nThe model could not be reached. If you set your own "
               "API key in Settings, check that it is valid and has credit.")


def _prepare(q: Query, request: Request):
    """Everything before generation: rate limit, gate, retrieve. Returns (error, hits, citations)."""
    if not _rate_ok(_client_ip(request)):
        return "*Rest a moment.*\n\nYou are asking faster than I can answer — try again in a little while.", [], []
    if not _indexed(q.game):
        return "*That kingdom is not yet mapped.*\n\nSilksong hasn't been indexed yet — check back soon.", [], []

    player = PlayerState(completed_beats=set(q.completed_beats))
    tol = SpoilerTolerance(q.tolerance) if q.tolerance in ("none", "light") else SpoilerTolerance.NONE

    from companion_cube.retrieval import retrieve

    try:
        hits = retrieve(q.question, player, tol, game=q.game, k=12)
    except Exception:
        # collection not built yet (e.g. tagged but not embedded)
        return "*That kingdom is not yet mapped.*\n\nIts pages are still being indexed — check back soon.", [], []

    hits = [h for h in hits if SUFFIX.sub("", h["doc_title"]).lower() not in JUNK_DOCS][:6]
    seen, citations = set(), []
    for h in hits:
        if h["url"] not in seen:
            seen.add(h["url"])
            citations.append({"id": h["chunk_id"], "title": h["doc_title"], "section": h["section"], "url": h["url"]})
    return None, hits, citations[:4]


def _ndjson(obj) -> str:
    return json.dumps(obj) + "\n"


def _say(text: str):
    """A fixed message shaped like a stream, so the client has one code path."""
    yield _ndjson({"type": "citations", "citations": []})
    yield _ndjson({"type": "delta", "text": text})
    yield _ndjson({"type": "done"})


def _stream_answer(q: Query, mode: Mode, hits: list, citations: list):
    yield _ndjson({"type": "citations", "citations": citations})
    llm = build_llm(q.provider, q.api_key, q.model)
    progress = _progress_summary(q.game, q.completed_beats)
    collected = q.collected_summary[:1500]
    raw, sent = "", ""
    try:
        for chunk in generate_stream(q.question, hits, mode, game=q.game, progress=progress,
                                     history=_history(q.history), llm=llm, collected=collected):
            raw += chunk
            clean = INLINE_CITE.sub("", raw)
            # hold back a trailing "[" — it may be the start of a cite marker still arriving
            cut = clean.rfind("[")
            safe = clean if cut == -1 or "]" in clean[cut:] or len(clean) - cut > 80 else clean[:cut]
            if len(safe) > len(sent):
                yield _ndjson({"type": "delta", "text": safe[len(sent):]})
                sent = safe
        clean = INLINE_CITE.sub("", raw)
        if len(clean) > len(sent):
            yield _ndjson({"type": "delta", "text": clean[len(sent):]})
        if not raw:
            yield _ndjson({"type": "error", "message": MODEL_ERROR})
            return
    except Exception:
        yield _ndjson({"type": "error", "message": MODEL_ERROR})
        return
    yield _ndjson({"type": "done"})


@app.post("/api/query")
def query(q: Query, request: Request):
    error, hits, citations = _prepare(q, request)
    mode = Mode(q.mode) if q.mode in ("hold_my_hand", "gently_nudge") else Mode.HOLD_MY_HAND

    if q.stream:
        gen = _say(error) if error else _stream_answer(q, mode, hits, citations)
        return StreamingResponse(gen, media_type="application/x-ndjson")

    if error:
        return {"answer": error, "citations": []}
    progress = _progress_summary(q.game, q.completed_beats)
    llm = build_llm(q.provider, q.api_key, q.model)
    try:
        answer = INLINE_CITE.sub("", generate(q.question, hits, mode, game=q.game, progress=progress,
                                              history=_history(q.history), llm=llm,
                                              collected=q.collected_summary[:1500])).strip()
    except Exception:
        return {"answer": MODEL_ERROR, "citations": []}
    return {"answer": answer, "citations": citations}
