import json
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "geo-datasets"
IMAGES_DIR = ROOT / "data" / "images"
WEB_DIST = ROOT / "web" / "dist"
LOCATIONS_CONFIG_PATH = ROOT / "data" / "locations.json"


class Settings(BaseSettings):
    """Runtime config from server/.env (see server/.env.template) or the
    environment. Env vars win over the file."""

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parent / ".env")

    host: str = "127.0.0.1"
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


with LOCATIONS_CONFIG_PATH.open() as _f:
    _cfg = json.load(_f)
CES_VALUES = _cfg["ces_values"]
LOCATION_CONFIG = _resolve_refs(_cfg["locations"], {"ces_values": CES_VALUES})

SHORT_TO_SNAKE = {v["short"]: v["key"] for v in CES_VALUES}
SNAKE_TO_SHORT = {v["key"]: v["short"] for v in CES_VALUES}


def _ces_short(ces_list):
    return " ".join(SNAKE_TO_SHORT.get(k, k) for k in ces_list)

THE_HAGUE_MODEL = "Mistral-Small-3.2-24B-Instruct-2506"


def _flatten_the_hague(props):
    model = props.get("models", {}).get(THE_HAGUE_MODEL, {})
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

app = FastAPI(root_path=settings.base_path)
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.get("/geo-dataset")
def geo_dataset(location: str):
    path = DATA_DIR / f"{location}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"unknown location: {location}")
    with path.open() as f:
        data = json.load(f)
    transform = TRANSFORMS.get(location)
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
    with path.open() as f:
        return json.load(f)


@app.get("/scaled")
def scaled(base: str, name: str, max_side: int = 400):
    path = IMAGES_DIR / base / "orig" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"missing image: {path.name}")
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
    return Response(buf.getvalue(), media_type="image/jpeg")


if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
