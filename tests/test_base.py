from datetime import date

import pytest

from grimoire.errors import GrimoireError
from grimoire.reminders import hook_message, parse_date, parse_id, with_status
from grimoire.store.base import HandoffRow, Reminder, base_label, date_from_name, find, label_for


def test_labels():
    assert label_for("repo", "cwd") == "repo (cwd)"
    assert label_for("repo", "git") == "repo (cwd)"
    assert label_for("skills", "wmux") == "skills"
    assert base_label("repo (cwd)") == "repo"
    assert base_label("fa-686 (data migration)") == "fa-686 (data migration)"


def test_date_from_name():
    assert date_from_name("/x/2026-09-24-epicor-2.md") == "2026-09-24"
    assert date_from_name("/x/notes.md") is None


class FakeStore:
    def __init__(self, rows):
        self._rows = rows

    def rows(self):
        return self._rows


def row(date_, label, order):
    return HandoffRow(date=date_, workspace=base_label(label), label=label, summary="", path=None,
                      exists=False, order=order, key=order)


def test_find_ignores_cwd_marker_and_case():
    rows = [row("2026-09-24", "Repo (cwd)", 0), row("2026-09-24", "other", 1),
            row("2026-09-23", "repo", 2), row("2026-09-24", "repo", 3)]
    newest, extra = find(FakeStore(rows), "repo")
    assert newest.order == 0
    assert [r.order for r in extra] == [3, 2]


def test_find_none():
    assert find(FakeStore([]), "x") == (None, [])


def test_parse_date_strict():
    assert parse_date("2026-09-25", "--due") == date(2026, 9, 25)
    for bad in ("2026-9-5", "next week", "25/09/2026"):
        with pytest.raises(GrimoireError, match="yyyy-MM-dd"):
            parse_date(bad, "--due")


def test_parse_id():
    assert parse_id("R3") == 3
    assert parse_id("r12") == 12
    assert parse_id("7") == 7
    with pytest.raises(GrimoireError):
        parse_id("X3")


def test_with_status():
    today = date(2026, 9, 25)
    mk = lambda due: with_status(Reminder(1, due, "t"), today, 3)
    assert mk("2026-09-20")["status"] == "overdue"
    assert mk("2026-09-20")["daysUntil"] == -5
    assert mk("2026-09-25")["status"] == "due"
    assert mk("2026-09-28")["status"] == "upcoming"
    assert mk("2026-09-29")["status"] == "later"
    bad = mk("soon")
    assert (bad["status"], bad["daysUntil"]) == ("unparseable-date", None)
    assert set(mk("2026-09-25")) == {"id", "due", "daysUntil", "status", "text", "context", "from", "setOn"}


def test_hook_message():
    today = date(2026, 9, 25)
    items = [with_status(Reminder(4, "2026-09-25", "rename flow", "[map](x.md)"), today, 3),
             with_status(Reminder(5, "2026-09-22", "check CI"), today, 3)]
    msg = hook_message("files: /v/reminders.md", items)
    assert msg.startswith("REMINDERS DUE - from files: /v/reminders.md")
    assert "- R4, due today: rename flow - context: [map](x.md)" in msg
    assert "- R5, 3 day(s) overdue (was due 2026-09-22): check CI" in msg
    assert "work it" in msg and "snooze" in msg and "clear" in msg
