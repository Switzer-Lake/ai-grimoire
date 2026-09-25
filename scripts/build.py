"""Copy core/ into each plugin's lib/. Installed plugins can't import from each
other, so each one ships its own copy; --check fails if a copy has drifted."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

PLUGINS = ("shift", "remind")


def _sources(root: Path) -> dict[str, Path]:
    pkg = root / "core" / "grimoire"
    files = {f"grimoire/{p.relative_to(pkg).as_posix()}": p for p in pkg.rglob("*.py") if "__pycache__" not in p.parts}
    files["run.py"] = root / "core" / "run.py"
    return files


def build(root: Path) -> None:
    for plugin in PLUGINS:
        lib = root / "plugins" / plugin / "lib"
        shutil.rmtree(lib, ignore_errors=True)
        for rel, src in _sources(root).items():
            dest = lib / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)


def check(root: Path) -> list[str]:
    problems = []
    sources = _sources(root)
    for plugin in PLUGINS:
        lib = root / "plugins" / plugin / "lib"
        for rel, src in sources.items():
            dest = lib / rel
            if not dest.exists():
                problems.append(f"{plugin}: missing lib/{rel}")
            elif dest.read_bytes().replace(b"\r\n", b"\n") != src.read_bytes().replace(b"\r\n", b"\n"):
                problems.append(f"{plugin}: lib/{rel} differs from core")
        if lib.exists():
            for p in lib.rglob("*.py"):
                rel = p.relative_to(lib).as_posix()
                if "__pycache__" not in p.parts and rel not in sources:
                    problems.append(f"{plugin}: lib/{rel} is not in core")
    return problems


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    if "--check" in sys.argv[1:]:
        found = check(root)
        for line in found:
            print(line)
        sys.exit(1 if found else 0)
    build(root)
    print("built plugins/*/lib from core/")
