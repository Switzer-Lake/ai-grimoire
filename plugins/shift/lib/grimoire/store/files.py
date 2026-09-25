"""Markdown-table backend. Reads and writes the same tables the original
PowerShell skills produced, so an Obsidian vault carries over unchanged."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import unquote

from ..errors import GrimoireError
from ..fsutil import read_lines, slug, write_lines
from .base import DATE_RE, HandoffRow, Reminder, base_label, date_from_name, label_for

SEP = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")
CELL_SPLIT = re.compile(r"(?<!\\)\|")
NEXT_ID = re.compile(r"<!--\s*next-id:\s*(\d+)\s*-->")

HANDOFF_HEADER = [
    "# Handoffs",
    "",
    "End-of-session handoffs, newest first. Written by `/shift:end`; `/shift:start`",
    "reads the newest one for its workspace and then removes it.",
    "",
    "| Date | Workspace | Handoff | Summary |",
    "|---|---|---|---|",
]
REMINDER_PREAMBLE = [
    "# Reminders",
    "",
    "Open reminders, soonest first. Managed by the `remind` skill: new sessions and",
    "`/shift:start` raise anything that is due. Hand edits are fine; keep the table",
    "shape and the `next-id` comment. Cleared reminders are deleted, not archived.",
    "",
    "<!-- next-id: 1 -->",
    "",
]
REMINDER_HEAD = [
    "| ID | Due | Reminder | Context | Set from | Set on |",
    "|---|---|---|---|---|---|",
]


_LINE_BREAK = re.compile("\r\n|[\r\n\u2028\u2029\x85\x0b\x0c\x1c-\x1e]")


def cell(text: str) -> str:
    """A table cell can't contain a bare pipe, and a line break would end the row."""
    return _LINE_BREAK.sub(" ", text or "").replace("|", r"\|").strip()


def split_cells(line: str) -> list[str]:
    return CELL_SPLIT.split(line.strip().strip("|"))


_WIN_DRIVE = re.compile(r"^/([A-Za-z]):(/.*)?$")


def uri_to_path(uri: str) -> str:
    """Like urlparse+url2pathname, but tolerant of PS-written `file:` links.

    The old PowerShell writer used [uri]::EscapeUriString, which escapes spaces
    and non-ASCII but leaves `#`, `?`, `(`, `)` unescaped. urlparse treats a bare
    `#`/`?` as the start of a fragment/query and truncates the path, so we parse
    `file:` URIs by hand instead of going through urlparse.
    """
    if not uri.startswith("file:"):
        return unquote(uri)
    rest = uri[len("file:"):]
    if rest.startswith("//"):
        rest = rest[2:]
        if rest and rest[0] != "/":
            # An authority component is present: "localhost" or (rarely) a host.
            slash = rest.find("/")
            host, tail = (rest, "") if slash < 0 else (rest[:slash], rest[slash:])
            if host.lower() not in ("", "localhost"):
                decoded = unquote(tail).replace("/", "\\")
                return f"\\\\{host}{decoded}"
            rest = tail
    if not rest.startswith("/"):
        rest = "/" + rest
    decoded = unquote(rest)
    m = _WIN_DRIVE.match(decoded)
    if m:
        drive, tail = m.group(1), m.group(2) or ""
        native = f"{drive}:{tail}"
        return native.replace("/", "\\") if os.name == "nt" else native
    return decoded.replace("/", "\\") if os.name == "nt" else decoded


def _inside(path: str, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


class FileHandoffs:
    def __init__(self, handoff_dir: Path, index: Path):
        self.dir = Path(handoff_dir)
        self.index = Path(index)

    def describe(self) -> str:
        return str(self.index)

    def new_target(self, date_: str, workspace: str) -> str:
        self.dir.mkdir(parents=True, exist_ok=True)
        base = f"{date_}-{slug(workspace)}"
        p, n = self.dir / f"{base}.md", 2
        while p.exists():
            p, n = self.dir / f"{base}-{n}.md", n + 1
        return str(p)

    def record(self, path: str, workspace: str, source: str, summary: str) -> str:
        p = Path(path)
        if not p.exists():
            raise GrimoireError(f"handoff not found: {path} - write it before recording it")
        full = p.resolve()
        date_ = date_from_name(full) or date.today().isoformat()
        row = f"| {date_} | {cell(label_for(workspace, source))} | [{full.name}]({full.as_uri()}) | {cell(summary)} |"
        if not self.index.exists():
            write_lines(self.index, HANDOFF_HEADER + [row])
            return f"created {self.index}"
        lines, nl = read_lines(self.index)
        sep = next((i for i, line in enumerate(lines) if SEP.match(line)), -1)
        if sep < 0:
            write_lines(self.index, lines + [""] + HANDOFF_HEADER[5:7] + [row], nl)
            return f"recorded in {self.index} (the table was missing; re-added it at the end)"
        write_lines(self.index, lines[: sep + 1] + [row] + lines[sep + 1:], nl)
        return f"recorded in {self.index}"

    def rows(self) -> list[HandoffRow]:
        if not self.index.exists():
            return []
        lines, _ = read_lines(self.index)
        out = []
        for i, line in enumerate(lines):
            if not line.lstrip().startswith("|") or SEP.match(line):
                continue
            cells = split_cells(line)
            if len(cells) < 4 or not DATE_RE.fullmatch(cells[0].strip()):
                continue
            label, link = cells[1].strip(), cells[2].strip()
            m = re.search(r"\]\(((?:[^()]|\([^()]*\))+)\)", link)
            if m:
                file = uri_to_path(m.group(1))
            else:
                m = re.search(r"\[([^\]]+)\]", link)
                file = str(self.dir / m.group(1)) if m else None
            out.append(HandoffRow(
                date=cells[0].strip(), workspace=base_label(label), label=label,
                summary=cells[3].replace(r"\|", "|").strip(), path=file,
                exists=bool(file and Path(file).exists()), order=i, key=i))
        return out

    def open(self, row: HandoffRow) -> str:
        if not (row.path and Path(row.path).exists()):
            raise GrimoireError(f"handoff document is missing: {row.path}")
        return row.path

    def consume(self, workspace: str) -> list[str]:
        target = base_label(workspace)
        mine = [r for r in self.rows() if r.workspace.casefold() == target.casefold()]
        if not mine:
            return [f"no rows for '{workspace}' in {self.index} - nothing to consume"]
        drop = {r.key for r in mine}
        lines, nl = read_lines(self.index)
        write_lines(self.index, [line for i, line in enumerate(lines) if i not in drop], nl)
        msgs = []
        for r in mine:
            if not r.path:
                continue
            if not Path(r.path).exists():
                msgs.append(f"already gone {r.path}")
            elif not _inside(r.path, self.dir):
                msgs.append(f"left in place (outside {self.dir}) {r.path}")
            else:
                try:
                    Path(r.path).unlink()
                    msgs.append(f"deleted {r.path}")
                except OSError as e:
                    msgs.append(f"could not delete {r.path}: {e}")
        msgs.append(f"removed {len(mine)} row(s) for '{target}' from {self.index}")
        return msgs


@dataclass
class _State:
    pre: list[str]
    rows: list[Reminder] = field(default_factory=list)
    post: list[str] = field(default_factory=list)
    next_id: int = 1
    newline: str = "\n"


class FileReminders:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.warning: str | None = None

    def describe(self) -> str:
        return str(self.path)

    def _read(self) -> _State:
        if not self.path.exists():
            return _State(pre=list(REMINDER_PREAMBLE))
        lines, nl = read_lines(self.path)
        sep = next((i for i, line in enumerate(lines) if SEP.match(line)), -1)
        state = _State(pre=[], newline=nl)
        pending_no_id: list[list[str]] = []
        if sep < 1:
            # The table is gone. Keep what they wrote and re-add the table below it.
            state.pre = lines + [""]
            self.warning = f"the table in {self.path} was missing; re-added it below the existing text"
        else:
            state.pre = lines[: sep - 1]
            end = sep + 1
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                cells = [c.replace(r"\|", "|").strip() for c in split_cells(lines[end])]
                if len(cells) >= 3 and re.fullmatch(r"[Rr]?\d+", cells[0]):
                    cells += [""] * (6 - len(cells))
                    state.rows.append(Reminder(int(cells[0].lstrip("Rr")), cells[1], cells[2], cells[3], cells[4], cells[5]))
                elif len(cells) >= 3 and cells[2]:
                    # Hand-added row with no ID (or a non-R first cell): keep it, assign an ID below.
                    cells += [""] * (6 - len(cells))
                    pending_no_id.append(cells)
                end += 1
            state.post = lines[end:]
        from_comment = 1
        for line in state.pre:
            m = NEXT_ID.search(line)
            if m:
                from_comment = int(m.group(1))
        next_id = max(from_comment, max((r.num for r in state.rows), default=0) + 1)
        for cells in pending_no_id:
            state.rows.append(Reminder(next_id, cells[1], cells[2], cells[3], cells[4], cells[5]))
            next_id += 1
        state.next_id = next_id
        return state

    def _write(self, state: _State) -> None:
        stamp = f"<!-- next-id: {state.next_id} -->"
        pre = list(state.pre)
        if any(NEXT_ID.search(line) for line in pre):
            pre = [NEXT_ID.sub(stamp, line) for line in pre]
        else:
            pre = pre + [stamp, ""]
        body = [f"| R{r.num} | {r.due} | {cell(r.text)} | {cell(r.context)} | {cell(r.set_from)} | {r.set_on} |"
                for r in sorted(state.rows, key=lambda r: (r.due, r.num))]
        write_lines(self.path, pre + REMINDER_HEAD + body + state.post, state.newline)

    def _find(self, state: _State, num: int) -> Reminder:
        for r in state.rows:
            if r.num == num:
                return r
        raise GrimoireError(f"no reminder R{num} in {self.path}")

    def all(self) -> list[Reminder]:
        return sorted(self._read().rows, key=lambda r: (r.due, r.num))

    def add(self, text: str, due: str, context: str, set_from: str, set_on: str) -> Reminder:
        state = self._read()
        r = Reminder(state.next_id, due, text, context, set_from, set_on)
        state.rows.append(r)
        state.next_id += 1
        self._write(state)
        return r

    def update_due(self, num: int, due: str) -> tuple[str, Reminder]:
        state = self._read()
        r = self._find(state, num)
        old, r.due = r.due, due
        self._write(state)
        return old, r

    def remove(self, num: int) -> Reminder:
        state = self._read()
        r = self._find(state, num)
        state.rows = [x for x in state.rows if x.num != num]
        self._write(state)
        return r
