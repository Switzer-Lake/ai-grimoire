"""Storage backends for handoffs and reminders."""
from __future__ import annotations

from pathlib import Path

from ..config import Config
from .base import HandoffStore, ReminderStore
from .files import FileHandoffs, FileReminders
from .sql import SqlStore, connect


def open_stores(cfg: Config, scratch: Path | None = None) -> tuple[HandoffStore, ReminderStore]:
    if cfg.backend == "files":
        return FileHandoffs(cfg.handoffs_dir, cfg.handoffs_index), FileReminders(cfg.reminders_path)
    if cfg.backend == "sqlite":
        store = SqlStore("sqlite", lambda: connect("sqlite", sqlite_path=cfg.sqlite_path), cfg.describe(), scratch)
    else:
        dsn = cfg.dsn()
        store = SqlStore(cfg.backend, lambda: connect(cfg.backend, dsn=dsn), cfg.describe(), scratch)
    return store, store
