import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_config():
    return json.loads((ROOT / "config.json").read_text())
