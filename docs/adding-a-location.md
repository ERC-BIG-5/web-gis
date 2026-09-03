# Adding a location

A location needs three things, all named after the same `<city>`:

| File | Format | Created by |
|---|---|---|
| `data/geo-datasets/<city>.json` | GeoJSON FeatureCollection of Point features | LLM pipeline (external) |
| `data/geo-datasets/filtered/<city>.json` | same, the copy the server serves | external (no script in repo) |
| `data/images/<city>/orig/*.jpg` | full-size images, filename = `image_name` | external |
| `data/images/<city>/thumb/*.jpg` | same filenames, longer side 75 px | `python scripts/make_thumbs.py data/images/<city>` |
| `data/locations.json` → `locations.<city>` | JSON config block | by hand |

## Dataset

Each feature's `properties` needs `id` (or `name`), `image_name`, and the
model output under `models.<model name>` with `nature_text`,
`nature_images` (booleans), `nature_terms_text`, `nature_terms_images` and
`ces` (map of CES key → bool). See `data/geo-datasets/milan.json`.

Fix-up scripts, both edit in place:

- `scripts/convert_yes_no.py <file>` — turns `"yes"`/`"no"` into booleans.
- `scripts/jitter_duplicates.py <file>` — spreads points on identical coordinates.

## Config

Copy the `the_hague` block in `data/locations.json` and set:

- `base_media_path`: `<city>`
- `model`: the exact key used under `models` in the dataset
- `workshop_target` (optional): posts per participant, default 100

`classification`, `popup_fields` and `evaluator` can stay as they are.

Restart the server; the config is read once at startup.

## Status

```bash
cd server
uv sync --extra cli            # once
typer cli.py run list-locations
```

Shows, per location, feature counts, whether a config block exists, and
how many images/thumbnails are on disk or missing.
