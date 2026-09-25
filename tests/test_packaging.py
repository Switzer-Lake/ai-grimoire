import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def test_marketplace_lists_both_plugins():
    m = load(".claude-plugin/marketplace.json")
    assert m["name"] == "ai-grimoire"
    assert m["owner"]["name"]
    by_name = {p["name"]: p for p in m["plugins"]}
    assert set(by_name) == {"shift", "remind"}
    for name, p in by_name.items():
        assert p["source"] == f"./plugins/{name}"
        assert load(f"plugins/{name}/.claude-plugin/plugin.json")["name"] == name


def test_hook_calls_run_py():
    h = load("plugins/remind/hooks/hooks.json")
    entry = h["hooks"]["SessionStart"][0]
    assert entry["matcher"] == "startup|clear"
    cmd = entry["hooks"][0]["command"]
    assert '"${CLAUDE_PLUGIN_ROOT}/lib/run.py" remind hook' in cmd
    assert cmd.endswith("|| exit 0")


def run_py(plugin, *args, env_extra=None, tmp_path=None):
    import os
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(ROOT / "plugins" / plugin / "lib" / "run.py"), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env)


def test_run_py_hook_silent_without_config(tmp_path):
    p = run_py("remind", "remind", "hook",
               env_extra={"AI_GRIMOIRE_CONFIG": str(tmp_path / "none.toml"), "HOME": str(tmp_path),
                          "USERPROFILE": str(tmp_path)})
    assert (p.returncode, p.stdout, p.stderr) == (0, "", "")


def test_run_py_shift_config_path(tmp_path):
    p = run_py("shift", "config", "path", env_extra={"AI_GRIMOIRE_CONFIG": str(tmp_path / "c.toml")})
    assert p.returncode == 0
    assert p.stdout.strip() == str(tmp_path / "c.toml")
