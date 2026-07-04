# CompanionCube — web

Next.js frontend for the spoiler-aware game guide. Dual Hallownest / Pharloom themes that
cross-fade, a canvas dust background with mouse parallax, progress-driven spoiler gating, and
streaming answers.

## Run

```bash
npm install
npm run dev        # http://localhost:3000
```

## Wiring the real backend

`components/CompanionCube.jsx` ships with a mock `apiQuery` whose request/response shapes match the
Python backend's gated retrieval. To go live, swap it for a fetch and load the progress lists from the
API instead of the inline `DATA`:

- `GET /api/beats?game={hollow_knight|silksong}` → `{ abilities:[{id,title}], areas:[…], bosses:[…] }`
- `POST /api/query` with `{ question, game, mode, tolerance, completed_beats: string[] }`
  → `{ answer: <markdown>, citations: [{ id, title, section, url }] }`

`mode`, `tolerance`, and `completed_beats` map directly to the backend's `Mode`, `SpoilerTolerance`,
and `PlayerState`.

## Assets

Drop the game icons at `public/assets/icon-hk.png` and `public/assets/icon-ss.png` (exported from the
CompanionCube design). The UI degrades gracefully if they are absent.
