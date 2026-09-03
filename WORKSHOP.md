# Workshop Validation Mode — What Changed & How to Run It

The project now has a second mode alongside the original map browser: a guided
validation flow for the workshop (8 case studies, one participant each,
target 100 posts in 1.5 h).

## What was added

**Backend (`server/src/webgis/main.py`)** — all original endpoints untouched, plus:

- `POST /session` — creates or resumes a session for a case study + participant.
  On first login it builds a seeded random queue of 150 posts (100 target × 1.5
  spares to backfill skips). For datasets with LLM nature flags the sample is
  80% nature-positive / 20% negative; otherwise uniform. The seed is derived
  from `case_study + participant name`, so the same person always gets the same
  queue — fully reproducible for your methods section.
- `GET /session/{id}/next` — the next pending post (feature + progress).
- `POST /session/{id}/validate` — saves one validation immediately to SQLite
  (`data/validation.db`), crash-safe. Statuses: `validated`, `not_relevant`
  (nature = "None"), `skipped` (can't judge — doesn't count toward the 100 and
  is backfilled automatically).
- `GET /session/{id}/progress`, `GET /session/{id}/done` (validated posts as
  GeoJSON for the map's done layer).
- `GET /export/{case_study}?format=csv|json` — CSV has one column per CES
  category (`agree` / `disagree` / empty), opens cleanly in Excel.
- `GET /facilitator/summary` — live counts per participant.
- The server now listens on `0.0.0.0:8955` and prints the network URL
  participants should use.

**Frontend (`web/src/`)** — new components, browse mode fully preserved:

- `LoginScreen.vue` — case-study picker + name; resuming after a crash or
  reload is automatic (same name + case study = same session, progress kept).
- `ValidationPanel.vue` — the guided flow: progress bar ("N / 100" + timer),
  large image (click to open a fullscreen lightbox), post text, the two-step
  form (nature elements 1/2/3/4 on the keyboard → CES agree/disagree chips),
  optional comment, "Can't judge" with reason, and **Enter = Save & Next**.
- `FacilitatorView.vue` — open `http://<server>:8955/#facilitator` for live
  progress of all 8 participants + CSV/JSON download buttons (auto-refreshes
  every 15 s). Not linked from the participant UI.
- `App.vue` / `MapView.vue` — validation layout (map left, panel right); the
  map flies to each post; validated posts appear as muted grey dots on a
  toggleable "Show validated" layer; participants see only their own case
  study. The original browse mode is reachable from the login screen
  ("Browse mode (facilitator)").

## One-time setup (your machine)

1. Replace your project folder with the contents of this zip (or copy over
   `server/src/webgis/main.py` and the whole `web/src/` folder — those are the only
   changed/new code files).
2. Rebuild the frontend once (the shipped `web/dist` is still the OLD UI):
   ```
   cd web
   npm install
   npm run build
   ```
   (Needs Node 20+. After this, `scripts\start.bat` auto-rebuilds every launch.)
3. Start: `scripts\start.bat` from the project root. It prints two URLs — use
   the **Network** one for participants.
4. First launch on Windows: allow Python/uvicorn through the firewall when
   prompted (choose Private networks). If no prompt appears and other laptops
   can't connect, add an inbound rule for TCP port 8955.

## Adding your 8 case studies (no code edits needed)

Per case study, exactly as before, plus one new optional key:

1. `data/geo-datasets/<city>.json` — GeoJSON FeatureCollection; each feature
   needs `id` (or `name`), `image_name`, and the LLM output either as a flat
   `ces` list or a `models` block like the_hague.
2. Images in `data/images/<city>/orig/`; thumbnails via
   `python scripts/make_thumbs.py data/images/<city>`.
3. Register the city in `data/locations.json`. **If the dataset uses a
   `models` block, add `"model": "<exact-model-name>"` to the city's config**
   — the server then flattens it automatically (nature flags, CES list) with
   no Python changes. You can also set `"workshop_target": 100` per city to
   override the default target.
4. Restart the server (config is read once at startup).

## Workshop-day checklist

- Delete `data/validation.db` before the real session if you ran tests with
  real participant names (or have participants use their exact name — same
  name resumes the old session, including test clicks).
- The session timer starts at a participant's FIRST login — have them log in
  when the 1.5 h actually starts, not during the 30-min briefing.
- All laptops on the same network as the server; test in the actual room —
  some university/guest Wi-Fi blocks device-to-device traffic ("AP isolation").
- Keep `http://<server>:8955/#facilitator` open on your machine to watch
  progress and download exports.
- **`data/validation.db` is the results.** Copy it somewhere safe right after
  the session (and optionally every 30 min during — it's a single file).

## Quick smoke test (5 min, do this now)

1. Start the server, open the Local URL → login screen appears.
2. Pick `the_hague`, name `test`, Start → map flies to a post, panel shows the
   image, press `3` (In both), click ✓/✗ on each CES chip (if any), Enter.
3. Progress goes 1/100; a grey dot appears on the map; toggle "Show validated".
4. Reload the page → you're back in the same session at the same count.
5. Open `/#facilitator` in a second tab → the `test` row is there; download the
   CSV and check the `ces_*` columns.
6. Delete `data/validation.db`, restart — clean slate.
