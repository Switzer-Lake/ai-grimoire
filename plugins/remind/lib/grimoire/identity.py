"""Which unit of work is this? Several workspaces often share one cwd, so a
multiplexer's caller-scoped workspace title beats the repo or folder name."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from . import pins

GUESSES = ("git", "cwd")
Run = Callable[[list[str], str], tuple[int, str]]
_UNSET = object()


@dataclass
class Identity:
    name: str
    source: str

    @property
    def guessed(self) -> bool:
        return self.source in GUESSES


def run_cmd(cmd: list[str], cwd: str, timeout: float = 2.0) -> tuple[int, str]:
    exe = shutil.which(cmd[0])  # also finds .cmd/.bat shims on Windows
    if not exe:
        return 127, ""
    try:
        p = subprocess.run([exe, *cmd[1:]], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return p.returncode, (p.stdout or "").strip()


def _json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None


class Context:
    def __init__(self, env: Mapping[str, str] | None = None, cwd: str | None = None,
                 run: Run | None = None, pins_dir: Path | None = None):
        self.env = os.environ if env is None else env
        self.cwd = cwd or os.getcwd()
        self.run = run or run_cmd
        self.pins_dir = pins_dir
        self._wmux = _UNSET

    def wmux(self) -> dict | None:
        """`wmux current-workspace` answers for the pane this shell is in, not the focused one."""
        if self._wmux is _UNSET:
            code, out = self.run(["wmux", "current-workspace"], self.cwd)
            if code != 0 and self.env.get("WMUX_CLI"):
                code, out = self.run(["node", self.env["WMUX_CLI"], "current-workspace"], self.cwd)
            info = _json(out) if code == 0 else None
            self._wmux = info if isinstance(info, dict) else None
        return self._wmux


def pane_key(ctx: Context) -> str:
    if ctx.env.get("CMUX_WORKSPACE_ID"):
        return "cmux:" + ctx.env["CMUX_WORKSPACE_ID"]
    info = ctx.wmux()
    if info and info.get("id"):
        return "wmux:" + str(info["id"])
    if ctx.env.get("TMUX") and ctx.env.get("TMUX_PANE"):
        return "tmux:" + ctx.env["TMUX_PANE"]
    if ctx.env.get("ZELLIJ_SESSION_NAME"):
        return "zellij:" + ctx.env["ZELLIJ_SESSION_NAME"]
    return "cwd:" + str(Path(ctx.cwd).resolve())


def _pinned(ctx: Context) -> str | None:
    return pins.get_pin(pane_key(ctx), ctx.pins_dir)


def _wmux(ctx: Context) -> str | None:
    info = ctx.wmux()
    return info.get("title") if info else None


def _cmux(ctx: Context) -> str | None:
    ws_id = ctx.env.get("CMUX_WORKSPACE_ID")
    if not ws_id:
        return None
    code, out = ctx.run(["cmux", "list-workspaces", "--json"], ctx.cwd)
    data = _json(out) if code == 0 else None
    items = data.get("workspaces", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    for w in items:
        if isinstance(w, dict) and w.get("id") == ws_id:
            return w.get("title")
    return None


def _tmux(ctx: Context) -> str | None:
    if not ctx.env.get("TMUX"):
        return None
    cmd = ["tmux", "display-message", "-p"]
    if ctx.env.get("TMUX_PANE"):
        cmd += ["-t", ctx.env["TMUX_PANE"]]
    cmd.append("#{session_name}:#{window_name}")
    code, out = ctx.run(cmd, ctx.cwd)
    return out if code == 0 else None


def _zellij(ctx: Context) -> str | None:
    return ctx.env.get("ZELLIJ_SESSION_NAME")


def _git(ctx: Context) -> str | None:
    code, out = ctx.run(["git", "rev-parse", "--show-toplevel"], ctx.cwd)
    return Path(out.strip()).name if code == 0 and out.strip() else None


def _cwd(ctx: Context) -> str:
    return Path(ctx.cwd).name or ctx.cwd


_RESOLVERS: dict[str, Callable[[Context], str | None]] = {
    "pinned": _pinned, "wmux": _wmux, "cmux": _cmux, "tmux": _tmux,
    "zellij": _zellij, "git": _git, "cwd": _cwd,
}


def resolve(order: list[str], explicit: str | None = None, ctx: Context | None = None) -> Identity:
    ctx = ctx or Context()
    for source in order:
        name = explicit if source == "arg" else _RESOLVERS[source](ctx)
        if name and name.strip():
            return Identity(name.strip(), source)
    return Identity(_cwd(ctx), "cwd")
