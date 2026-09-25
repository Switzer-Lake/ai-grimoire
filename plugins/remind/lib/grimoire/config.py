from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import GrimoireError

BACKENDS = ("files", "sqlite", "postgres", "mysql")
RESOLVERS = ("arg", "pinned", "wmux", "cmux", "tmux", "zellij", "git", "cwd")


def expand(p: str | os.PathLike) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(str(p))))


def config_path() -> Path:
    env = os.environ.get("AI_GRIMOIRE_CONFIG")
    return expand(env) if env else expand("~/.config/ai-grimoire/config.toml")


def state_dir() -> Path:
    return expand("~/.local/state/ai-grimoire")


@dataclass
class Config:
    backend: str = "files"
    files_dir: Path = field(default_factory=lambda: expand("~/grimoire"))
    handoff_dir: Path | None = None
    handoff_index: Path | None = None
    reminders_file: Path | None = None
    sqlite_path: Path = field(default_factory=lambda: expand("~/.local/share/ai-grimoire/grimoire.db"))
    dsn_env: str = "AI_GRIMOIRE_DSN"
    identity_order: list[str] = field(default_factory=lambda: list(RESOLVERS))
    loaded_from: Path | None = None

    @property
    def handoffs_dir(self) -> Path:
        return self.handoff_dir or self.files_dir / "handoffs"

    @property
    def handoffs_index(self) -> Path:
        return self.handoff_index or self.files_dir / "handoffs.md"

    @property
    def reminders_path(self) -> Path:
        return self.reminders_file or self.files_dir / "reminders.md"

    def dsn(self) -> str:
        value = os.environ.get(self.dsn_env, "").strip()
        if not value:
            raise GrimoireError(
                f"backend {self.backend} reads its connection string from ${self.dsn_env}, "
                "which is not set; set it before starting Claude Code, or run /shift:setup"
            )
        return value

    def describe(self) -> str:
        if self.backend == "files":
            return f"files: {self.handoffs_index} + {self.reminders_path}"
        if self.backend == "sqlite":
            return f"sqlite: {self.sqlite_path}"
        return f"{self.backend} (${self.dsn_env})"


def load(path: Path | None = None) -> Config:
    path = Path(path) if path else config_path()
    cfg = Config()
    if not path.exists():
        return cfg
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as e:
        raise GrimoireError(f"{path}: {e}") from None
    cfg.loaded_from = path

    storage = data.get("storage", {})
    cfg.backend = storage.get("backend", "files")
    if cfg.backend not in BACKENDS:
        raise GrimoireError(f"{path}: backend '{cfg.backend}' is not one of {', '.join(BACKENDS)}")

    files = storage.get("files", {})
    if "dir" in files:
        cfg.files_dir = expand(files["dir"])
    if "handoff_dir" in files:
        cfg.handoff_dir = expand(files["handoff_dir"])
    if "handoff_index" in files:
        cfg.handoff_index = expand(files["handoff_index"])
    if "reminders" in files:
        cfg.reminders_file = expand(files["reminders"])

    sqlite = storage.get("sqlite", {})
    if "path" in sqlite:
        cfg.sqlite_path = expand(sqlite["path"])

    if cfg.backend in ("postgres", "mysql"):
        cfg.dsn_env = storage.get(cfg.backend, {}).get("dsn_env", cfg.dsn_env)

    order = data.get("identity", {}).get("order")
    if order is not None:
        bad = [o for o in order if o not in RESOLVERS]
        if bad:
            raise GrimoireError(f"{path}: unknown identity resolver(s) {', '.join(bad)}; known: {', '.join(RESOLVERS)}")
        cfg.identity_order = list(order)
    return cfg


def render(backend: str, files_dir: str | None = None, sqlite_path: str | None = None,
           dsn_env: str | None = None) -> str:
    """A minimal config.toml. json.dumps produces valid TOML basic strings."""
    if backend not in BACKENDS:
        raise GrimoireError(f"backend '{backend}' is not one of {', '.join(BACKENDS)}")
    q = json.dumps
    lines = ["[storage]", f"backend = {q(backend)}", ""]
    if backend == "files":
        lines += ["[storage.files]", f"dir = {q(files_dir or '~/grimoire')}"]
    elif backend == "sqlite":
        lines += ["[storage.sqlite]", f"path = {q(sqlite_path or '~/.local/share/ai-grimoire/grimoire.db')}"]
    else:
        lines += [f"[storage.{backend}]", f"dsn_env = {q(dsn_env or 'AI_GRIMOIRE_DSN')}"]
    return "\n".join(lines) + "\n"
