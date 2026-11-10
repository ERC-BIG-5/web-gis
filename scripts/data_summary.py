#!/usr/bin/env python3
"""One-line-per-dataset summary: datasets, posts, reachable images.

    cd server && uv sync --extra cli && uv run ../scripts/data_summary.py

- datasets: files in data/geo-datasets/filtered/ (what the server serves).
- posts: features in each file.
- reachable: the post's image_name exists as a readable file (symlinks are
  followed, so broken symlinks count as unreachable) in
  data/images/<base_media_path>/orig and, separately, .../thumb.
"""

import json
from pathlib import Path

from tqdm import tqdm

DATA = Path(__file__).resolve().parent.parent / "data"
FILTERED = DATA / "geo-datasets" / "filtered"
IMAGES = DATA / "images"


def reachable(folder: Path, names: list[str], desc: str) -> int:
    return sum((folder / n).is_file() for n in tqdm(names, desc=desc, unit="img", leave=False))


def main() -> None:
    cfg_path = DATA / "locations.json"
    config = json.loads(cfg_path.read_text("utf-8")).get("locations", {}) if cfg_path.is_file() else {}

    rows = []
    for path in tqdm(sorted(FILTERED.glob("*.json")), desc="datasets", unit="ds"):
        feats = json.loads(path.read_text("utf-8")).get("features", [])
        names = [n for f in feats if (n := f.get("properties", {}).get("image_name"))]
        base = config.get(path.stem, {}).get("base_media_path", path.stem)
        rows.append((
            path.stem, len(feats), len(names),
            reachable(IMAGES / base / "orig", names, f"{path.stem} orig"),
            reachable(IMAGES / base / "thumb", names, f"{path.stem} thumb"),
        ))

    head = ("dataset", "posts", "w/ image", "orig ok", "thumb ok")
    w = max([len(head[0])] + [len(r[0]) for r in rows])
    print(f"{head[0]:<{w}}  " + "  ".join(f"{h:>8}" for h in head[1:]))
    for r in rows:
        print(f"{r[0]:<{w}}  " + "  ".join(f"{v:>8}" for v in r[1:]))
    tot = [sum(r[i] for r in rows) for i in range(1, 5)]
    print(f"{'TOTAL':<{w}}  " + "  ".join(f"{v:>8}" for v in tot))
    print(f"\n{len(rows)} datasets, {tot[0]} posts, "
          f"{tot[2]}/{tot[1]} images reachable (orig), {tot[3]}/{tot[1]} (thumb)")


if __name__ == "__main__":
    main()
