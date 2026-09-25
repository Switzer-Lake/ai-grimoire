from pathlib import Path

from grimoire.store.base import find
from grimoire.store.files import FileHandoffs, FileReminders

HANDOFFS = (
    "# Handoffs\n"
    "\n"
    "End-of-day handoff documents, newest first. Written by the `end-of-day` skill \u2014\n"
    "the documents themselves live outside the vault, under `~\\Work\\accelevation\\handoffs\\`.\n"
    "\n"
    "| Date | Workspace | Handoff | Summary |\n"
    "|---|---|---|---|\n"
    "| 2026-09-24 | epicor | [2026-09-24-epicor.md](file:///C:/Users/me/handoffs/2026-09-24-epicor.md) | #592 REST-only \\| BAQs retire |\n"
    "| 2026-09-23 | hmi (cwd) | [2026-09-23-hmi.md](file:///C:/Users/me/handoffs/2026-09-23-hmi.md) | guessed name |\n"
)

REMINDERS = "\r\n".join([
    "# Reminders",
    "",
    "Open reminders, soonest first. Hand edits are fine.",
    "",
    "<!-- next-id: 15 -->",
    "",
    "| ID | Due | Reminder | Context | Set from | Set on |",
    "|---|---|---|---|---|---|",
    "| R13 | 2026-09-28 | Two prod failures \\| investigate | [x](y.md) | field_admin | 2026-09-24 |",
    "| R4 | 2026-10-02 | Rename flow |  | hmi (cwd) | 2026-09-20 |",
    "",
    "Notes kept below the table.",
]) + "\r\n"


def test_reads_existing_vault_index(tmp_path):
    idx = tmp_path / "handoffs.md"
    idx.write_bytes(HANDOFFS.encode("utf-8"))
    rows = FileHandoffs(tmp_path / "handoffs", idx).rows()
    assert [(r.date, r.label, r.workspace) for r in rows] == [
        ("2026-09-24", "epicor", "epicor"), ("2026-09-23", "hmi (cwd)", "hmi")]
    assert rows[0].summary == "#592 REST-only | BAQs retire"
    assert rows[0].path.replace("\\", "/").endswith("handoffs/2026-09-24-epicor.md")
    assert rows[0].exists is False


def test_record_inserts_only_one_line_under_the_separator(tmp_path):
    idx = tmp_path / "handoffs.md"
    idx.write_bytes(HANDOFFS.encode("utf-8"))
    hs = FileHandoffs(tmp_path / "handoffs", idx)
    p = hs.new_target("2026-09-25", "skills")
    Path(p).write_text("doc", encoding="utf-8")
    hs.record(p, "skills", "wmux", "shipped")
    before = HANDOFFS.split("\n")
    after = idx.read_bytes().decode("utf-8").split("\n")
    assert after[:7] == before[:7]
    assert after[7].startswith("| 2026-09-25 | skills | [2026-09-25-skills.md](file:")
    assert after[7].endswith(") | shipped |")
    assert after[8:] == before[7:]


def test_record_creates_index(tmp_path):
    hs = FileHandoffs(tmp_path / "handoffs", tmp_path / "idx" / "handoffs.md")
    p = hs.new_target("2026-09-25", "ws")
    Path(p).write_text("doc", encoding="utf-8")
    assert "created" in hs.record(p, "ws", "wmux", "s")
    assert find(hs, "ws")[0].exists is True


def test_record_readds_missing_table(tmp_path):
    idx = tmp_path / "handoffs.md"
    idx.write_text("# My notes\n\nI deleted the table.\n", encoding="utf-8")
    hs = FileHandoffs(tmp_path / "handoffs", idx)
    p = hs.new_target("2026-09-25", "ws")
    Path(p).write_text("doc", encoding="utf-8")
    assert "table was missing" in hs.record(p, "ws", "wmux", "s")
    text = idx.read_text(encoding="utf-8")
    assert text.startswith("# My notes\n\nI deleted the table.\n")
    assert find(hs, "ws")[0].summary == "s"


def test_consume_leaves_documents_outside_handoff_dir(tmp_path):
    outside = tmp_path / "important.md"
    outside.write_text("keep me", encoding="utf-8")
    idx = tmp_path / "handoffs.md"
    idx.write_text(
        "| Date | Workspace | Handoff | Summary |\n|---|---|---|---|\n"
        f"| 2026-09-25 | ws | [important.md]({outside.resolve().as_uri()}) | hand-edited |\n",
        encoding="utf-8")
    msgs = FileHandoffs(tmp_path / "handoffs", idx).consume("ws")
    assert outside.exists()
    assert any("left in place" in m for m in msgs)
    assert "hand-edited" not in idx.read_text(encoding="utf-8")


def test_consume_deletes_documents_inside_handoff_dir(tmp_path):
    hs = FileHandoffs(tmp_path / "handoffs", tmp_path / "handoffs.md")
    p = hs.new_target("2026-09-25", "ws")
    Path(p).write_text("doc", encoding="utf-8")
    hs.record(p, "ws", "wmux", "s")
    hs.consume("ws")
    assert not Path(p).exists()


def test_reminders_golden_round_trip_keeps_crlf_and_trailing_text(tmp_path):
    f = tmp_path / "reminders.md"
    f.write_bytes(REMINDERS.encode("utf-8"))
    rs = FileReminders(f)
    got = rs.all()
    assert [(r.num, r.text) for r in got] == [(13, "Two prod failures | investigate"), (4, "Rename flow")]
    r = rs.add("temp", "2026-12-01", "", "ws", "2026-09-25")
    assert r.num == 15
    rs.remove(15)
    expected = REMINDERS.replace("<!-- next-id: 15 -->", "<!-- next-id: 16 -->")
    assert f.read_bytes().decode("utf-8") == expected


def test_reminders_new_file(tmp_path):
    f = tmp_path / "sub" / "reminders.md"
    rs = FileReminders(f)
    assert rs.all() == []
    assert rs.add("x", "2026-09-26", "", "ws", "2026-09-25").num == 1
    text = f.read_text(encoding="utf-8")
    assert "<!-- next-id: 2 -->" in text
    assert "| R1 | 2026-09-26 | x |  | ws | 2026-09-25 |" in text


def test_reminders_reshaped_file_keeps_text(tmp_path):
    f = tmp_path / "reminders.md"
    f.write_text("# Reminders\n\nI removed the table by accident.\n", encoding="utf-8")
    rs = FileReminders(f)
    rs.add("x", "2026-09-26", "", "ws", "2026-09-25")
    assert rs.warning and "re-added" in rs.warning
    text = f.read_text(encoding="utf-8")
    assert text.startswith("# Reminders\n\nI removed the table by accident.\n")
    assert [r.text for r in FileReminders(f).all()] == ["x"]


def test_unparseable_due_is_kept(tmp_path):
    f = tmp_path / "reminders.md"
    f.write_text("| ID | Due | Reminder | Context | Set from | Set on |\n|---|---|---|---|---|---|\n"
                 "| R1 | next tues | fix me | | ws | 2026-09-25 |\n", encoding="utf-8")
    assert FileReminders(f).all()[0].due == "next tues"
