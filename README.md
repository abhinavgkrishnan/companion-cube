# companion-cube

A game-guide assistant that answers questions **without spoiling what's ahead**. You tell it where you
are in the game and how much help you want; it retrieves only guide content you've already earned the
right to see, then answers in one of two modes.

Most guide chatbots retrieve the most *relevant* passage. For a game guide that's a bug: the most
relevant passage for "how do I beat this boss?" often reveals a twist three areas ahead. companion-cube
treats player progress as a permission set and gates retrieval on it — so the answer can never leak
content from further than you've reached.

## Ideas it's built on

- **Progress as a set, not a number.** Open-world games have no single "chapter you're on." Progress is
  the set of story beats you've completed and abilities you've unlocked. Spoiler-gating is then a
  set-membership check, which generalizes to non-linear games.
- **Gating is access control.** A chunk is retrievable only if it discloses nothing the player hasn't
  reached. This is the same shape as tenant-scoped retrieval in a multi-user knowledge base.
- **Two modes over the same context.** *Hold my hand* gives the full walkthrough; *gently nudge* gives
  a hint that points the way without solving it — same retrieved chunks, different generation contract.
- **A spoiler-tolerance knob** layered on top, for players who'll accept a light peek ahead.

## Status

Working end-to-end on a small hand-tagged Hollow Knight set, no external services required:

- progress-gated retrieval (the spoiler filter) with unit tests
- lexical scoring, mode-conditioned + grounded prompt assembly, citations
- a runnable demo comparing an early-game vs late-game player

Retrieval quality is deliberately basic at this stage — the point of this cut was to prove the gate and
the two-mode flow before layering real retrieval on top.

## Run

```bash
pip install -r requirements.txt   # only pytest is needed for the current cut
python -m companion_cube.cli      # demo
pytest                            # spoiler-gate tests
```

Generation runs in dry-run mode (prints the grounded prompt) unless `anthropic` is installed and
`ANTHROPIC_API_KEY` is set, in which case it answers with Claude.

## Architecture

```
ingest/   scrape -> clean -> chunk -> tag (region, reveals_beats, spoiler_level) -> embed -> upsert
api/      query {question, player_state, mode, spoiler_tolerance}
  retrieval   hybrid (dense + BM25) + metadata gate + rerank
  generate    mode-conditioned, grounded, cited
eval/     golden set + recall@k + LLM-judge (did nudge mode leak a spoiler?)
web/      chat + ability/area checklist (player_state) + mode / tolerance controls
```

## Roadmap

- Real retrieval: dense embeddings + BM25 hybrid, cross-encoder rerank, Qdrant with payload-filtered
  ANN so the gate runs inside the query
- LLM-assisted spoiler tagging at ingest instead of hand tagging
- Eval harness: spoiler-leak rate in nudge mode, recall@k on gated retrieval
- Next.js UI with the progress checklist
- Generalize the tagged set from Hollow Knight to an open-world title (Elden Ring)

## Data

Guide content is derived from community wiki text under its original license (CC BY-SA); sources are
tracked per chunk and attributed. Only a small hand-authored sample is included here.
