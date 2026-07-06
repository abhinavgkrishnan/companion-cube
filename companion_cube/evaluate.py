"""Eval harness for the gated retrieval.

Two things matter here: the guide surfaces the right page when the player is far enough along
(recall@k), and it never surfaces a beat the player hasn't reached (spoiler-leak rate). Both run
against the live Qdrant index, so they exercise the real hybrid retrieval + gate, not a mock.

    python -m companion_cube.evaluate
"""

from .models import PlayerState
from .retrieval import retrieve

K = 6

# With the given progress, the expected page should surface in the top-k.
RECALL = [
    {"q": "how do I beat the Mantis Lords", "game": "hollow_knight",
     "beats": ["forgotten_crossroads", "greenpath", "fungal_wastes"], "expect": "Mantis Lords"},
    {"q": "how to beat the Soul Master", "game": "hollow_knight",
     "beats": ["forgotten_crossroads", "greenpath", "fungal_wastes", "city_of_tears"], "expect": "Soul Master"},
    {"q": "what does the Mothwing Cloak dash do", "game": "hollow_knight",
     "beats": ["greenpath", "mothwing_cloak"], "expect": "Mothwing Cloak"},
    {"q": "where can I find mask shards", "game": "hollow_knight",
     "beats": ["forgotten_crossroads", "greenpath"], "expect": "Mask Shard (Hollow Knight)"},
    {"q": "how do I beat Lace", "game": "silksong",
     "beats": ["moss_grotto", "the_marrow", "deep_docks", "far_fields"], "expect": "Lace"},
]

# With the given (under-)progress, none of the returned chunks may reveal a forbidden beat.
LEAK = [
    {"q": "how does the game end", "game": "hollow_knight", "beats": [],
     "forbid": {"the_radiance", "absolute_radiance", "endings_(hollow_knight)"}},
    {"q": "how to beat the Radiance final boss", "game": "hollow_knight",
     "beats": ["forgotten_crossroads", "greenpath", "fungal_wastes", "city_of_tears"],
     "forbid": {"the_radiance", "absolute_radiance"}},
    {"q": "how do I beat the Soul Master", "game": "hollow_knight", "beats": ["forgotten_crossroads"],
     "forbid": {"soul_master"}},
    {"q": "what is the true ending", "game": "silksong",
     "beats": ["moss_grotto", "the_marrow", "deep_docks"], "forbid": {"lost_lace", "grand_mother_silk"}},
]


def _titles(hits):
    return [h.get("doc_title", "") for h in hits]


def recall_at_k(k=K):
    ok = 0
    for c in RECALL:
        hits = retrieve(c["q"], PlayerState(completed_beats=set(c["beats"])), game=c["game"], k=k)
        found = c["expect"] in _titles(hits)
        ok += found
        print(f"  [{'PASS' if found else 'MISS'}] {c['game']:13} {c['q'][:38]:38} -> {c['expect']!r}")
    return ok / len(RECALL)


def leak_rate(k=K):
    # A real leak is serving a page ABOUT a forbidden beat. A chunk's primary subject is reveals_beats[0]
    # (its own page); a forbidden beat appearing further down is an incidental name-drop in reached-area
    # content, not a leak of that content. (Tighter reveals_beats would remove even the name-drops — a
    # re-tag item.)
    leaks = 0
    for c in LEAK:
        hits = retrieve(c["q"], PlayerState(completed_beats=set(c["beats"])), game=c["game"], k=k)
        served = {h["reveals_beats"][0] for h in hits if h.get("reveals_beats")}
        leaked = c["forbid"] & served
        leaks += bool(leaked)
        tag = f"LEAK {sorted(leaked)}" if leaked else "safe"
        print(f"  [{tag}] {c['game']:13} {c['q'][:38]:38} -> forbid {sorted(c['forbid'])}")
    return leaks / len(LEAK)


def main():
    print(f"recall@{K} (expected page surfaces when reachable):")
    r = recall_at_k()
    print("\nspoiler-leak (an under-progressed player must see none of the forbidden beats):")
    lr = leak_rate()
    print(f"\n=== recall@{K} = {r:.0%}   spoiler-leak rate = {lr:.0%} ===")


if __name__ == "__main__":
    main()
