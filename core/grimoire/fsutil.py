from __future__ import annotations

import contextlib
import os
import re
import tempfile
from pathlib import Path


def slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s or "workspace"


def read_lines(path: Path) -> tuple[list[str], str]:
    """Lines without terminators, plus the file's newline style. Drops a UTF-8 BOM."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        raw = f.read()
    newline = "\r\n" if "\r\n" in raw else "\n"
    return raw.splitlines(), newline


def write_lines(path: Path, lines: list[str], newline: str = "\n") -> None:
    write_atomic(path, newline.join(lines) + newline)


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file + rename so an interrupted write can't truncate the target."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
