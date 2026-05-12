#!/usr/bin/env python3
"""Convert "yes"/"no" string values to booleans inside features[*].properties.models.

Targets fields named nature_text and nature_images per model.

Usage:
    python scripts/convert_yes_no.py <dataset.json>
"""
import argparse
import json
from pathlib import Path

YES_NO_FIELDS = ("nature_text", "nature_images")


def convert(value):
    if isinstance(value, str):
        if value.lower() in ("yes", "y", "true"):
            return True
        if value.lower() in ("no", "n", "false"):
            return False
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--out")
    args = ap.parse_args()

    src = Path(args.dataset)
    dst = Path(args.out) if args.out else src
    data = json.loads(src.read_text())

    changed = 0
    for feat in data["features"]:
        models = feat.get("properties", {}).get("models", {})
        for model_data in models.values():
            for key in YES_NO_FIELDS:
                if key in model_data:
                    new = convert(model_data[key])
                    if new is not model_data[key]:
                        model_data[key] = new
                        changed += 1

    dst.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"converted {changed} fields | wrote {dst}")


if __name__ == "__main__":
    main()
