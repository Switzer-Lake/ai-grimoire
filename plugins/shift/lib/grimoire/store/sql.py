"""One SQL backend for sqlite, postgres and mysql. The handoff body lives in the
database, not as a path: a path only exists on the machine that wrote it."""
from __future__ import annotations

import socket
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from .. import config
from ..errors import GrimoireError
from ..fsutil import slug, write_atomic
from .base import HandoffRow, Reminder, base_label, date_from_name, label_for

SCHEMA_VERSION = 1

_ID = {"sqlite": "INTEGER PRIMARY KEY AUTOINCREMENT", "postgres": "BIGSERIAL PRIMARY KEY",
       "mysql": "BIGINT AUTO_INCREMENT PRIMARY KEY"}
_BODY = {"sqlite": "TEXT", "postgres": "TEXT", "mysql": "LONGTEXT"}


def ddl(backend: str) -> list[str]:
    tail = " DEFAULT CHARSET=utf8mb4" if backend == "mysql" else ""
    return [
        f"CREATE TABLE IF NOT EXISTS grimoire_schema (version INTEGER NOT NULL){tail}",
        f"CREATE TABLE IF NOT EXISTS grimoire_handoffs (id {_ID[backend]}, workspace VARCHAR(255) NOT NULL, "
        f"source VARCHAR(16) NOT NULL, created_on VARCHAR(10) NOT NULL, summary TEXT NOT NULL, "
        f"body {_BODY[backend]} NOT NULL, machine VARCHAR(255) NOT NULL){tail}",
        f"CREATE TABLE IF NOT EXISTS grimoire_reminders (id {_ID[backend]}, due VARCHAR(10) NOT NULL, "
        f"reminder TEXT NOT NULL, context TEXT NOT NULL, set_from VARCHAR(255) NOT NULL, "
        f"set_on VARCHAR(10) NOT NULL){tail}",
    ]


def _scrub(text: str, dsn: str | None, *passwords: str | None) -> str:
    """Mask a DSN and its password fragment(s) out of driver error text."""
    for pw in passwords:
        if pw:
            text = text.replace(pw, "***")
    if dsn:
        text = text.replace(dsn, "***")
    return text


def connect(backend: str, sqlite_path=None, dsn: str | None = None, timeout: int = 3):
    if backend == "sqlite":
        import sqlite3
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(sqlite_path), timeout=timeout)
    if backend == "postgres":
        try:
            import psycopg
        except ImportError:
            raise GrimoireError('psycopg is not installed - run: python -m pip install --user "psycopg[binary]"') from None
        u = urlparse(dsn or "")
        raw_pw = u.password or ""
        pw = unquote(raw_pw)
        try:
            return psycopg.connect(dsn, connect_timeout=timeout)
        except Exception as e:
            raise GrimoireError(f"cannot connect to postgres: {_scrub(str(e), dsn, pw, raw_pw)}") from None
    if backend == "mysql":
        u = urlparse(dsn or "")
        if u.scheme not in ("mysql", "mysql+pymysql"):
            raise GrimoireError("mysql connection string must look like mysql://user:pass@host:3306/dbname")
        try:
            host, port, user = u.hostname or "localhost", u.port or 3306, unquote(u.username or "")
            raw_pw = u.password or ""
            password = unquote(raw_pw)
            database = u.path.lstrip("/")
        except ValueError:
            raise GrimoireError(
                "mysql connection string is malformed - percent-encode special characters in the "
                "password (e.g. / as %2F)"
            ) from None
        try:
            import pymysql
        except ImportError:
            raise GrimoireError("PyMySQL is not installed - run: python -m pip install --user PyMySQL") from None
        try:
            return pymysql.connect(host=host, port=port, user=user, password=password,
                                   database=database, connect_timeout=timeout, charset="utf8mb4")
        except Exception as e:
            raise GrimoireError(f"cannot connect to mysql: {_scrub(str(e), dsn, password, raw_pw)}") from None
    raise GrimoireError(f"not a SQL backend: {backend}")


class SqlStore:
    def __init__(self, backend: str, connect_fn: Callable[[], Any], label: str, scratch: Path | None = None):
        self.backend = backend
        self._connect = connect_fn
        self._db = None
        self.label = label
        self.scratch = Path(scratch) if scratch else config.state_dir() / "scratch"
        self._p = "?" if backend == "sqlite" else "%s"
        self.scratch.mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.scratch / "pending").mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.scratch / "reading").mkdir(parents=True, exist_ok=True, mode=0o700)

    # -- plumbing -----------------------------------------------------------
    def describe(self) -> str:
        return self.label

    def db(self):
        if self._db is None:
            self._db = self._connect()
            self._ensure_schema()
        return self._db

    def _exec(self, sql: str, args: tuple = ()):
        cur = self.db().cursor()
        cur.execute(sql.replace("?", self._p), args)
        return cur

    def _ensure_schema(self) -> None:
        cur = self._db.cursor()
        for stmt in ddl(self.backend):
            cur.execute(stmt)
        cur.execute("SELECT COUNT(*) FROM grimoire_schema")
        if cur.fetchone()[0] == 0:
            cur.execute(f"INSERT INTO grimoire_schema (version) VALUES ({self._p})", (SCHEMA_VERSION,))
        self._db.commit()

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    # -- handoffs -----------------------------------------------------------
    def new_target(self, date_: str, workspace: str) -> str:
        d = self.scratch / "pending"
        d.mkdir(parents=True, exist_ok=True)
        base = f"{date_}-{slug(workspace)}"
        p, n = d / f"{base}.md", 2
        while p.exists():
            p, n = d / f"{base}-{n}.md", n + 1
        return str(p)

    def record(self, path: str, workspace: str, source: str, summary: str) -> str:
        p = Path(path)
        if not p.exists():
            raise GrimoireError(f"handoff not found: {path} - write it before recording it")
        body = p.read_text(encoding="utf-8")
        date_ = date_from_name(p) or date.today().isoformat()
        self._exec("INSERT INTO grimoire_handoffs (workspace, source, created_on, summary, body, machine) "
                   "VALUES (?, ?, ?, ?, ?, ?)",
                   (base_label(workspace), source, date_, " ".join((summary or "").split()), body, socket.gethostname()))
        self.db().commit()
        if p.resolve().is_relative_to((self.scratch / "pending").resolve()):
            p.unlink()
        return f"recorded in {self.label}"

    def rows(self) -> list[HandoffRow]:
        cur = self._exec("SELECT id, workspace, source, created_on, summary, machine FROM grimoire_handoffs "
                         "ORDER BY created_on DESC, id DESC")
        return [HandoffRow(date=r[3], workspace=r[1], label=label_for(r[1], r[2]), summary=r[4], path=None,
                           exists=True, machine=r[5], order=-int(r[0]), key=int(r[0])) for r in cur.fetchall()]

    def open(self, row: HandoffRow) -> str:
        r = self._exec("SELECT body FROM grimoire_handoffs WHERE id = ?", (row.key,)).fetchone()
        if not r:
            raise GrimoireError(f"handoff {row.key} is gone from {self.label}")
        out = self.scratch / "reading" / f"{row.date}-{slug(row.workspace)}-{row.key}.md"
        write_atomic(out, r[0])
        return str(out)

    def consume(self, workspace: str) -> list[str]:
        target = base_label(workspace)
        ids = [r.key for r in self.rows() if r.workspace.casefold() == target.casefold()]
        if not ids:
            return [f"no rows for '{workspace}' in {self.label} - nothing to consume"]
        for i in ids:
            self._exec("DELETE FROM grimoire_handoffs WHERE id = ?", (i,))
        self.db().commit()
        for i in ids:
            for p in (self.scratch / "reading").glob(f"*-{i}.md"):
                p.unlink(missing_ok=True)
        return [f"removed {len(ids)} row(s) for '{target}' from {self.label}"]

    # -- reminders ----------------------------------------------------------
    def all(self) -> list[Reminder]:
        cur = self._exec("SELECT id, due, reminder, context, set_from, set_on FROM grimoire_reminders ORDER BY due, id")
        return [Reminder(int(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in cur.fetchall()]

    def add(self, text: str, due: str, context: str, set_from: str, set_on: str) -> Reminder:
        sql = "INSERT INTO grimoire_reminders (due, reminder, context, set_from, set_on) VALUES (?, ?, ?, ?, ?)"
        args = (due, text, context or "", set_from or "", set_on)
        if self.backend == "postgres":
            num = int(self._exec(sql + " RETURNING id", args).fetchone()[0])
        else:
            num = int(self._exec(sql, args).lastrowid)
        self.db().commit()
        return Reminder(num, due, text, context or "", set_from or "", set_on)

    def _get(self, num: int) -> Reminder:
        r = self._exec("SELECT id, due, reminder, context, set_from, set_on FROM grimoire_reminders WHERE id = ?",
                       (num,)).fetchone()
        if not r:
            raise GrimoireError(f"no reminder R{num} in {self.label}")
        return Reminder(int(r[0]), r[1], r[2], r[3], r[4], r[5])

    def update_due(self, num: int, due: str) -> tuple[str, Reminder]:
        r = self._get(num)
        old = r.due
        self._exec("UPDATE grimoire_reminders SET due = ? WHERE id = ?", (due, num))
        self.db().commit()
        r.due = due
        return old, r

    def remove(self, num: int) -> Reminder:
        r = self._get(num)
        self._exec("DELETE FROM grimoire_reminders WHERE id = ?", (num,))
        self.db().commit()
        return r
