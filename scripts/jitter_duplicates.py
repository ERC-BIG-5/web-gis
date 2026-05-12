#!/usr/bin/env python3
"""
Randomly jitter points that share exact coordinates with more than `threshold`
other points. Jitter is uniform within a disk of `radius_m` meters.

Usage:
    python scripts/jitter_duplicates.py <dataset.json> [--threshold 10] [--radius 8]
"""
import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

EARTH_M_PER_DEG_LAT = 111_320.0


def jitter(lng, lat, radius_m):
    theta = random.uniform(0, 2 * math.pi)
    d = math.sqrt(random.random()) * radius_m
    dy = (d * math.cos(theta)) / EARTH_M_PER_DEG_LAT
    dx = (d * math.sin(theta)) / (EARTH_M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return [lng + dx, lat + dy]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--threshold", type=int, default=10,
                    help="jitter clusters with strictly more than this many points (default 10)")
    ap.add_argument("--radius", type=float, default=8.0,
                    help="jitter radius in meters (default 8)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    args = ap.parse_args()

    random.seed(args.seed)
    src = Path(args.dataset)
    dst = Path(args.out) if args.out else src

    data = json.loads(src.read_text())
    feats = data["features"]

    groups = defaultdict(list)
    for f in feats:
        c = f["geometry"]["coordinates"]
        groups[(c[0], c[1])].append(f)

    affected_groups = 0
    affected_points = 0
    for (lng, lat), members in groups.items():
        if len(members) <= args.threshold:
            continue
        affected_groups += 1
        for f in members:
            f["geometry"]["coordinates"] = jitter(lng, lat, args.radius)
            affected_points += 1

    dst.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"groups: {len(groups)} | jittered groups: {affected_groups} | jittered points: {affected_points}")
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
