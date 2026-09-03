# web-gis

Small FastAPI + Vue/MapLibre app for browsing geo-located points with
attached images and CES (Cultural Ecosystem Services) classifications.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.13+)
- Node.js 20+ is optional. `web/dist/` is not tracked; the launcher
  builds it on first start, using system npm or a Node runtime fetched
  via `uvx` (needs network on first run).

## Data

`data/` is **not tracked** in git. Before starting, place these there
(ask a team member for a copy):

```
data/locations.json      per-city UI config
data/world.geojson       background world layer
data/geo-datasets/       GeoJSON per city
data/images/<city>/      orig/ and thumb/ images
```

## Run

The server serves both the API and the prebuilt frontend on
`http://0.0.0.0:8955` by default (reachable from the LAN; the startup
banner prints the network URL).

Port, bind address and URL prefix are read from `server/.env` — copy
`server/.env.template` and edit, or set them as environment variables:

```bash
cp server/.env.template server/.env   # then edit PORT / HOST / BASE_PATH
# or one-off:
PORT=9000 ./scripts/start.sh
```

Linux / macOS:

```bash
./scripts/start.sh
```

Windows:

```cmd
scripts\start.bat
```

The launcher builds the frontend (`scripts/build.sh`) when `web/dist/`
is missing, and rebuilds on every start once `web/node_modules/` exists
— i.e. on machines where you've run `npm install`.

To set up frontend development:

```bash
cd web
npm install
# from now on, every ./scripts/start.sh will rebuild before serving
```

For hot-reload dev: `npm run dev` in `web/` (proxy/CORS may need
tweaking against the running server).

## Deploy (systemd + nginx)

The files in `deploy/` are used directly from the checkout on the server;
nothing is copied to the repo root.

`deploy/web-gis.service` is a hardened systemd unit (read-only system,
home hidden except the project, writes only to `data/`). `systemctl link`
it from its place in `deploy/`, and put `PORT=...` and `HOST=127.0.0.1`
in `server/.env`. Serve it behind a reverse proxy; the frontend uses
relative URLs, so any path prefix works.

`deploy/nginx_web-gis.conf` + `nginx_web-gis-common.conf` serve the app
under `/web-gis/` with security headers and a per-IP rate limit on the
session endpoints; `include` the first from your `server {}` block.
`deploy/nginx_web-gis-ratelimit.conf` is the one exception: it has to sit
at `http {}` level, so copy it to `/etc/nginx/conf.d/`.

Updating on the server:

```bash
git pull
cd server && uv sync && cd ..
sudo systemctl daemon-reload && sudo systemctl restart web-gis   # if deploy/web-gis.service changed
sudo nginx -t && sudo systemctl reload nginx                     # if deploy/nginx_* changed
```

## Project layout

```
data/
  geo-datasets/        GeoJSON FeatureCollections, one per city
  images/<city>/
    orig/              full-size source images
    thumb/             pre-generated thumbnails (optional)
  locations.json       per-city UI config (filters, popup, evaluator)
  world.geojson        background world layer
server/src/webgis/     FastAPI app (main.py), config paths, maintenance CLI (cli.py)
web/                   Vue 3 + Vite frontend
scripts/start.sh|.bat  launcher
scripts/build.sh       build web/dist (system npm, or Node via uvx)
server/.env.template   PORT / HOST / BASE_PATH defaults — copy to server/.env
```

## Adding a new city

1. Create `data/geo-datasets/<city>.json` — a GeoJSON
   `FeatureCollection` of `Point` features. Each feature's `properties`
   must include at least:
   - `name` or `id`
   - `image_name` — filename inside `data/images/<city>/orig/`
   - `ces` — either a CES short code (e.g. `"AES"`) or a list of snake_case keys
2. Drop the corresponding images into `data/images/<city>/orig/`.
3. Optionally pre-generate thumbnails into `data/images/<city>/thumb/`
   (same filenames). If absent, the server can resize on the fly via
   `/scaled`.
4. Register the city in `data/locations.json` under the `locations`
   object — set `base_media_path`, `popup_fields`, and the
   `classification` / `evaluator` blocks. Use `the_hague` as a richer
   template or `barcelona` as a minimal one. The string `"@ces_values"`
   inlines the shared CES taxonomy defined at the top of the file.
5. Restart the server (the config is read once on startup). The
   dropdown is populated from `data/geo-datasets/*.json`.

## Location config (`data/locations.json`)

The per-city UI configuration — filters, popup fields, evaluator — lives
in `data/locations.json` and is **loaded once at server startup**, so any
edit requires restarting the server to take effect.

Top-level shape:

```jsonc
{
  "ces_values": [ { "key": "...", "short": "...", "name": "..." }, ... ],
  "locations": {
    "<city>": { "base_media_path": "...", "classification": {...}, ... }
  }
}
```

`"@ces_values"` anywhere inside a location block is substituted with the
full `ces_values` array on load — use it wherever you'd otherwise
duplicate the CES taxonomy.

## Thumbnails

Place resized images (longer side = 75px) into `data/images/<city>/thumb/`
with the same filenames as in `orig/`.

Use the helper script (requires `ffmpeg` on PATH):

```bash
python scripts/make_thumbs.py data/images/<city>
```

It mirrors every image from `<city>/orig/` into `<city>/thumb/`, skipping
files that already exist. The underlying command is:

```bash
ffmpeg -i input.jpg -vf "scale=75:75:force_original_aspect_ratio=decrease" output.jpg
```

## Helper scripts

### `scripts/convert_yes_no.py`

Cleans up a dataset where `nature_text` / `nature_images` came in as
string `"yes"` / `"no"` values (e.g. from an LLM that didn't follow the
schema) and converts them to real booleans in-place inside
`features[*].properties.models[<model>][...]`.

```bash
python scripts/convert_yes_no.py data/geo-datasets/<city>.json [--out other.json]
```

Only touches `nature_text` and `nature_images`. The `the_hague` pipeline
depends on these being booleans — a stringified `"no"` would be
**truthy** in Python and silently flip the meaning.

### `scripts/jitter_duplicates.py`

Spreads out clusters of points sitting on the exact same lat/lng so
they don't all stack into a single marker on the map. Jitter is uniform
within a disk of `radius_m` meters (lat-corrected for longitude).

```bash
python scripts/jitter_duplicates.py data/geo-datasets/<city>.json \
  --threshold 10  # only jitter groups with > 10 colocated points
  --radius 8      # disk radius in meters
  --seed 0
  --out other.json   # optional, default overwrites input
```

Only groups with strictly more than `threshold` co-located points get
jittered — small duplicates are left alone.
