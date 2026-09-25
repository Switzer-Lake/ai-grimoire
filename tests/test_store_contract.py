import os
from pathlib import Path

import pytest

from grimoire.config import Config
from grimoire.errors import GrimoireError
from grimoire.store import open_stores
from grimoire.store.base import find

DSN_ENV = {"postgres": "AI_GRIMOIRE_TEST_PG_DSN", "mysql": "AI_GRIMOIRE_TEST_MYSQL_DSN"}


@pytest.fixture(params=["files", "sqlite", "postgres", "mysql"])
def stores(request, tmp_path):
    kind = request.param
    if kind in DSN_ENV and not os.environ.get(DSN_ENV[kind]):
        pytest.skip(f"set {DSN_ENV[kind]} to run the {kind} contract tests")
    cfg = Config(backend=kind, files_dir=tmp_path / "files", sqlite_path=tmp_path / "g.db",
                 dsn_env=DSN_ENV.get(kind, "UNUSED"))
    hs, rs = open_stores(cfg, scratch=tmp_path / "scratch")
    if kind in DSN_ENV:
        for table in ("grimoire_handoffs", "grimoire_reminders"):
            hs._exec(f"DELETE FROM {table}")
        hs.db().commit()
    yield hs, rs
    close = getattr(hs, "close", None)
    if close:
        close()


def write_and_record(hs, date_, workspace, source, summary, body):
    p = hs.new_target(date_, workspace)
    Path(p).write_text(body, encoding="utf-8")
    hs.record(p, workspace, source, summary)
    return p


def test_new_target_names_by_date_and_slug_and_never_collides(stores):
    hs, _ = stores
    p1 = hs.new_target("2026-09-25", "fa-686 (data migration)")
    assert Path(p1).name == "2026-09-25-fa-686-data-migration.md"
    Path(p1).write_text("pending", encoding="utf-8")
    p2 = hs.new_target("2026-09-25", "fa-686 (data migration)")
    assert p2 != p1
    assert Path(p2).name == "2026-09-25-fa-686-data-migration-2.md"


def test_record_find_open_consume(stores):
    hs, _ = stores
    write_and_record(hs, "2026-09-24", "skills", "wmux", "first day", "# Day one\n")
    write_and_record(hs, "2026-09-25", "skills", "wmux", "second day", "# Day two\n")
    write_and_record(hs, "2026-09-25", "other", "wmux", "not mine", "# Other\n")
    newest, extra = find(hs, "skills")
    assert (newest.date, newest.summary) == ("2026-09-25", "second day")
    assert [r.summary for r in extra] == ["first day"]
    assert Path(hs.open(newest)).read_text(encoding="utf-8") == "# Day two\n"
    msgs = hs.consume("skills")
    assert any("removed 2 row(s)" in m for m in msgs)
    assert find(hs, "skills") == (None, [])
    assert find(hs, "other")[0].summary == "not mine"


def test_consume_is_case_and_accent_fold_consistent_with_find(stores):
    hs, _ = stores
    write_and_record(hs, "2026-09-25", "Über", "wmux", "accented", "x")
    write_and_record(hs, "2026-09-25", "uber", "wmux", "decoy", "y")
    msgs = hs.consume("über")
    assert any("removed 1 row(s)" in m for m in msgs)
    assert find(hs, "uber")[0].summary == "decoy"


def test_same_day_twice_newest_first(stores):
    hs, _ = stores
    write_and_record(hs, "2026-09-25", "ws", "wmux", "morning", "a")
    write_and_record(hs, "2026-09-25", "ws", "wmux", "evening", "b")
    newest, extra = find(hs, "ws")
    assert newest.summary == "evening"
    assert [r.summary for r in extra] == ["morning"]


def test_guessed_label_is_found_by_base_name(stores):
    hs, _ = stores
    write_and_record(hs, "2026-09-25", "repo", "cwd", "guessed", "x")
    newest, _ = find(hs, "Repo")
    assert (newest.label, newest.workspace) == ("repo (cwd)", "repo")


def test_summary_with_pipe_and_newline(stores):
    hs, _ = stores
    write_and_record(hs, "2026-09-25", "ws", "wmux", "a | b\nc", "x")
    assert find(hs, "ws")[0].summary == "a | b c"


def test_record_requires_document(stores, tmp_path):
    hs, _ = stores
    with pytest.raises(GrimoireError, match="write it before recording"):
        hs.record(str(tmp_path / "nope.md"), "ws", "wmux", "s")


def test_consume_nothing(stores):
    hs, _ = stores
    assert "nothing to consume" in hs.consume("ghost")[0]


def test_reminder_ids_are_never_reused(stores):
    _, rs = stores
    a = rs.add("one", "2026-09-26", "", "ws", "2026-09-25")
    b = rs.add("two", "2026-09-27", "", "ws", "2026-09-25")
    assert b.num == a.num + 1
    rs.remove(b.num)
    c = rs.add("three", "2026-09-28", "", "ws", "2026-09-25")
    assert c.num == b.num + 1


def test_reminders_sorted_by_due_then_id(stores):
    _, rs = stores
    late = rs.add("late", "2026-10-01", "", "ws", "2026-09-25")
    early = rs.add("early", "2026-09-26", "[ctx](x.md)", "ws (cwd)", "2026-09-25")
    got = rs.all()
    assert [r.num for r in got] == [early.num, late.num]
    assert (got[0].context, got[0].set_from, got[0].set_on) == ("[ctx](x.md)", "ws (cwd)", "2026-09-25")


def test_update_due_and_remove(stores):
    _, rs = stores
    r = rs.add("text | with pipe", "2026-09-26", "", "ws", "2026-09-25")
    old, new = rs.update_due(r.num, "2026-10-05")
    assert (old, new.due, new.text) == ("2026-09-26", "2026-10-05", "text | with pipe")
    assert rs.remove(r.num).text == "text | with pipe"
    assert rs.all() == []
    with pytest.raises(GrimoireError, match=f"R{r.num}"):
        rs.remove(r.num)
