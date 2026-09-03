"""Paths shared by the server (main.py) and the maintenance CLI (cli.py)."""

from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[2]   # server/ (holds pyproject.toml, .env)
ROOT = SERVER_DIR.parent
DATA_ROOT = ROOT / "data"

DATASETS_DIR = DATA_ROOT / "geo-datasets"        # raw GeoJSON per location
FILTERED_DIR = DATASETS_DIR / "filtered"         # what the server actually serves
IMAGES_DIR = DATA_ROOT / "images"                # <base_media_path>/{orig,thumb}/
LOCATIONS_CONFIG_PATH = DATA_ROOT / "locations.json"
WORLD_GEOJSON = DATA_ROOT / "world.geojson"
DB_PATH = DATA_ROOT / "validation.db"
WEB_DIST = ROOT / "web" / "dist"
