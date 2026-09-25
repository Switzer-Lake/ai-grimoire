from __future__ import annotations

import re
from datetime import date, datetime

from .errors import GrimoireError
from .store.base import DATE_RE, Reminder

DUE_STATUSES = ("overdue", "due", "unparseable-date")


def parse_date(s: str, what: str) -> date:
    s = (s or "").strip()
    if DATE_RE.fullmatch(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError:
            pass
    raise GrimoireError(f"{what} must be yyyy-MM-dd, got '{s}'")


def parse_id(s) -> int:
    m = re.fullmatch(r"\s*[Rr]?(\d+)\s*", str(s))
    if not m:
        raise GrimoireError(f"reminder id must look like R3 or 3, got '{s}'")
    return int(m.group(1))


def with_status(r: Reminder, today: date, ahead: int) -> dict:
    try:
        days = (parse_date(r.due, "due") - today).days
        status = "overdue" if days < 0 else "due" if days == 0 else "upcoming" if days <= ahead else "later"
    except GrimoireError:
        days, status = None, "unparseable-date"
    return {"id": f"R{r.num}", "due": r.due, "daysUntil": days, "status": status, "text": r.text,
            "context": r.context, "from": r.set_from, "setOn": r.set_on}


def hook_message(where: str, items: list[dict]) -> str:
    lines = []
    for r in items:
        if r["status"] == "overdue":
            when = f"{-r['daysUntil']} day(s) overdue (was due {r['due']})"
        elif r["status"] == "due":
            when = "due today"
        else:
            when = f"due date '{r['due']}' is unreadable"
        ctx = f" - context: {r['context']}" if r["context"] else ""
        lines.append(f"- {r['id']}, {when}: {r['text']}{ctx}")
    return "\n".join([
        f"REMINDERS DUE - from {where} (managed by the `remind` skill):",
        *lines,
        "",
        "Raise these with the user once, briefly, at the very top of your first reply, before anything else, "
        "even if the user asked about something unrelated. Do not act on them unless the user says to. "
        "For each one the user can:",
        "- work it: start a background agent seeded with the reminder and its context, then carry on with the current task;",
        "- snooze it to a new date;",
        "- clear it, if it is done or no longer needed.",
        "Use the `remind` skill for all three.",
    ])
