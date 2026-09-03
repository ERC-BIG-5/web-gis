"""Maintenance CLI for the web-gis data folder.

    uv sync --extra cli          # once
    typer cli.py run list-locations
"""

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

# `typer cli.py run ...` imports this file without putting its folder on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATASETS_DIR, FILTERED_DIR, IMAGES_DIR, LOCATIONS_CONFIG_PATH  # noqa: E402

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
    """Show every location known from datasets, config or image folders."""
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


if __name__ == "__main__":
    app()
