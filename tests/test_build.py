import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build", ROOT / "scripts" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_repo_is_in_sync():
    assert build.check(ROOT) == []


def test_check_detects_drift(tmp_path):
    for part in ("core", "plugins"):
        shutil.copytree(ROOT / part, tmp_path / part, ignore=shutil.ignore_patterns("__pycache__"))
    assert build.check(tmp_path) == []
    (tmp_path / "plugins" / "shift" / "lib" / "grimoire" / "cli.py").write_text("# edited\n", encoding="utf-8")
    (tmp_path / "plugins" / "remind" / "lib" / "grimoire" / "stray.py").write_text("", encoding="utf-8")
    problems = build.check(tmp_path)
    assert any("shift" in p and "cli.py" in p for p in problems)
    assert any("stray.py" in p for p in problems)
    build.build(tmp_path)
    assert build.check(tmp_path) == []
