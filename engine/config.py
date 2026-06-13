"""Loads config.yaml — the single source of truth for every tunable number (PRD §13)."""
from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else _CONFIG_PATH
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()
