# Manual install test

CI runs the automated suite (`python -m pytest`) on Linux, macOS and Windows with
Python 3.11 and 3.13, plus the SQL contract tests against real Postgres and MySQL.
This page is the part CI can't do: installing the plugins into Claude Code and
running them end to end. Run it on each OS before a release.

Everything below uses the default store under `~/grimoire`, so it never touches an
existing vault or database. If you already have a `~/.config/ai-grimoire/config.toml`,
move it aside first.

## 1. Python 3.11+ as `python3`

```bash
python3 --version
```

- **macOS:** the Xcode Command Line Tools `python3` is 3.9. Install a newer one
  (`brew install python@3.13`), open a new terminal, and check again. With 3.9 the
  skills print "ai-grimoire needs Python 3.11 or newer" and the reminder hook
  silently does nothing.
- **Windows:** if `python3` opens the Microsoft Store, `python` or `py -3` must be
  3.11+. The skills fall back to them; the hook falls back to `python`.

## 2. Get the code and install

Until the release is merged, test the branch:

```bash
git clone -b feat/v0.1 https://github.com/Switzer-Lake/ai-grimoire.git ~/ai-grimoire
```

In Claude Code:

```
/plugin marketplace add ~/ai-grimoire
/plugin install shift@ai-grimoire
/plugin install remind@ai-grimoire
```

Restart Claude Code.

## 3. Smoke test

Start a session in a throwaway folder (`mkdir ~/grimoire-smoke && cd ~/grimoire-smoke && claude`).

| # | Do | Expect |
|---|---|---|
| a | `/shift:name smoke-test` | One line: name `smoke-test`, source `pinned`. |
| b | `/shift:end testing the plugin` | A document in `~/grimoire/handoffs/`, a row at the top of `~/grimoire/handoffs.md`, and a two-line reply. |
| c | `/remind:remind remind me today to delete the smoke test` | `Set R1 for <weekday> <today>: ...` |
| d | `/clear` | The new session opens with a "REMINDERS DUE" block listing R1. |
| e | `/shift:start` | Reads the smoke-test handoff, checks it against the folder, proposes next steps, then consumes it: the row and the document are gone. |
| f | Ask it to clear R1, then `/shift:name --clear` | `cleared R1: ...`; the pin is removed. |

## 4. Workspace names

Repeat 3b and 3e **without** 3a, in each terminal you use:

| Where | `/shift:end` should report |
|---|---|
| tmux | source `tmux`, name `session:window` |
| cmux | source `cmux`, the workspace title |
| zellij | source `zellij`, the session name |
| wmux | source `wmux`, the workspace title |
| plain terminal | source `git` or `cwd`; the name is marked `(cwd)` in the index |

`/shift:start` in the same pane must find the handoff with no name typed.

## 5. Optional: SQL backends

Create the user and databases with `dev/postgres-standup.sql` or
`dev/mysql-standup.sql` (see their headers), install the driver
(`python3 -m pip install --user "psycopg[binary]"` or `PyMySQL`), then run
`/shift:setup`, choose postgres or mysql, and set the env var it names before
restarting Claude Code. Repeat section 3. Two machines pointed at the same database
should see each other's handoffs and reminders.

## 6. Optional: automated suite

```bash
cd ~/ai-grimoire
python3 -m pip install --user "pytest>=8"
python3 -m pytest -q
```

Expect everything to pass, with the postgres/mysql contract tests skipped unless
`AI_GRIMOIRE_TEST_PG_DSN` / `AI_GRIMOIRE_TEST_MYSQL_DSN` are set.

## Reporting

Open an issue for anything that doesn't match an "Expect" line, with the step,
what you saw, your OS, `python3 --version` and `claude --version`.

## Clean up

```
/plugin uninstall shift@ai-grimoire
/plugin uninstall remind@ai-grimoire
```

```bash
rm -rf ~/grimoire ~/grimoire-smoke ~/.local/state/ai-grimoire
```
