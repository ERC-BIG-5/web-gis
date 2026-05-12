"""Generate 75px thumbnails for a city's images.

Usage: python make_thumbs.py <city-folder>
    where <city-folder> contains an `orig/` subdir.
Thumbnails are written to <city-folder>/thumb/, skipping existing files.
Requires `ffmpeg` on PATH.
"""
import subprocess
import sys
from pathlib import Path

EXTS = {".jpg", ".jpeg", ".png"}


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <city-folder>", file=sys.stderr)
        sys.exit(1)

    city = Path(sys.argv[1])
    src = city / "orig"
    dst = city / "thumb"

    if not src.is_dir():
        print(f"error: {src} not found", file=sys.stderr)
        sys.exit(1)

    dst.mkdir(parents=True, exist_ok=True)

    for f in sorted(src.iterdir()):
        if f.suffix.lower() not in EXTS:
            continue
        out = dst / f.name
        if out.exists():
            continue
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-i", str(f),
                "-vf", "scale=75:75:force_original_aspect_ratio=decrease",
                "-y", str(out),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
