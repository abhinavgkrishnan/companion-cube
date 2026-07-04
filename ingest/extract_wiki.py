"""Pull raw wikitext + metadata from the Hollow Knight wiki via the MediaWiki API.

Source: hollowknight.wiki (MediaWiki 1.41, CC BY-SA 3.0). API lives at /mw/api.php, not /w/.
The wiki hosts both Hollow Knight and Silksong, so we enumerate every non-redirect page and keep only
those matching the selected GAME (Hollow Knight by default; see GAME below). Wikitext keeps everything
downstream tagging needs:
[[Category:...]] tags, {{Infobox}} templates, section headings, internal links. One JSON per kept page
in data/raw/, source URL kept for attribution.

Resumable: kept pages are cached as files, and every processed title is recorded in a ledger so the
discarded Silksong pages aren't re-fetched on a re-run.

Run:  python ingest/extract_wiki.py
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://hollowknight.wiki/mw/api.php"
PAGE_BASE = "https://hollowknight.wiki/w/"
UA = "companion-cube/0.1 (portfolio RAG project; github.com/abhinavgkrishnan)"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
LEDGER = OUT / ".seen.json"
DELAY_S = 0.3

# which game's pages to keep — set via first CLI arg or the GAME env var
#   python ingest/extract_wiki.py            -> hollow_knight (default)
#   python ingest/extract_wiki.py silksong   -> silksong
#   GAME=all python ingest/extract_wiki.py   -> both
GAME = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("GAME", "hollow_knight")).lower()


def api(**params):
    params["format"] = "json"
    params.setdefault("maxlag", 5)          # MediaWiki politeness
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def all_titles():
    titles = []
    params = dict(action="query", list="allpages", apnamespace=0,
                  aplimit=500, apfilterredir="nonredirects")
    while True:
        d = api(**params)
        titles += [x["title"] for x in d["query"]["allpages"]]
        if "continue" in d:
            params.update(d["continue"])
        else:
            return titles


def page_game(title, categories):
    """Which game a page belongs to, from its categories — or None if ambiguous/neither."""
    cats = [c.replace("_", " ").lower() for c in categories]
    if any("disambiguation" in c for c in cats):
        return None
    hk = any("(hollow knight)" in c or c == "hollow knight" for c in cats)
    ss = any("(silksong)" in c or c == "silksong" for c in cats) or "(silksong)" in title.lower()
    if hk and not ss:
        return "hollow_knight"
    if ss and not hk:
        return "silksong"
    return None


def wanted(game):
    return game is not None and (GAME == "all" or game == GAME)


def fetch(title):
    d = api(action="parse", page=title, redirects=1, prop="wikitext|categories|sections")
    if "error" in d:
        return None
    p = d["parse"]
    return {
        "title": p["title"],
        "url": PAGE_BASE + urllib.parse.quote(p["title"].replace(" ", "_")),
        "pageid": p.get("pageid"),
        "categories": [c["*"] for c in p.get("categories", [])],
        "sections": [{"line": s["line"], "level": s["level"]} for s in p.get("sections", [])],
        "wikitext": p["wikitext"]["*"],
    }


def slug(title):
    return title.replace(" ", "_").replace("/", "-").replace("'", "")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    seen = set(json.loads(LEDGER.read_text())) if LEDGER.exists() else set()
    titles = all_titles()
    kept = sum(1 for t in titles if (OUT / f"{slug(t)}.json").exists())
    print(f"{len(titles)} non-redirect pages; keeping game={GAME}; {kept} already cached")

    for i, title in enumerate(titles):
        if title in seen or (OUT / f"{slug(title)}.json").exists():
            continue
        try:
            rec = fetch(title)
        except Exception as e:
            print(f"FAIL {title}: {e}")
            continue
        seen.add(title)
        game = page_game(rec["title"], rec["categories"]) if rec else None
        if rec and wanted(game):
            rec["game"] = game
            (OUT / f"{slug(rec['title'])}.json").write_text(
                json.dumps(rec, indent=2, ensure_ascii=False))
            kept += 1
        if i % 25 == 0:
            LEDGER.write_text(json.dumps(sorted(seen)))
            print(f"  {i}/{len(titles)} processed | {kept} pages kept")
        time.sleep(DELAY_S)

    LEDGER.write_text(json.dumps(sorted(seen)))
    print(f"done: kept {kept} {GAME} pages in {OUT}")


if __name__ == "__main__":
    main()
