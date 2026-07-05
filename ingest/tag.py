"""Tag chunks with spoiler metadata: derived beat taxonomy + Claude refinement (hybrid).

Beats (progression milestones) come from the wiki categories: abilities, bosses, areas, events.
For each doc, Claude reads its chunks + the taxonomy and assigns, per chunk:
  reveals_beats / spoiler_level / region.

The taxonomy + instructions are identical across every call, so they live in a cached system block
(Anthropic prompt caching): the constant prefix is written once and read cheaply on every later doc.
Only each doc's chunks vary, after the cache breakpoint.

Per-doc results are cached in data/tags/ — LLM calls are the expensive step, so this is resumable.
Assembles data/chunks_tagged.json and writes the taxonomy to data/beats.json.

Run:  python ingest/tag.py     (needs ANTHROPIC_API_KEY, via env or .env)
"""

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
GAME = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("GAME", "hollow_knight")).lower()
DATA = ROOT / "data" / GAME
CLEAN = DATA / "clean"
CHUNKS = DATA / "chunks.json"
TAGS = DATA / "tags"
OUT = DATA / "chunks_tagged.json"
BEATS = DATA / "beats.json"
MODEL = "claude-sonnet-4-6"


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def slug(t):
    return t.replace(" ", "_").replace("/", "-").replace("'", "")


def beat_type(categories):
    c = " ".join(categories).lower()
    if "boss" in c:
        return "boss"
    if "area" in c:
        return "area"
    if "abilities" in c:                 # "Spells and Abilities" (HK) / "Skills and Abilities" (Silksong)
        return "ability"
    return "event"


def build_taxonomy(docs):
    return {
        slug(d["title"]).lower(): {"title": d["title"], "type": beat_type(d["categories"])}
        for d in docs
    }


TAG_TOOL = {
    "name": "submit_tags",
    "description": "Return spoiler tags for each provided chunk.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "reveals_beats": {"type": "array", "items": {"type": "string"}},
                        "spoiler_level": {"type": "string",
                                          "enum": ["mechanics", "light", "major_plot"]},
                        "region": {"type": "string"},
                    },
                    "required": ["chunk_id", "reveals_beats", "spoiler_level", "region"],
                },
            }
        },
        "required": ["tags"],
    },
}

INSTRUCTIONS = """You are tagging chunks of a Hollow Knight wiki for a spoiler-aware guide.

Beat taxonomy (canonical progression milestones — use these exact ids in reveals_beats):
{taxonomy}

spoiler_level:
- mechanics: ONLY universal, game-wide systems safe at ANY point (how SOUL, healing, or the nail work in general). A mechanics chunk reveals NO specific ability, boss, or area. Anything about a SPECIFIC ability/boss/area — including its combat tactics or charm interactions — is NOT mechanics.
- light: reveals a specific ability, area, or mini-boss.
- major_plot: reveals story beats, endings, or major/final bosses.

For each chunk, decide:
- reveals_beats: which beat ids the chunk discloses. Include the chunk's own subject if it reveals that
  ability/boss/area exists or how to obtain/beat/reach it, PLUS any other beats it cross-references.
- spoiler_level: per the definitions above. A chunk with any reveals_beats must NOT be mechanics.
- region: the in-game area it concerns, or "" if none."""

USER = """Document: {title}  (type: {dtype}; categories: {cats})

Chunks:
{chunks}"""


def tag_doc(client, doc, chunks, system_blocks):
    chunks_str = "\n\n".join(f"[{c['id']}] (section: {c['section']})\n{c['text']}" for c in chunks)
    user = USER.format(
        title=doc["title"], dtype=beat_type(doc["categories"]),
        cats=", ".join(doc["categories"]), chunks=chunks_str,
    )
    resp = client.messages.create(
        model=MODEL, max_tokens=4000,
        system=system_blocks,                                  # cached constant prefix
        tools=[TAG_TOOL], tool_choice={"type": "tool", "name": "submit_tags"},
        messages=[{"role": "user", "content": user}],
    )
    tags = {}
    for block in resp.content:
        if block.type == "tool_use":
            tags = {t["chunk_id"]: t for t in block.input["tags"]}
    return tags, resp.usage


def main():
    load_env()
    TAGS.mkdir(parents=True, exist_ok=True)
    docs = [json.loads(p.read_text()) for p in sorted(CLEAN.glob("*.json"))]
    taxonomy = build_taxonomy(docs)
    tax_str = "\n".join(f"- {bid} ({b['type']}): {b['title']}" for bid, b in taxonomy.items())
    system_blocks = [{
        "type": "text",
        "text": INSTRUCTIONS.format(taxonomy=tax_str),
        "cache_control": {"type": "ephemeral"},                # cache taxonomy + instructions (+ tools)
    }]

    chunks = json.loads(CHUNKS.read_text())
    by_doc = {}
    for c in chunks:
        by_doc.setdefault(c["doc_title"], []).append(c)

    client = anthropic.Anthropic()
    all_tags = {}
    cache_read = cache_write = 0
    for doc in docs:
        cache = TAGS / f"{slug(doc['title'])}.json"
        if cache.exists():
            all_tags.update(json.loads(cache.read_text()))
            continue
        try:
            tags, usage = tag_doc(client, doc, by_doc.get(doc["title"], []), system_blocks)
        except Exception as e:
            print(f"FAIL    {doc['title']}: {e}")
            continue
        cache.write_text(json.dumps(tags, indent=2, ensure_ascii=False))
        all_tags.update(tags)
        cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0
        print(f"tagged  {doc['title'][:28]:28} ({len(tags)} chunks)  "
              f"cache_read={getattr(usage, 'cache_read_input_tokens', 0)}")
        time.sleep(0.3)

    for c in chunks:
        t = all_tags.get(c["id"], {})
        beats = t.get("reveals_beats", [])
        level = t.get("spoiler_level", "light")
        if level == "mechanics" and beats:      # mechanics must disclose nothing specific
            level = "light"
        c["reveals_beats"] = beats
        c["spoiler_level"] = level
        c["region"] = t.get("region", "")
    OUT.write_text(json.dumps(chunks, indent=2, ensure_ascii=False))
    BEATS.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False))

    lv = Counter(c["spoiler_level"] for c in chunks)
    print(f"\nassembled {OUT.name}: {dict(lv)} across {len(chunks)} chunks; {len(taxonomy)} beats")
    print(f"prompt cache: {cache_write} tokens written, {cache_read} read")


if __name__ == "__main__":
    main()
