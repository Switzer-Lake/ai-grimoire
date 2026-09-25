import json
from pathlib import Path

from grimoire import pins
from grimoire.config import RESOLVERS
from grimoire.identity import Context, pane_key, resolve, run_cmd

ORDER = list(RESOLVERS)
TMUX_CMD = ("tmux", "display-message", "-p", "-t", "%3", "#{session_name}:#{window_name}")


class FakeRun:
    def __init__(self, table=None):
        self.table = table or {}
        self.calls = []

    def __call__(self, cmd, cwd):
        self.calls.append(tuple(cmd))
        return self.table.get(tuple(cmd), (127, ""))


def ctx(tmp_path, env=None, table=None, cwd=None):
    return Context(env=env or {}, cwd=cwd or str(tmp_path / "proj"), run=FakeRun(table), pins_dir=tmp_path / "state")


def test_arg_wins(tmp_path):
    c = ctx(tmp_path, table={("wmux", "current-workspace"): (0, '{"id":"ws-1","title":"skills"}')})
    ident = resolve(ORDER, "explicit", c)
    assert (ident.name, ident.source) == ("explicit", "arg")


def test_wmux_title(tmp_path):
    c = ctx(tmp_path, table={("wmux", "current-workspace"): (0, '{"id":"ws-1","title":"skills"}')})
    assert (resolve(ORDER, None, c).name, resolve(ORDER, None, c).source) == ("skills", "wmux")


def test_wmux_via_node_cli(tmp_path):
    c = ctx(tmp_path, env={"WMUX_CLI": "/x/wmux.js"},
            table={("node", "/x/wmux.js", "current-workspace"): (0, '{"id":"ws-2","title":"via-node"}')})
    assert resolve(ORDER, None, c).name == "via-node"


def test_cmux_matches_caller_workspace(tmp_path):
    listing = {"workspaces": [{"id": "other", "title": "focused-one", "selected": True},
                              {"id": "abc", "title": "cmux-ws", "selected": False}]}
    c = ctx(tmp_path, env={"CMUX_WORKSPACE_ID": "abc"},
            table={("cmux", "list-workspaces", "--json"): (0, json.dumps(listing))})
    ident = resolve(ORDER, None, c)
    assert (ident.name, ident.source) == ("cmux-ws", "cmux")


def test_tmux(tmp_path):
    c = ctx(tmp_path, env={"TMUX": "/tmp/tmux-1/default,1,0", "TMUX_PANE": "%3"},
            table={TMUX_CMD: (0, "main:editor")})
    assert (resolve(ORDER, None, c).name, resolve(ORDER, None, c).source) == ("main:editor", "tmux")


def test_tmux_ignored_outside_tmux(tmp_path):
    c = ctx(tmp_path, env={"TMUX_PANE": "%3"}, table={TMUX_CMD: (0, "main:editor")})
    assert resolve(ORDER, None, c).source == "cwd"


def test_zellij(tmp_path):
    c = ctx(tmp_path, env={"ZELLIJ_SESSION_NAME": "zj"})
    assert (resolve(ORDER, None, c).name, resolve(ORDER, None, c).source) == ("zj", "zellij")


def test_git_then_cwd(tmp_path):
    c = ctx(tmp_path, table={("git", "rev-parse", "--show-toplevel"): (0, "/x/repo\n")})
    ident = resolve(ORDER, None, c)
    assert (ident.name, ident.source, ident.guessed) == ("repo", "git", True)
    c = ctx(tmp_path)
    ident = resolve(ORDER, None, c)
    assert (ident.name, ident.source, ident.guessed) == ("proj", "cwd", True)


def test_configured_order_is_respected(tmp_path):
    c = ctx(tmp_path, table={("wmux", "current-workspace"): (0, '{"id":"ws-1","title":"skills"}'),
                             ("git", "rev-parse", "--show-toplevel"): (0, "/x/repo")})
    assert resolve(["git", "wmux"], None, c).source == "git"


def test_pin_beats_multiplexer(tmp_path):
    c = ctx(tmp_path, table={("wmux", "current-workspace"): (0, '{"id":"ws-1","title":"skills"}')})
    assert pane_key(c) == "wmux:ws-1"
    pins.set_pin("wmux:ws-1", "pinned-name", tmp_path / "state")
    ident = resolve(ORDER, None, c)
    assert (ident.name, ident.source, ident.guessed) == ("pinned-name", "pinned", False)


def test_pane_key_precedence(tmp_path):
    assert pane_key(ctx(tmp_path, env={"CMUX_WORKSPACE_ID": "abc", "TMUX": "x", "TMUX_PANE": "%1"})) == "cmux:abc"
    assert pane_key(ctx(tmp_path, env={"TMUX": "x", "TMUX_PANE": "%1"})) == "tmux:%1"
    assert pane_key(ctx(tmp_path, env={"ZELLIJ_SESSION_NAME": "zj"})) == "zellij:zj"
    assert pane_key(ctx(tmp_path)) == "cwd:" + str(Path(tmp_path / "proj").resolve())


def test_pins_round_trip_and_corrupt_file(tmp_path):
    base = tmp_path / "state"
    assert pins.get_pin("k", base) is None
    pins.set_pin("k", "v", base)
    assert pins.get_pin("k", base) == "v"
    assert pins.clear_pin("k", base) is True
    assert pins.clear_pin("k", base) is False
    (base / "pins.json").write_text("{not json", encoding="utf-8")
    assert pins.load(base) == {}


def test_run_cmd_missing_executable():
    assert run_cmd(["definitely-not-a-command-xyz-123"], ".") == (127, "")
