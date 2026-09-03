"""Paths shared by the server (main.py) and the maintenance CLI (cli.py)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "data"

DATASETS_DIR = DATA_ROOT / "geo-datasets"        # raw GeoJSON per location
FILTERED_DIR = DATASETS_DIR / "filtered"         # what the server actually serves
IMAGES_DIR = DATA_ROOT / "images"                # <base_media_path>/{orig,thumb}/
LOCATIONS_CONFIG_PATH = DATA_ROOT / "locations.json"
WORLD_GEOJSON = DATA_ROOT / "world.geojson"
DB_PATH = DATA_ROOT / "validation.db"
WEB_DIST = ROOT / "web" / "dist"
