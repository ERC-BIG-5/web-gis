import json
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "geo-datasets"
IMAGES_DIR = ROOT / "data" / "images"
WEB_DIST = ROOT / "web" / "dist"

CES_VALUES = [
    {"key": "physical_recreation",     "short": "PHY", "name": "physical recreation"},
    {"key": "experiential_recreation", "short": "EXP", "name": "experiential recreation"},
    {"key": "scientific",              "short": "SCI", "name": "scientific"},
    {"key": "educational",             "short": "EDU", "name": "educational"},
    {"key": "heritage",                "short": "HER", "name": "heritage"},
    {"key": "aesthetics",              "short": "AES", "name": "aesthetics"},
    {"key": "social_relations",        "short": "SOC", "name": "social relations"},
    {"key": "symbolic",                "short": "SYM", "name": "symbolic"},
    {"key": "sacred_religious",        "short": "SAC", "name": "sacred / religious"},
    {"key": "entertainment",           "short": "ENT", "name": "entertainment"},
    {"key": "existence",               "short": "EXI", "name": "existence"},
    {"key": "bequest",                 "short": "BEQ", "name": "bequest"},
]

SHORT_TO_SNAKE = {
    "PHY": "physical_recreation",
    "EXP": "experiential_recreation",
    "SCI": "scientific",
    "EDU": "educational",
    "HER": "heritage",
    "AES": "aesthetics",
    "SOC": "social_relations",
    "SYM": "symbolic",
    "SAC": "sacred_religious",
    "ENT": "entertainment",
    "EXI": "existence",
    "BEQ": "bequest",
}
SNAKE_TO_SHORT = {v: k for k, v in SHORT_TO_SNAKE.items()}


def _ces_short(ces_list):
    return " ".join(SNAKE_TO_SHORT.get(k, k) for k in ces_list)

LOCATION_CONFIG = {
    "barcelona": {
        "base_media_path": "barcelona",
        "classification": {
            "label": "CES classes",
            "filters": [{"field": "ces", "values": CES_VALUES, "default": "all"}],
        },
        "popup_fields": [
            {"field": "name"},
            {"field": "ces", "label": "CES"},
        ],
        "evaluator": {
            "label": "CES evaluation",
            "field": "ces",
            "values": CES_VALUES,
        },
    },
    "the_hague": {
        "base_media_path": "the_hague",
        "classification": {
            "label": "Mistral classification",
            "filters": [
                {
                    "field": "nature",
                    "label": "nature in",
                    "values": [
                        {"key": "text", "name": "text"},
                        {"key": "images", "name": "images"},
                    ],
                    "default": "all",
                },
                {"field": "ces", "values": CES_VALUES, "default": "all"},
            ],
        },
        "popup_fields": [
            {"field": "id", "label": "ID"},
            {"field": "text", "label": "text"},
            {"field": "nature_text", "label": "nature in text"},
            {"field": "nature_images", "label": "nature in images"},
            {"field": "nature_terms_text", "label": "nature terms (text)"},
            {"field": "nature_terms_images", "label": "nature terms (images)"},
            {"field": "ces", "label": "CES"},
        ],
        "evaluator": {
            "label": "CES evaluation",
            "field": "ces",
            "values": CES_VALUES,
        },
    },
}

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

app = FastAPI()
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
    uvicorn.run(app, host="127.0.0.1", port=8955)
