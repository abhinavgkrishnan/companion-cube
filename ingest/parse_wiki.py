"""Turn raw wikitext (data/raw/) into clean, structured docs (data/clean/).

Keeps the signal — lead + useful sections as prose, infobox facts, internal links, real categories —
and drops the noise: templates, refs, localisation, interwiki/category tags, boilerplate sections.
Disambiguation pages are skipped.

Regex-based cleaning is good enough for this wiki's markup; mwparserfromhell would be the swap for a
fully general parser.

Run:  python ingest/parse_wiki.py
"""

import json
import os
import re
import sys
from pathlib import Path

GAME = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("GAME", "hollow_knight")).lower()
DATA = Path(__file__).resolve().parent.parent / "data" / GAME
RAW = DATA / "raw"
CLEAN = DATA / "clean"

DROP_SECTIONS = {"names in other languages", "references", "gallery", "see also", "notes"}
CATEGORY_NOISE = re.compile(r"pages_with_missing|disambiguation", re.I)


def strip_templates(text):
    # remove {{...}} blocks, handling nesting by tracking brace depth
    out, depth, i = [], 0, 0
    while i < len(text):
        if text[i:i + 2] == "{{":
            depth += 1
            i += 2
        elif text[i:i + 2] == "}}" and depth:
            depth -= 1
            i += 2
        else:
            if depth == 0:
                out.append(text[i])
            i += 1
    return "".join(out)


def clean_prose(text):
    text = re.sub(r"<ref[^>]*?/>", "", text)
    text = re.sub(r"<ref[^>]*?>.*?</ref>", "", text, flags=re.S)
    text = strip_templates(text)
    text = text.replace("{{", "").replace("}}", "")             # leftover unbalanced braces
    text = re.sub(r"\[\[[a-z\-]+:[^\]]+\]\]", "", text)          # interwiki [[fr:...]]
    text = re.sub(r"\[\[Category:[^\]]+\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)   # [[target|label]] -> label
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)              # [[target]] -> target
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)   # [url label] -> label
    text = re.sub(r"</?[a-z][^>]*>", "", text)                   # stray html tags
    text = text.replace("'''", "").replace("''", "")            # bold / italic
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_infobox(wikitext):
    m = re.search(r"\{\{[^}\n]*Infobox", wikitext)
    if not m:
        return {}
    start, depth, i = m.start(), 0, m.start()
    while i < len(wikitext):                                     # brace-match the infobox block
        if wikitext[i:i + 2] == "{{":
            depth += 1
            i += 2
        elif wikitext[i:i + 2] == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                break
        else:
            i += 1
    block = wikitext[start:i]
    fields = {}
    for part in re.split(r"\n\s*\|", block):                     # params start with a newline-pipe
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        k, v = k.strip().lower(), clean_prose(v).strip()
        if k and v and "image" not in k and not k.startswith("{{"):
            fields[k] = v
    return fields


def internal_links(wikitext):
    seen, out = set(), []
    for link in re.findall(r"\[\[([^\]|:]+)(?:\|[^\]]+)?\]\]", wikitext):
        link = link.strip()
        if link and link not in seen:
            seen.add(link)
            out.append(link)
    return out


def split_sections(wikitext):
    parts = re.split(r"\n=+\s*(.+?)\s*=+\s*\n", wikitext)        # heading text captured
    sections = [("Summary", parts[0])]
    for i in range(1, len(parts), 2):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((parts[i].strip(), body))
    return sections


def is_disambiguation(cats, wikitext):
    return any("disambiguation" in c.lower() for c in cats) or "{{Disambiguation" in wikitext


def clean_categories(cats):
    return [c.replace("_", " ") for c in cats if not CATEGORY_NOISE.search(c)]


def parse_doc(rec):
    wt = rec["wikitext"]
    cats = rec.get("categories", [])
    if is_disambiguation(cats, wt):
        return None
    sections = []
    for heading, body in split_sections(wt):
        if heading.lower() in DROP_SECTIONS:
            continue
        text = clean_prose(body)
        if text:
            sections.append({"heading": heading, "text": text})
    return {
        "title": rec["title"],
        "url": rec["url"],
        "categories": clean_categories(cats),
        "infobox": parse_infobox(wt),
        "links": internal_links(wt),
        "sections": sections,
    }


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    for path in sorted(RAW.glob("*.json")):
        rec = json.loads(path.read_text())
        if "wikitext" not in rec:
            continue
        doc = parse_doc(rec)
        if doc is None:
            print(f"skip (disambiguation): {rec['title']}")
            continue
        (CLEAN / path.name).write_text(json.dumps(doc, indent=2, ensure_ascii=False))
        chars = sum(len(s["text"]) for s in doc["sections"])
        print(f"cleaned {doc['title']:22} {len(doc['sections'])} sec | "
              f"{chars:>5} prose chars | infobox:{len(doc['infobox'])} | links:{len(doc['links'])}")


if __name__ == "__main__":
    main()
