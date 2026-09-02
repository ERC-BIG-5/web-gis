import csv
import hashlib
import io
import json
import math
import random
import re
import sqlite3
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "geo-datasets" / "filtered"
IMAGES_DIR = ROOT / "data" / "images"
WEB_DIST = ROOT / "web" / "dist"
LOCATIONS_CONFIG_PATH = ROOT / "data" / "locations.json"

# User-supplied path segments (location names, image base dirs, file names) must
# be plain names: no separators, no leading dot, no "..". Paths built from them
# are additionally checked to resolve inside their root directory.
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _safe_segment(value: str, what: str) -> str:
    if not value or ".." in value or not _SAFE_SEGMENT.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"invalid {what}")
    return value


def _under(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise HTTPException(status_code=400, detail="invalid path")
    return resolved


class Settings(BaseSettings):
    """Runtime config from server/.env (see server/.env.template) or the
    environment. Env vars win over the file."""

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parent / ".env")

    host: str = "0.0.0.0"
    port: int = 8955
    # Public URL prefix when served behind a reverse proxy that strips it,
    # e.g. "/web-gis". Only affects /docs and OpenAPI URLs; routes stay at root.
    base_path: str = ""


settings = Settings()


def _resolve_refs(obj, refs):
    if isinstance(obj, str) and obj.startswith("@"):
        key = obj[1:]
        if key not in refs:
            raise ValueError(f"unknown reference @{key} in locations.json")
        return refs[key]
    if isinstance(obj, dict):
        return {k: _resolve_refs(v, refs) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(v, refs) for v in obj]
    return obj


with LOCATIONS_CONFIG_PATH.open(encoding="utf-8") as _f:
    _cfg = json.load(_f)
CES_VALUES = _cfg["ces_values"]
LOCATION_CONFIG = _resolve_refs(_cfg["locations"], {"ces_values": CES_VALUES})

SHORT_TO_SNAKE = {v["short"]: v["key"] for v in CES_VALUES}
SNAKE_TO_SHORT = {v["key"]: v["short"] for v in CES_VALUES}


def _ces_short(ces_list):
    return " ".join(SNAKE_TO_SHORT.get(k, k) for k in ces_list)

THE_HAGUE_MODEL = "Mistral-Small-3.2-24B-Instruct-2506"


def _make_model_transform(model_name):
    """Flatten props for datasets that store per-model LLM output under
    properties.models[<model_name>] (the_hague style)."""

    def _flatten(props):
        model = props.get("models", {}).get(model_name, {})
        out = {k: v for k, v in props.items() if k != "models"}
        nat_text = bool(model.get("nature_text"))
        nat_img = bool(model.get("nature_images"))
        out["nature_text"] = nat_text
        out["nature_images"] = nat_img
        nature = []
        if nat_text:
            nature.append("text")
        if nat_img:
            nature.append("images")
        out["nature"] = nature
        out["nature_terms_text"] = model.get("nature_terms_text", [])
        out["nature_terms_images"] = model.get("nature_terms_images", [])
        ces_dict = model.get("ces", {})
        out["ces"] = [k for k, v in ces_dict.items() if v]
        out["ces_short"] = _ces_short(out["ces"])
        return out

    return _flatten


_flatten_the_hague = _make_model_transform(THE_HAGUE_MODEL)


def _flatten_barcelona(props):
    out = dict(props)
    ces = props.get("ces")
    if isinstance(ces, str):
        out["ces"] = [SHORT_TO_SNAKE.get(ces, ces)]
    out["ces_short"] = _ces_short(out.get("ces", []))
    return out


TRANSFORMS = {
    "the_hague": _flatten_the_hague,
    "barcelona": _flatten_barcelona,
}


def _transform_for(location):
    """Explicit transform, or a generic one when locations.json declares a
    "model" key for the case study, so new case studies need no code edits."""
    t = TRANSFORMS.get(location)
    if t:
        return t
    model = LOCATION_CONFIG.get(location, {}).get("model")
    if model:
        return _make_model_transform(model)
    return None

# No interactive API docs: the app has no authentication, so do not advertise routes.
app = FastAPI(root_path=settings.base_path, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.get("/geo-dataset")
def geo_dataset(location: str):
    _safe_segment(location, "location")
    path = _under(DATA_DIR, DATA_DIR / f"{location}.json")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"unknown location: {location}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    transform = _transform_for(location)
    if transform:
        for feat in data["features"]:
            feat["properties"] = transform(feat["properties"])
    config = LOCATION_CONFIG.get(location, {})
    for key in ("classification", "base_media_path", "popup_fields", "evaluator"):
        if key in config:
            data[key] = config[key]
    return data


@app.get("/locations")
def locations():
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


@app.get("/evaluate")
def evaluate(id: str):
    print(f"[evaluate] id={id}")
    return {"id": id, "status": "logged"}


@app.post("/evaluate")
async def evaluate_post(payload: dict):
    print(f"[evaluate] POST {payload}")
    return {"status": "logged", "received": payload}


@app.get("/world")
def world():
    path = ROOT / "data" / "world.geojson"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@app.get("/scaled")
def scaled(base: str, name: str, max_side: int = 400):
    _safe_segment(base, "base")
    _safe_segment(name, "name")
    max_side = max(16, min(max_side, 2000))
    path = _under(IMAGES_DIR, IMAGES_DIR / base / "orig" / name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"missing image: {path.name}")
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
    return Response(buf.getvalue(), media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Workshop validation mode
# ---------------------------------------------------------------------------

DB_PATH = ROOT / "data" / "validation.db"
DEFAULT_TARGET = 100        # posts each participant should validate
QUEUE_FACTOR = 1.5          # spare posts so skips can be backfilled
# queue composition (must sum to 1.0). Pools shrink gracefully if a stratum
# has too few posts; the shortfall is topped up from the remaining posts.
SHARE_CES = 0.6             # posts with >=1 CES category assigned by the LLM
SHARE_POS_NO_CES = 0.2      # nature-positive posts without any CES
SHARE_NEGATIVE = 0.2        # nature-negative posts
POSITIVE_SHARE = 0.8        # fallback split for datasets without CES lists


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db():
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_study TEXT NOT NULL,
                participant TEXT NOT NULL,
                seed INTEGER NOT NULL,
                target INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (case_study, participant)
            );
            CREATE TABLE IF NOT EXISTS queue (
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                position INTEGER NOT NULL,
                feature_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY (session_id, position)
            );
            CREATE TABLE IF NOT EXISTS validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                feature_id TEXT NOT NULL,
                nature_elements TEXT,
                ces_judgments TEXT,
                comment TEXT,
                skipped_reason TEXT,
                elapsed_ms INTEGER,
                created_at TEXT NOT NULL
            );
            """
        )


_init_db()


def _migrate_db():
    with _db() as conn:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(validations)")]
        if "location_incorrect" not in cols:
            conn.execute(
                "ALTER TABLE validations ADD COLUMN location_incorrect INTEGER DEFAULT 0"
            )


_migrate_db()

_dataset_cache: dict = {}


def _dataset(location: str):
    """Load, transform and index a case study's features (cached)."""
    if location in _dataset_cache:
        return _dataset_cache[location]
    _safe_segment(location, "location")
    path = _under(DATA_DIR, DATA_DIR / f"{location}.json")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"unknown location: {location}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    transform = _transform_for(location)
    by_id, order = {}, []
    for i, feat in enumerate(data["features"]):
        props = feat["properties"]
        if transform:
            props = transform(props)
        fid = str(props.get("id") or props.get("name") or i)
        by_id[fid] = {
            "type": "Feature",
            "geometry": feat["geometry"],
            "properties": props,
        }
        order.append(fid)
    base = LOCATION_CONFIG.get(location, {}).get("base_media_path", location)
    entry = {"by_id": by_id, "order": order, "base_media_path": base}
    _dataset_cache[location] = entry
    return entry


def _seed_for(case_study: str, participant: str) -> int:
    h = hashlib.sha256(f"{case_study}:{participant}".encode()).hexdigest()
    return int(h[:12], 16)


def _build_queue(location: str, seed: int, target: int) -> list[str]:
    ds = _dataset(location)
    ids = ds["order"]
    qlen = min(len(ids), math.ceil(target * QUEUE_FACTOR))
    rng = random.Random(seed)

    def props(fid):
        return ds["by_id"][fid]["properties"]

    def is_positive(fid):
        p = props(fid)
        return bool(p.get("nature_text")) or bool(p.get("nature_images"))

    def has_ces(fid):
        return bool(props(fid).get("ces"))

    has_flags = "nature_text" in props(ids[0]) if ids else False
    if has_flags:
        ces_pool = [f for f in ids if has_ces(f)]
        pos_pool = [f for f in ids if is_positive(f) and not has_ces(f)]
        neg_pool = [f for f in ids if not is_positive(f) and not has_ces(f)]
        if ces_pool:
            # stratified: CES-bearing / nature-positive-no-CES / negative,
            # topping up from the other pools when one is too small
            want = [
                (ces_pool, round(qlen * SHARE_CES)),
                (pos_pool, round(qlen * SHARE_POS_NO_CES)),
                (neg_pool, round(qlen * SHARE_NEGATIVE)),
            ]
            sample, remaining = [], []
            for pool, n in want:
                take = min(len(pool), n)
                picked = rng.sample(pool, take)
                sample.extend(picked)
                remaining.extend(f for f in pool if f not in set(picked))
            shortfall = qlen - len(sample)
            if shortfall > 0 and remaining:
                sample.extend(rng.sample(remaining, min(shortfall, len(remaining))))
            rng.shuffle(sample)
            return sample
        pos = [f for f in ids if is_positive(f)]
        neg = [f for f in ids if not is_positive(f)]
        if pos and neg:
            n_pos = min(len(pos), round(qlen * POSITIVE_SHARE))
            n_neg = min(len(neg), qlen - n_pos)
            n_pos = min(len(pos), qlen - n_neg)
            sample = rng.sample(pos, n_pos) + rng.sample(neg, n_neg)
            rng.shuffle(sample)
            return sample
    return rng.sample(ids, qlen)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _progress(conn, session_id: int) -> dict:
    ses = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if ses is None:
        raise HTTPException(status_code=404, detail="unknown session")
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM queue WHERE session_id=? GROUP BY status",
        (session_id,),
    ).fetchall()
    counts = {r["status"]: r["n"] for r in rows}
    validated = counts.get("validated", 0) + counts.get("not_relevant", 0)
    created = datetime.fromisoformat(ses["created_at"])
    elapsed_s = int((datetime.now(timezone.utc) - created).total_seconds())
    return {
        "validated": validated,
        "skipped": counts.get("skipped", 0),
        "pending": counts.get("pending", 0),
        "target": ses["target"],
        "elapsed_s": elapsed_s,
    }


@app.post("/session")
def create_session(payload: dict):
    case_study = (payload.get("case_study") or "").strip()
    participant = (payload.get("participant") or "").strip()
    if not case_study or not participant:
        raise HTTPException(status_code=400, detail="case_study and participant required")
    _dataset(case_study)  # validates the case study exists
    target = int(
        LOCATION_CONFIG.get(case_study, {}).get("workshop_target", DEFAULT_TARGET)
    )
    with _db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE case_study=? AND participant=?",
            (case_study, participant),
        ).fetchone()
        if row is None:
            seed = _seed_for(case_study, participant)
            cur = conn.execute(
                "INSERT INTO sessions (case_study, participant, seed, target, created_at)"
                " VALUES (?,?,?,?,?)",
                (case_study, participant, seed, target, _now()),
            )
            session_id = cur.lastrowid
            queue = _build_queue(case_study, seed, target)
            conn.executemany(
                "INSERT INTO queue (session_id, position, feature_id) VALUES (?,?,?)",
                [(session_id, i, fid) for i, fid in enumerate(queue)],
            )
        else:
            session_id = row["id"]
        prog = _progress(conn, session_id)
    return {
        "session_id": session_id,
        "case_study": case_study,
        "participant": participant,
        "target": prog["target"],
        "progress": prog,
        "ces_values": CES_VALUES,
    }


@app.get("/session/{session_id}/next")
def session_next(session_id: int):
    with _db() as conn:
        prog = _progress(conn, session_id)
        if prog["validated"] >= prog["target"]:
            return {"done": True, "progress": prog}
        ses = conn.execute(
            "SELECT case_study FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        ds = _dataset(ses["case_study"])
        while True:
            row = conn.execute(
                "SELECT position, feature_id FROM queue"
                " WHERE session_id=? AND status='pending' ORDER BY position LIMIT 1",
                (session_id,),
            ).fetchone()
            if row is None:
                return {"done": True, "progress": prog}
            feature = ds["by_id"].get(row["feature_id"])
            if feature is not None:
                break
            # The queue was built against an older version of the dataset.
            # Drop the stale entry instead of failing the whole session.
            print(
                f"[session {session_id}] feature {row['feature_id']} missing"
                " from dataset, marking queue entry 'missing'"
            )
            conn.execute(
                "UPDATE queue SET status='missing' WHERE session_id=? AND position=?",
                (session_id, row["position"]),
            )
        prog = _progress(conn, session_id)
    return {
        "done": False,
        "position": row["position"],
        "feature_id": row["feature_id"],
        "feature": feature,
        "base_media_path": ds["base_media_path"],
        "progress": prog,
    }


@app.post("/session/{session_id}/validate")
def session_validate(session_id: int, payload: dict):
    feature_id = str(payload.get("feature_id") or "")
    if not feature_id:
        raise HTTPException(status_code=400, detail="feature_id required")
    nature = payload.get("nature_elements")  # image|text|both|none|None
    skipped_reason = payload.get("skipped_reason")
    if skipped_reason:
        status = "skipped"
    elif nature == "none":
        status = "not_relevant"
    else:
        status = "validated"
    judgments = payload.get("ces_judgments") or {}
    with _db() as conn:
        upd = conn.execute(
            "UPDATE queue SET status=? WHERE session_id=? AND feature_id=?"
            " AND status='pending'",
            (status, session_id, feature_id),
        )
        if upd.rowcount == 0:
            raise HTTPException(
                status_code=409, detail="post not pending (already validated?)"
            )
        conn.execute(
            "INSERT INTO validations (session_id, feature_id, nature_elements,"
            " ces_judgments, comment, skipped_reason, elapsed_ms,"
            " location_incorrect, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                session_id,
                feature_id,
                nature,
                json.dumps(judgments),
                payload.get("comment") or None,
                skipped_reason or None,
                payload.get("elapsed_ms"),
                1 if payload.get("location_incorrect") else 0,
                _now(),
            ),
        )
        prog = _progress(conn, session_id)
    return {"status": status, "progress": prog}


@app.get("/session/{session_id}/progress")
def session_progress(session_id: int):
    with _db() as conn:
        return _progress(conn, session_id)


@app.get("/session/{session_id}/done")
def session_done(session_id: int):
    with _db() as conn:
        ses = conn.execute(
            "SELECT case_study FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if ses is None:
            raise HTTPException(status_code=404, detail="unknown session")
        rows = conn.execute(
            "SELECT feature_id, status FROM queue WHERE session_id=?"
            " AND status IN ('validated','not_relevant')",
            (session_id,),
        ).fetchall()
    ds = _dataset(ses["case_study"])
    feats = []
    for r in rows:
        f = ds["by_id"].get(r["feature_id"])
        if not f:
            continue
        p = f["properties"]
        feats.append(
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "id": r["feature_id"],
                    "status": r["status"],
                    "ces_short": p.get("ces_short", ""),
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


@app.get("/export/{case_study}")
def export(case_study: str, format: str = "csv"):
    _safe_segment(case_study, "case_study")
    with _db() as conn:
        rows = conn.execute(
            "SELECT v.*, s.participant, s.case_study FROM validations v"
            " JOIN sessions s ON s.id = v.session_id"
            " WHERE s.case_study=? ORDER BY v.created_at",
            (case_study,),
        ).fetchall()
    records = []
    for r in rows:
        judgments = json.loads(r["ces_judgments"] or "{}")
        records.append(
            {
                "case_study": r["case_study"],
                "participant": r["participant"],
                "session_id": r["session_id"],
                "feature_id": r["feature_id"],
                "nature_elements": r["nature_elements"],
                "location_incorrect": bool(r["location_incorrect"]),
                "ces_judgments": judgments,
                "comment": r["comment"],
                "skipped_reason": r["skipped_reason"],
                "elapsed_ms": r["elapsed_ms"],
                "created_at": r["created_at"],
            }
        )
    if format == "json":
        return Response(
            json.dumps(records, indent=1),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{case_study}_validations.json"'
            },
        )
    buf = io.StringIO()
    ces_cols = [v["key"] for v in CES_VALUES]
    writer = csv.writer(buf)
    writer.writerow(
        ["case_study", "participant", "session_id", "feature_id",
         "nature_elements", "location_incorrect"]
        + [f"ces_{k}" for k in ces_cols]
        + ["comment", "skipped_reason", "elapsed_ms", "created_at"]
    )
    for rec in records:
        j = rec["ces_judgments"]
        writer.writerow(
            [
                rec["case_study"],
                rec["participant"],
                rec["session_id"],
                rec["feature_id"],
                rec["nature_elements"] or "",
                "yes" if rec["location_incorrect"] else "",
            ]
            + [
                "agree"
                if j.get(k) is True
                else "disagree"
                if j.get(k) is False
                else "added"
                if j.get(k) == "added"
                else ""
                for k in ces_cols
            ]
            + [
                rec["comment"] or "",
                rec["skipped_reason"] or "",
                rec["elapsed_ms"] if rec["elapsed_ms"] is not None else "",
                rec["created_at"],
            ]
        )
    return Response(
        "\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{case_study}_validations.csv"'
        },
    )


@app.get("/facilitator/summary")
def facilitator_summary():
    with _db() as conn:
        sessions = conn.execute("SELECT * FROM sessions ORDER BY case_study").fetchall()
        out = []
        for s in sessions:
            prog = _progress(conn, s["id"])
            last = conn.execute(
                "SELECT MAX(created_at) AS t FROM validations WHERE session_id=?",
                (s["id"],),
            ).fetchone()
            out.append(
                {
                    "session_id": s["id"],
                    "case_study": s["case_study"],
                    "participant": s["participant"],
                    "validated": prog["validated"],
                    "skipped": prog["skipped"],
                    "target": prog["target"],
                    "last_activity": last["t"],
                    "created_at": s["created_at"],
                }
            )
    return out


if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")


if __name__ == "__main__":
    import socket
    import uvicorn

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except OSError:
        lan_ip = "127.0.0.1"
    port = settings.port
    print(f"\n  Local:   http://127.0.0.1:{port}")
    if settings.host == "0.0.0.0":
        print(f"  Network: http://{lan_ip}:{port}  <-use this")
    print()
    uvicorn.run(app, host=settings.host, port=port)
