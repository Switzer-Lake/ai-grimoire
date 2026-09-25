# ai-grimoire — design

Date: 2026-09-25
Status: draft, awaiting review

## Goal

Publish two Claude Code plugins, generalized from skills that already work on
one machine:

- **`shift`**: `/shift:end` writes an end-of-session handoff filed under the
  current workspace's name; `/shift:start` finds that workspace's newest
  handoff, verifies it against live state, proposes next steps, then consumes
  it.
- **`remind`**: dated reminders that a SessionStart hook (and `/shift:start`)
  raise on the day they come due.

The originals are hardwired to one Windows machine: PowerShell scripts, a fixed
Obsidian vault path, and wmux as the only source of workspace names. The public
version must run anywhere Claude Code runs, name workspaces in any terminal, and
store data in a local folder or a shared database.

### Success criteria

1. Both plugins install from the `ai-grimoire` marketplace on Windows, macOS and
   Linux with Python 3.11+ and nothing else (file and SQLite backends).
2. A handoff written by `/shift:end` in a wmux, cmux, tmux or zellij pane is
   found by `/shift:start` in the same pane the next day, with no name typed.
3. In any other terminal, `/shift:name <tag>` (or `--name`) gives the same
   result.
4. Two machines configured against the same Postgres or MySQL database see each
   other's handoffs and reminders.
5. The current machine can switch over by writing a config file that points the
   file backend at its existing vault files — no data migration.

### Non-goals

- Codex or other agents. The CLI stays agent-agnostic so this can be added
  later, but only Claude Code is packaged and tested.
- Publishing the Python package to PyPI.
- Archiving consumed handoffs or cleared reminders (same as today: deleted).
- Syncing the file backend between machines. Multi-machine means a database.

### Constraint

The working skills in `~/.claude/skills/{end-of-day,start-of-day,remind}` are
not modified. This repo is built and tested independently; the switch-over is a
separate, manual step after it works.

## Repo layout

```
ai-grimoire/
  .claude-plugin/marketplace.json      # lists shift + remind
  core/run.py                          # launcher: Python version check, then grimoire.cli.main
  core/grimoire/                       # the only hand-edited copy of shared code
    __init__.py
    cli.py                             # entry point: `handoff ...`, `remind ...`, `name ...`, `config ...`
    config.py                          # load config.toml, env overrides, defaults
    identity.py                        # workspace-name resolver chain
    pins.py                            # per-machine pinned names
    store/base.py                      # HandoffStore, ReminderStore protocols
    store/files.py                     # markdown tables + .md documents
    store/sql.py                       # sqlite / postgres / mysql
  plugins/
    shift/
      .claude-plugin/plugin.json
      lib/run.py, lib/grimoire/        # generated copy of core/run.py + core/grimoire
      skills/end/SKILL.md              # /shift:end
      skills/start/SKILL.md            # /shift:start
      skills/name/SKILL.md             # /shift:name
      skills/setup/SKILL.md            # /shift:setup
    remind/
      .claude-plugin/plugin.json
      lib/run.py, lib/grimoire/        # generated copy of core/run.py + core/grimoire
      skills/remind/SKILL.md
      hooks/hooks.json                 # SessionStart (startup|clear) -> remind hook
  scripts/build.py                     # copy core/ into each plugin's lib/; --check fails on drift
  tests/
  README.md
  LICENSE                              # MIT
```

`lib/grimoire/` is committed (plugins install from the repo as-is) but never
edited by hand. `scripts/build.py --check` runs in CI and fails if either copy
differs from `core/`.

### Launcher

Skills and the hook run `python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" <args>`
(Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` in skill text and hook
commands). Skills tell the agent to retry with `python`, then `py -3`, when
`python3` is not found; the hook command chains `python3 ... || python ...`.
`run.py` checks for Python 3.11+ and prints one line naming the requirement if
it is older (the hook variant exits 0 silently instead; see Hook).

There is no `bin/` directory: plugin `bin/` folders are put on PATH, so two
plugins shipping the same `grimoire` command would collide, and claude.ai /
Cowork refuse plugins that contain one.

## Workspace identity

`identity.resolve(explicit=None) -> {name, source}` walks `identity.order` from
config (default below) and returns the first resolver that answers:

| Source   | How                                                                                   |
|----------|---------------------------------------------------------------------------------------|
| `arg`    | Name passed explicitly (`--name`, or the skill's argument)                            |
| `pinned` | `pins.json` entry for this pane key (see Pins)                                        |
| `wmux`   | `wmux current-workspace` (or `node $WMUX_CLI current-workspace`) → `.title`           |
| `cmux`   | `CMUX_WORKSPACE_ID` set → `cmux list-workspaces --json`, entry whose `id` matches → `.title` |
| `tmux`   | `TMUX` set → `tmux display-message -p -t $TMUX_PANE '#{session_name}:#{window_name}'`  |
| `zellij` | `ZELLIJ_SESSION_NAME` env var (does not follow a later rename)                        |
| `git`    | basename of `git rev-parse --show-toplevel`                                           |
| `cwd`    | basename of the working directory                                                     |

All multiplexer resolvers are caller-scoped (they answer for the pane the shell
is in, not the focused one) and time out after 2 s. Any failure falls through
to the next resolver.

`git` and `cwd` are guesses. Stores record `source`; the file backend renders a
guessed name as `name (cwd)` exactly as today, and lookups strip that marker so
a handoff filed from outside a pane is still found from inside one.

`/shift:end`, `/shift:start` and `remind add` all call the same function, so
they cannot disagree about a name.

### Pins

`/shift:name <tag>` stores `{pane_key: tag}` in
`~/.local/state/ai-grimoire/pins.json` (per machine — pane IDs mean nothing
elsewhere). `pane_key` is the first available of `CMUX_WORKSPACE_ID`, the wmux
workspace id, `TMUX_PANE`, `ZELLIJ_SESSION_NAME`, else the absolute cwd.
`/shift:name` with no argument shows the current name and its source;
`/shift:name --clear` removes the pin.

## Config

Path: `$AI_GRIMOIRE_CONFIG`, else `~/.config/ai-grimoire/config.toml` on every
OS. No file means all defaults (file backend under `~/grimoire`).

```toml
[storage]
backend = "files"            # files | sqlite | postgres | mysql

[storage.files]
dir = "~/grimoire"           # handoffs/, handoffs.md, reminders.md under here
# per-item overrides:
# handoff_dir   = "~/Work/accelevation/handoffs"
# handoff_index = "~/Work/accelevation/_vault/handoffs.md"
# reminders     = "~/Work/accelevation/_vault/reminders.md"

[storage.sqlite]
path = "~/.local/share/ai-grimoire/grimoire.db"

[storage.postgres]           # [storage.mysql] has the same shape
dsn_env = "AI_GRIMOIRE_DSN"  # name of the env var holding the connection string

[identity]
order = ["arg", "pinned", "wmux", "cmux", "tmux", "zellij", "git", "cwd"]
```

Credentials are never stored in the file; `dsn_env` names the variable to read.
`grimoire config show` prints the resolved config with the DSN redacted;
`grimoire config check` opens the store and reports success or the exact error.

## Storage

### Interfaces

```
HandoffStore
  new_target(date, workspace) -> target      # where to write; unique per day+workspace
  record(target, workspace, source, summary, body)
  find(workspace) -> {newest, extra[]}       # newest-first, marker-insensitive match
  list() -> rows[]
  consume(workspace) -> removed[]            # every row for the workspace + its document

ReminderStore
  add(text, due, context, set_from) -> reminder
  list(today, ahead) -> reminders[]          # with daysUntil + status
  snooze(id, due) / clear(id)
```

Status values and JSON shapes match the current scripts (`overdue | due |
upcoming | later | unparseable-date`; IDs `R<n>`, never reused), so the ported
SKILL.md text changes as little as possible.

### files backend

Byte-compatible with today's files: the same markdown tables, the same
`<!-- next-id: N -->` comment, the same newest-first handoff index with
`file:///` links, the same pipe escaping and "table missing → re-add it"
recovery. `new_target` returns a file path and the agent writes the document
there, as today. Writes go to a temp file then rename, so an interrupted write
can't truncate a file the user reads for months.

### SQL backends (sqlite, postgres, mysql)

One schema, created on first use:

```
schema_version(version)
handoffs(id PK, workspace, source, created_on DATE, summary, body TEXT, machine)
reminders(id PK, due DATE, text, context, set_from, set_on DATE)
```

The handoff **body is stored in the database**, not as a path — a path only
exists on the machine that wrote it. For SQL, `new_target` returns a local temp
file path; the agent writes the document there, and `record` reads it into
`body` and deletes the temp file. `find` returns the body written back out to a
temp file so `/shift:start` reads it the same way in every backend.

`machine` is the hostname and is shown in listings. Reminder IDs come from the
`id` column, so they are never reused. `sqlite` uses the stdlib driver;
`postgres` needs `psycopg` (v3) and `mysql` needs `PyMySQL`, imported only when
selected. A missing driver fails with the exact install command.

## Skills

Behavior is ported from the current skills; only the mechanics change.

- **`/shift:end [focus]`** — `grimoire handoff new` → write the handoff to
  the returned target following the `handoff`-style content guidance (inlined
  into this skill, since a public install can't assume a separate `handoff`
  skill) → `grimoire handoff record ...` with a one-line summary → report path
  and row in two lines.
- **`/shift:start [workspace]`** — `grimoire remind due` (skip if the hook
  already raised them) → `grimoire handoff find` → read → verify claims
  against live state (git, GitHub via `gh` when available, time-sensitive
  claims) → report drift and next steps → `grimoire handoff consume` only after
  the document is in the session, and not when the user is only browsing.
- **`/shift:name [tag | --clear]`** — pin, show or clear the workspace name.
- **`/shift:setup`** — ask which backend; ask its path or DSN env var name;
  install the driver if needed; write `config.toml`; run `grimoire config
  check`. Never writes a password into the file.
- **`/remind:remind`** (plugin skills are namespaced; it also triggers from its
  description on "remind me ...") — same as today: add / list / due / snooze / clear / work it,
  with the date-resolution rules and the "raise once per session" rule.

References to Accelevation-specific workflows (ticket boards, the vault path)
are removed; the skills stay generic.

## Hook

`plugins/remind/hooks/hooks.json` registers SessionStart with matcher
`startup|clear`, running `lib/run.py remind hook`. It prints the
`hookSpecificOutput` JSON only when something is due, and **never fails a
session**: a missing Python, a missing config, an unreachable database or a
broken file all print nothing and exit 0. For SQL backends it uses a 3 s
connect timeout so an offline laptop doesn't stall startup.

## Error handling

- CLI commands exit non-zero with one-line messages that say what to do
  (`psycopg not installed — run: python -m pip install --user "psycopg[binary]"`).
- `record` refuses when the handoff document doesn't exist yet.
- `consume` is a no-op with a message when there is nothing to consume.
- Dates accepted only as `yyyy-MM-dd`; the agent resolves phrases like "next
  week" itself, as today.

## Testing

- pytest, run on Windows, macOS and Linux in GitHub Actions.
- One shared contract test suite for HandoffStore and ReminderStore, run against
  every backend: files and sqlite everywhere; postgres and mysql via service
  containers on Linux.
- Golden-file tests: the files backend reads and writes fixtures copied from the
  current machine's `handoffs.md` / `reminders.md` format and produces
  identical output.
- Identity tests with each resolver's command and environment faked.
- Hook test: every failure mode prints nothing and exits 0.
- `scripts/build.py --check` in CI.

## Switch-over on the current machine (after release)

1. Install both plugins from the marketplace.
2. Write `config.toml` with the files backend and the three per-item overrides
   pointing at the current vault paths.
3. Run `/shift:start` against an existing handoff and `/remind` list; confirm
   both read today's data.
4. Remove the old skills and the old SessionStart hook entry from settings, so
   reminders aren't raised twice.
