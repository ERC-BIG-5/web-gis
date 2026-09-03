"""Maintenance CLI for the web-gis data folder.

    uv sync --extra cli          # once
    uv run webgis list-locations
"""

import json
import sqlite3
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from webgis.config import DATASETS_DIR, DB_PATH, FILTERED_DIR, IMAGES_DIR, LOCATIONS_CONFIG_PATH

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.callback()
def _main():
    """Maintenance commands for the web-gis data folder."""


def _load_config() -> dict:
    if not LOCATIONS_CONFIG_PATH.is_file():
        return {}
    with LOCATIONS_CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f).get("locations", {})


def _features(path: Path) -> list[dict] | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f).get("features", [])


def _image_status(features: list[dict] | None, base: str) -> tuple[str, str]:
    """(orig, thumb) cells: count on disk plus how many features lack an image."""
    orig_dir = IMAGES_DIR / base / "orig"
    thumb_dir = IMAGES_DIR / base / "thumb"
    cells = []
    for d in (orig_dir, thumb_dir):
        if not d.is_dir():
            cells.append("[red]-[/red]")
            continue
        on_disk = {p.name for p in d.iterdir() if p.is_file()}
        cell = str(len(on_disk))
        if features:
            wanted = {f.get("properties", {}).get("image_name") for f in features}
            wanted.discard(None)
            missing = len(wanted - on_disk)
            if missing:
                cell += f" [red]({missing} missing)[/red]"
        cells.append(cell)
    return cells[0], cells[1]


@app.command("list-locations")
def list_locations():
    """Show every location known from datasets, config or image folders.

    Columns:

    - location: name shared by dataset file, config block and image folder.

    - raw: feature count in data/geo-datasets/<location>.json.

    - filtered (served): feature count in data/geo-datasets/filtered/<location>.json, the file the server actually serves.

    - config: whether data/locations.json has a block for this location.

    - model: the "model" key of that block, used to flatten models.<name> in the dataset.

    - orig images: files in data/images/<base_media_path>/orig, plus how many features reference an image that is not there.

    - thumbs: same for data/images/<base_media_path>/thumb (map markers).

    "-" means the file or folder does not exist.
    """
    config = _load_config()
    names = set(config)
    for d in (DATASETS_DIR, FILTERED_DIR):
        names.update(p.stem for p in d.glob("*.json"))
    names.update(p.name for p in IMAGES_DIR.iterdir() if p.is_dir())

    table = Table(title="Locations", show_lines=False)
    table.add_column("location", style="bold")
    table.add_column("raw", justify="right")
    table.add_column("filtered (served)", justify="right")
    table.add_column("config")
    table.add_column("model")
    table.add_column("orig images", justify="right")
    table.add_column("thumbs", justify="right")

    for name in sorted(names):
        raw = _features(DATASETS_DIR / f"{name}.json")
        served = _features(FILTERED_DIR / f"{name}.json")
        cfg = config.get(name)
        base = (cfg or {}).get("base_media_path", name)
        orig_cell, thumb_cell = _image_status(served or raw, base)
        table.add_row(
            name,
            str(len(raw)) if raw is not None else "[red]-[/red]",
            str(len(served)) if served is not None else "[red]-[/red]",
            "[green]yes[/green]" if cfg else "[red]no[/red]",
            (cfg or {}).get("model", "-"),
            orig_cell,
            thumb_cell,
        )
    console.print(table)


@app.command()
def annotations():
    """Count workshop annotations (rows in data/validation.db) per location.

    Columns:

    - location: the case_study participants logged in with.

    - participants: sessions, i.e. distinct participant names for that location.

    - annotations: all validation rows, including skipped ones.

    - skipped: rows where the participant gave a skip reason instead of a judgment.

    - posts: distinct features that received at least one annotation.
    """
    if not DB_PATH.is_file():
        console.print(f"[red]no database at {DB_PATH}[/red]")
        raise typer.Exit(1)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT s.case_study,
               COUNT(DISTINCT s.id),
               COUNT(v.id),
               SUM(v.skipped_reason IS NOT NULL AND v.skipped_reason != ''),
               COUNT(DISTINCT v.feature_id)
        FROM sessions s LEFT JOIN validations v ON v.session_id = s.id
        GROUP BY s.case_study ORDER BY s.case_study
        """
    ).fetchall()
    conn.close()

    table = Table(title="Annotations")
    table.add_column("location", style="bold")
    for col in ("participants", "annotations", "skipped", "posts"):
        table.add_column(col, justify="right")
    for case_study, sessions, total, skipped, posts in rows:
        table.add_row(case_study, str(sessions), str(total), str(skipped or 0), str(posts))
    console.print(table)


if __name__ == "__main__":
    app()
