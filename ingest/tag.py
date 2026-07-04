"""Tag chunks with spoiler metadata: derived beat taxonomy + Claude refinement (hybrid).

Beats (progression milestones) come from the wiki categories: abilities, bosses, areas, events.
For each doc, Claude reads its chunks + the taxonomy and assigns, per chunk:
  reveals_beats  - which milestones the chunk discloses (its own subject + any cross-references)
  spoiler_level  - mechanics (universal, always safe) | light (specific ability/area/mini-boss)
                   | major_plot (story, endings, major/final bosses)
  region         - the in-game area it concerns

Per-doc results are cached in data/tags/ — LLM calls are the expensive step, so this is resumable.
Assembles data/chunks_tagged.json and writes the taxonomy to data/beats.json.

Run:  python ingest/tag.py     (needs ANTHROPIC_API_KEY)
"""

import json
import os
import time
from collections import Counter
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    # read a gitignored .env so ANTHROPIC_API_KEY doesn't need to live in the shell profile
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
CLEAN = ROOT / "data" / "clean"
CHUNKS = ROOT / "data" / "chunks.json"
TAGS = ROOT / "data" / "tags"
OUT = ROOT / "data" / "chunks_tagged.json"
BEATS = ROOT / "data" / "beats.json"
MODEL = "claude-sonnet-4-6"


def slug(t):
    return t.replace(" ", "_").replace("/", "-").replace("'", "")


def beat_type(categories):
    c = " ".join(categories).lower()
    if "boss" in c:
        return "boss"
    if "area" in c:
        return "area"
    if "spells and abilities" in c:
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

PROMPT = """You are tagging chunks of a Hollow Knight wiki for a spoiler-aware guide.

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
- region: the in-game area it concerns, or "" if none.

Document: {title}  (type: {dtype}; categories: {cats})

Chunks:
{chunks}
"""


def tag_doc(client, doc, chunks, taxonomy):
    tax_str = "\n".join(f"- {bid} ({b['type']}): {b['title']}" for bid, b in taxonomy.items())
    chunks_str = "\n\n".join(f"[{c['id']}] (section: {c['section']})\n{c['text']}" for c in chunks)
    prompt = PROMPT.format(
        taxonomy=tax_str, title=doc["title"], dtype=beat_type(doc["categories"]),
        cats=", ".join(doc["categories"]), chunks=chunks_str,
    )
    resp = client.messages.create(
        model=MODEL, max_tokens=4000,
        tools=[TAG_TOOL], tool_choice={"type": "tool", "name": "submit_tags"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return {t["chunk_id"]: t for t in block.input["tags"]}
    return {}


def main():
    load_env()
    TAGS.mkdir(parents=True, exist_ok=True)
    docs = [json.loads(p.read_text()) for p in sorted(CLEAN.glob("*.json"))]
    taxonomy = build_taxonomy(docs)
    chunks = json.loads(CHUNKS.read_text())
    by_doc = {}
    for c in chunks:
        by_doc.setdefault(c["doc_title"], []).append(c)

    client = anthropic.Anthropic()
    all_tags = {}
    for doc in docs:
        cache = TAGS / f"{slug(doc['title'])}.json"
        if cache.exists():
            print(f"cached  {doc['title']}")
            all_tags.update(json.loads(cache.read_text()))
            continue
        try:
            tags = tag_doc(client, doc, by_doc.get(doc["title"], []), taxonomy)
        except Exception as e:
            print(f"FAIL    {doc['title']}: {e}")
            continue
        cache.write_text(json.dumps(tags, indent=2, ensure_ascii=False))
        all_tags.update(tags)
        print(f"tagged  {doc['title']:26} ({len(tags)} chunks)")
        time.sleep(0.5)

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


if __name__ == "__main__":
    main()
