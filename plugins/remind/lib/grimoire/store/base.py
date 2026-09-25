from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..identity import GUESSES

GUESS_MARKER = " (cwd)"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def base_label(label: str) -> str:
    """Strip the guessed-name marker so a handoff filed outside a pane is found from inside one."""
    return re.sub(r"\s*\(cwd\)\s*$", "", label).strip()


def label_for(workspace: str, source: str) -> str:
    return workspace + GUESS_MARKER if source in GUESSES else workspace


def date_from_name(path) -> str | None:
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", Path(path).name)
    return m.group(1) if m else None


@dataclass
class HandoffRow:
    date: str
    workspace: str
    label: str
    summary: str
    path: str | None
    exists: bool
    machine: str = ""
    order: int = 0  # lower = newer among rows with the same date
    key: int = 0    # backend handle: line index (files) or row id (sql)

    def public(self) -> dict:
        return {"date": self.date, "workspace": self.workspace, "label": self.label, "path": self.path,
                "exists": self.exists, "summary": self.summary, "machine": self.machine}


@dataclass
class Reminder:
    num: int
    due: str
    text: str
    context: str = ""
    set_from: str = ""
    set_on: str = ""


class HandoffStore(Protocol):
    def describe(self) -> str: ...
    def new_target(self, date: str, workspace: str) -> str: ...
    def record(self, path: str, workspace: str, source: str, summary: str) -> str: ...
    def rows(self) -> list[HandoffRow]: ...
    def open(self, row: HandoffRow) -> str: ...
    def consume(self, workspace: str) -> list[str]: ...


class ReminderStore(Protocol):
    def describe(self) -> str: ...
    def all(self) -> list[Reminder]: ...
    def add(self, text: str, due: str, context: str, set_from: str, set_on: str) -> Reminder: ...
    def update_due(self, num: int, due: str) -> tuple[str, Reminder]: ...
    def remove(self, num: int) -> Reminder: ...


def find(store: HandoffStore, workspace: str) -> tuple[HandoffRow | None, list[HandoffRow]]:
    target = base_label(workspace).casefold()
    mine = sorted((r for r in store.rows() if r.workspace.casefold() == target), key=lambda r: r.order)
    mine.sort(key=lambda r: r.date, reverse=True)  # stable: same-date rows keep `order`
    return (mine[0], mine[1:]) if mine else (None, [])
