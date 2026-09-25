import json
from pathlib import Path

import pytest

from grimoire.cli import main


@pytest.fixture
def cfg(home, tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    path.write_text(f'[storage]\nbackend = "files"\n[storage.files]\ndir = {json.dumps(str(tmp_path / "data"))}\n',
                    encoding="utf-8")
    monkeypatch.setenv("AI_GRIMOIRE_CONFIG", str(path))
    return path


def run(capsys, *argv):
    code = main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def js(capsys, *argv):
    code, out, err = run(capsys, *argv)
    assert code == 0, err
    return json.loads(out)


def test_handoff_full_cycle(cfg, capsys, tmp_path):
    new = js(capsys, "--today", "2026-09-25", "handoff", "new", "--name", "skills")
    assert (new["workspace"], new["source"], new["date"]) == ("skills", "arg", "2026-09-25")
    assert Path(new["path"]).name == "2026-09-25-skills.md"
    Path(new["path"]).write_text("# handoff\n", encoding="utf-8")
    code, out, _ = run(capsys, "handoff", "record", "--path", new["path"], "--workspace", "skills",
                       "--source", "arg", "--summary", "did things")
    assert code == 0 and "handoffs.md" in out
    found = js(capsys, "handoff", "find", "--name", "skills")
    assert found["found"] is True and found["exists"] is True and found["summary"] == "did things"
    assert Path(found["path"]).read_text(encoding="utf-8") == "# handoff\n"
    assert len(js(capsys, "handoff", "list")) == 1
    code, out, _ = run(capsys, "handoff", "consume", "--workspace", "skills")
    assert "removed 1 row(s)" in out
    assert js(capsys, "handoff", "find", "--name", "skills")["found"] is False


def test_unicode_workspace_round_trips(cfg, capsys):
    new = js(capsys, "handoff", "new", "--name", "café — ñ")
    Path(new["path"]).write_text("x", encoding="utf-8")
    run(capsys, "handoff", "record", "--path", new["path"], "--workspace", "café — ñ", "--source", "arg",
        "--summary", "naïve — ok")
    found = js(capsys, "handoff", "find", "--name", "café — ñ")
    assert found["summary"] == "naïve — ok"


def test_remind_cycle(cfg, capsys):
    added = js(capsys, "--today", "2026-09-25", "remind", "add", "--text", "check CI", "--due", "2026-09-25",
               "--context", "[run](x)")
    assert (added["id"], added["status"]) == ("R1", "due")
    js(capsys, "--today", "2026-09-25", "remind", "add", "--text", "later", "--due", "2026-09-27")
    due = js(capsys, "--today", "2026-09-25", "remind", "due")
    assert [r["id"] for r in due["due"]] == ["R1"]
    assert [r["id"] for r in due["upcoming"]] == ["R2"]
    code, out, _ = run(capsys, "remind", "snooze", "--id", "R1", "--due", "2026-10-01")
    assert "snoozed R1 from 2026-09-25 to 2026-10-01" in out
    code, out, _ = run(capsys, "remind", "clear", "--id", "2")
    assert "cleared R2: later" in out
    assert [r["id"] for r in js(capsys, "remind", "list")] == ["R1"]


def test_bad_date_is_one_line_error(cfg, capsys):
    code, out, err = run(capsys, "remind", "add", "--text", "x", "--due", "next week")
    assert code == 1 and out == ""
    assert err.strip() == "grimoire: --due must be yyyy-MM-dd, got 'next week'"


def test_hook_silent_when_nothing_due(cfg, capsys):
    assert run(capsys, "--today", "2026-09-25", "remind", "hook") == (0, "", "")


def test_hook_reports_due(cfg, capsys):
    js(capsys, "--today", "2026-09-20", "remind", "add", "--text", "old thing", "--due", "2026-09-22")
    code, out, _ = run(capsys, "--today", "2026-09-25", "remind", "hook")
    ctx = json.loads(out)["hookSpecificOutput"]
    assert ctx["hookEventName"] == "SessionStart"
    assert "R1, 3 day(s) overdue (was due 2026-09-22): old thing" in ctx["additionalContext"]


def test_hook_silent_on_broken_config(cfg, capsys):
    cfg.write_text("[storage\n", encoding="utf-8")
    assert run(capsys, "remind", "hook") == (0, "", "")


def test_hook_silent_when_dsn_missing(cfg, capsys, monkeypatch):
    cfg.write_text('[storage]\nbackend = "postgres"\n[storage.postgres]\ndsn_env = "NOPE_DSN"\n', encoding="utf-8")
    monkeypatch.delenv("NOPE_DSN", raising=False)
    assert run(capsys, "remind", "hook") == (0, "", "")


def test_name_pin_is_used_by_handoff_new(cfg, capsys):
    pinned = js(capsys, "name", "my-tag")
    assert (pinned["workspace"], pinned["source"]) == ("my-tag", "pinned")
    new = js(capsys, "handoff", "new")
    assert (new["workspace"], new["source"]) == ("my-tag", "pinned")
    cleared = js(capsys, "name", "--clear")
    assert cleared["cleared"] is True
    assert js(capsys, "handoff", "new")["source"] != "pinned"


def test_config_init_show_check(home, tmp_path, capsys, monkeypatch):
    target = tmp_path / "new" / "config.toml"
    monkeypatch.setenv("AI_GRIMOIRE_CONFIG", str(target))
    code, out, _ = run(capsys, "config", "init", "--backend", "sqlite", "--sqlite-path", str(tmp_path / "g.db"))
    assert code == 0 and target.exists()
    code, _, err = run(capsys, "config", "init", "--backend", "files")
    assert code == 1 and "--force" in err
    shown = js(capsys, "config", "show")
    assert shown["backend"] == "sqlite" and shown["file"] == str(target)
    code, out, _ = run(capsys, "config", "check")
    assert code == 0 and out.startswith("ok")
    code, out, _ = run(capsys, "config", "path")
    assert out.strip() == str(target)


def test_config_show_never_prints_dsn(home, tmp_path, capsys, monkeypatch):
    target = tmp_path / "c.toml"
    target.write_text('[storage]\nbackend = "postgres"\n', encoding="utf-8")
    monkeypatch.setenv("AI_GRIMOIRE_CONFIG", str(target))
    monkeypatch.setenv("AI_GRIMOIRE_DSN", "postgresql://u:hunter2@h/db")
    code, out, _ = run(capsys, "config", "show")
    assert "hunter2" not in out


def test_unexpected_store_error_is_one_line(home, tmp_path, capsys, monkeypatch):
    db = tmp_path / "not-a-db.sqlite"
    db.write_text("this is not a sqlite database", encoding="utf-8")
    path = tmp_path / "config.toml"
    path.write_text(f'[storage]\nbackend = "sqlite"\n[storage.sqlite]\npath = {json.dumps(str(db))}\n',
                    encoding="utf-8")
    monkeypatch.setenv("AI_GRIMOIRE_CONFIG", str(path))
    code, out, err = run(capsys, "config", "check")
    assert code == 1
    assert out == ""
    lines = err.strip("\n").splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("grimoire: ")


def test_unexpected_files_error_is_one_line(cfg, capsys, tmp_path, monkeypatch):
    blocker = tmp_path / "blocker-dir"
    blocker.write_text("i am a file, not a directory", encoding="utf-8")
    cfg.write_text(f'[storage]\nbackend = "files"\n[storage.files]\ndir = {json.dumps(str(blocker / "data"))}\n',
                    encoding="utf-8")
    code, out, err = run(capsys, "remind", "add", "--text", "x", "--due", "2026-09-25")
    assert code == 1
    assert out == ""
    lines = err.strip("\n").splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("grimoire: ")


def test_sqlite_store_is_closed_after_command(home, tmp_path, capsys, monkeypatch):
    db = tmp_path / "g.db"
    path = tmp_path / "config.toml"
    path.write_text(f'[storage]\nbackend = "sqlite"\n[storage.sqlite]\npath = {json.dumps(str(db))}\n',
                    encoding="utf-8")
    monkeypatch.setenv("AI_GRIMOIRE_CONFIG", str(path))
    code, out, err = run(capsys, "remind", "list")
    assert code == 0, err
    assert db.exists()
    # On Windows, an unclosed sqlite handle blocks rename/delete of the file.
    db.rename(tmp_path / "moved.db")
