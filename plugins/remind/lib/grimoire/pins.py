from __future__ import annotations

import json
from pathlib import Path

from .config import state_dir
from .fsutil import write_atomic


def _file(base: Path | None) -> Path:
    return Path(base or state_dir()) / "pins.json"


def load(base: Path | None = None) -> dict[str, str]:
    try:
        data = json.loads(_file(base).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict[str, str], base: Path | None) -> None:
    write_atomic(_file(base), json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def get_pin(key: str, base: Path | None = None) -> str | None:
    return load(base).get(key)


def set_pin(key: str, name: str, base: Path | None = None) -> None:
    data = load(base)
    data[key] = name
    _save(data, base)


def clear_pin(key: str, base: Path | None = None) -> bool:
    data = load(base)
    if key not in data:
        return False
    del data[key]
    _save(data, base)
    return True
