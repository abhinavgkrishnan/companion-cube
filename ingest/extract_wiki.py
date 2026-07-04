"""Pull raw wikitext + metadata from the Hollow Knight wiki via the MediaWiki API.

Source: hollowknight.wiki (MediaWiki 1.41, CC BY-SA 3.0). API lives at /mw/api.php, not /w/.
Wikitext keeps everything downstream tagging needs: [[Category:...]] tags, {{Infobox}} templates,
section headings, and internal links. One JSON per page in data/raw/, source URL kept for attribution.

Run:  python ingest/extract_wiki.py
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://hollowknight.wiki/mw/api.php"
PAGE_BASE = "https://hollowknight.wiki/w/"
UA = "companion-cube/0.1 (portfolio RAG project; github.com/abhinavgkrishnan)"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
DELAY_S = 0.7  # polite gap between requests

# curated HK subset to validate the pipeline before a full run
SUBSET = [
    # abilities
    "Mothwing Cloak", "Mantis Claw", "Crystal Heart", "Monarch Wings",
    "Shade Cloak", "Isma's Tear", "Dream Nail",
    # bosses
    "False Knight", "Broken Vessel", "The Hollow Knight", "The Radiance",
    # areas
    "Greenpath", "City of Tears", "The Abyss (Hollow Knight)", "Crystal Peak", "Ancient Basin",
    # endgame / spoiler-heavy
    "Endings (Hollow Knight)",
]


def api(**params):
    params["format"] = "json"
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(title):
    # redirects=1 so an ability/area that redirects lands on the real page
    data = api(action="parse", page=title, redirects=1,
               prop="wikitext|categories|sections")
    if "error" in data:
        return {"title": title, "error": data["error"].get("code", "unknown")}
    p = data["parse"]
    resolved = p["title"]
    return {
        "title": resolved,
        "url": PAGE_BASE + urllib.parse.quote(resolved.replace(" ", "_")),
        "pageid": p.get("pageid"),
        "categories": [c["*"] for c in p.get("categories", [])],
        "sections": [{"line": s["line"], "level": s["level"]} for s in p.get("sections", [])],
        "wikitext": p["wikitext"]["*"],
    }


def slug(title):
    return title.replace(" ", "_").replace("/", "-").replace("'", "")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for title in SUBSET:
        path = OUT / f"{slug(title)}.json"
        if path.exists():
            print(f"cached  {title}")
            continue
        try:
            rec = fetch(title)
        except Exception as e:
            print(f"FAIL    {title}: {e}")
            continue
        if "error" in rec:
            print(f"ERROR   {title}: {rec['error']}")
            continue
        path.write_text(json.dumps(rec, indent=2, ensure_ascii=False))
        print(f"saved   {rec['title']:22} "
              f"{len(rec['wikitext']):>6} chars | "
              f"{len(rec['categories'])} cats | {len(rec['sections'])} sections")
        time.sleep(DELAY_S)


if __name__ == "__main__":
    main()
