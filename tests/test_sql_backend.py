import builtins
from pathlib import Path

import pytest

from grimoire.config import Config
from grimoire.errors import GrimoireError
from grimoire.store import open_stores
from grimoire.store.base import find
from grimoire.store.sql import SCHEMA_VERSION, connect


@pytest.fixture
def sqlite_store(tmp_path):
    hs, rs = open_stores(Config(backend="sqlite", sqlite_path=tmp_path / "db" / "g.db"), scratch=tmp_path / "scratch")
    yield hs
    hs.close()


def test_schema_version_row(sqlite_store):
    rows = sqlite_store._exec("SELECT version FROM grimoire_schema").fetchall()
    assert rows == [(SCHEMA_VERSION,)]


def test_body_stored_in_db_and_pending_file_removed(sqlite_store, tmp_path):
    p = sqlite_store.new_target("2026-09-25", "ws")
    assert Path(p).is_relative_to(tmp_path / "scratch" / "pending")
    Path(p).write_text("# body\n", encoding="utf-8")
    sqlite_store.record(p, "ws", "wmux", "s")
    assert not Path(p).exists()
    newest, _ = find(sqlite_store, "ws")
    assert newest.path is None and newest.exists is True and newest.machine
    opened = sqlite_store.open(newest)
    assert Path(opened).is_relative_to(tmp_path / "scratch" / "reading")
    assert Path(opened).read_text(encoding="utf-8") == "# body\n"


def test_record_does_not_delete_files_outside_pending(sqlite_store, tmp_path):
    mine = tmp_path / "2026-09-25-mine.md"
    mine.write_text("keep", encoding="utf-8")
    sqlite_store.record(str(mine), "ws", "wmux", "s")
    assert mine.exists()


def test_schema_created_once(tmp_path):
    cfg = Config(backend="sqlite", sqlite_path=tmp_path / "g.db")
    for _ in range(2):
        hs, _ = open_stores(cfg, scratch=tmp_path / "s")
        hs.rows()
        hs.close()
    hs, _ = open_stores(cfg, scratch=tmp_path / "s")
    assert hs._exec("SELECT COUNT(*) FROM grimoire_schema").fetchone()[0] == 1
    hs.close()


def _block_import(monkeypatch, name):
    real = builtins.__import__

    def fake(mod, *a, **k):
        if mod == name:
            raise ImportError(mod)
        return real(mod, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)


def test_missing_postgres_driver_names_install_command(monkeypatch):
    _block_import(monkeypatch, "psycopg")
    with pytest.raises(GrimoireError, match=r'pip install --user "psycopg\[binary\]"'):
        connect("postgres", dsn="postgresql://x@localhost/db")


def test_missing_mysql_driver_names_install_command(monkeypatch):
    _block_import(monkeypatch, "pymysql")
    with pytest.raises(GrimoireError, match="pip install --user PyMySQL"):
        connect("mysql", dsn="mysql://x@localhost/db")


def test_open_stores_requires_dsn(monkeypatch, tmp_path):
    monkeypatch.delenv("NOPE_DSN", raising=False)
    with pytest.raises(GrimoireError, match=r"\$NOPE_DSN"):
        open_stores(Config(backend="postgres", dsn_env="NOPE_DSN"))


def test_default_scratch_is_under_state_dir(home, tmp_path):
    from grimoire.config import state_dir
    hs, _ = open_stores(Config(backend="sqlite", sqlite_path=tmp_path / "db" / "g.db"))
    assert Path(hs.scratch).is_relative_to(state_dir())
    hs.close()


def test_malformed_mysql_dsn_password_not_leaked():
    with pytest.raises(GrimoireError) as exc:
        connect("mysql", dsn="mysql://user:s3cr/et@host:3306/db")
    msg = str(exc.value)
    assert "s3cr" not in msg
    assert "percent-encode" in msg


def test_scrub_masks_password_and_dsn():
    from grimoire.store.sql import _scrub
    dsn = "postgresql://user:s3cr3t@host:5432/db"
    text = f"connection to server failed: {dsn} password authentication for user \"user\" with s3cr3t"
    scrubbed = _scrub(text, dsn, "s3cr3t")
    assert "s3cr3t" not in scrubbed
    assert dsn not in scrubbed
    assert "***" in scrubbed


def test_consume_removes_reading_copy(sqlite_store, tmp_path):
    p = sqlite_store.new_target("2026-09-25", "ws")
    Path(p).write_text("# body\n", encoding="utf-8")
    sqlite_store.record(p, "ws", "wmux", "s")
    newest, _ = find(sqlite_store, "ws")
    opened = Path(sqlite_store.open(newest))
    assert opened.exists()
    sqlite_store.consume("ws")
    assert not opened.exists()
