import re
from pathlib import Path

import pytest

from grimoire.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(ROOT.glob("plugins/*/skills/*/SKILL.md"))
CALL = re.compile(r'lib/run\.py"((?:\s+--(?:config|today)\s+\S+)*)\s+([a-z]+)(?:\s+([a-z]+))?')


def test_all_five_skills_exist():
    assert {f"{p.parts[-4]}:{p.parts[-2]}" for p in SKILLS} == {
        "shift:end", "shift:start", "shift:name", "shift:setup", "remind:remind"}


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: f"{p.parts[-4]}:{p.parts[-2]}")
def test_frontmatter_and_commands(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "missing frontmatter"
    front = m.group(1)
    assert f"name: {path.parts[-2]}" in front
    assert re.search(r"^description: .{40,}", front, re.M)
    assert "~/.claude/skills" not in text and "accelevation" not in text.lower()

    parser = build_parser()
    subs = {a.dest: a for a in parser._subparsers._group_actions}
    top = subs["cmd"].choices
    calls = CALL.findall(text)
    assert calls, "skill never calls the CLI"
    for _, cmd, action in calls:
        assert cmd in top, f"unknown command {cmd}"
        if cmd in ("handoff", "remind", "config"):
            actions = top[cmd]._subparsers._group_actions[0].choices
            assert action in actions, f"unknown action {cmd} {action}"
