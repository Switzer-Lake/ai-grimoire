---
name: setup
description: Configure where the shift and remind plugins store handoffs and reminders - a local folder of markdown files (works with Obsidian), a SQLite file, or a shared Postgres or MySQL database for using several machines. Use when the user says "set up shift", "configure grimoire", "change where handoffs are stored", "use postgres for handoffs", "share reminders between machines", or when a shift or remind command fails because of missing configuration or a missing database driver.
---

Writes `~/.config/ai-grimoire/config.toml` (or `$AI_GRIMOIRE_CONFIG`). Both
plugins read it. Without it, everything goes to markdown files under
`~/grimoire`.

Run `python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" ...`; if `python3` is not found
use `python`, then `py -3`. Python 3.11+ is required.

## Step 1 - show what's there

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" config show
```

If `file` is set, a config already exists: show the backend and ask before
replacing it.

## Step 2 - ask one question

"Will you use this from one machine or several?"

- **One machine** - offer:
  - **files** (default): markdown tables plus one `.md` per handoff, in a folder
    they choose (default `~/grimoire`). Good for an Obsidian vault.
  - **sqlite**: one database file (default `~/.local/share/ai-grimoire/grimoire.db`).
- **Several machines** - offer **postgres** or **mysql**. Ask for the *name* of
  an environment variable to hold the connection string (default
  `AI_GRIMOIRE_DSN`). Never ask for the connection string or password itself,
  and never write it into any file. Tell the user to set it in their shell
  profile before starting Claude Code, e.g.
  `export AI_GRIMOIRE_DSN='postgresql://user:pass@host:5432/db'` or
  `mysql://user:pass@host:3306/db`. Percent-encode special characters in the
  password (e.g. `/` as `%2F`).

## Step 3 - install the driver (postgres / mysql only)

```bash
python3 -m pip install --user "psycopg[binary]"   # postgres
python3 -m pip install --user PyMySQL             # mysql
```

Use the same interpreter that runs `run.py`.

## Step 4 - write the config

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" config init --backend files --dir '<folder>'
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" config init --backend sqlite --sqlite-path '<file>'
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" config init --backend postgres --dsn-env '<VAR>'
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" config init --backend mysql --dsn-env '<VAR>'
```

Add `--force` only if the user agreed to replace an existing config.

For the files backend, the index files and the handoff documents can live in
different folders (for example the index in a vault, documents next to the
repos). That needs a hand edit after `init`; show the user these optional keys
under `[storage.files]`: `handoff_dir`, `handoff_index`, `reminders`.

## Step 5 - check it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" config check
```

`ok - ...` means both plugins can read and write. Otherwise show the one-line
error; it names the fix (missing env var, missing driver, bad connection
string). If the env var was only just set, Claude Code must be restarted from a
shell that has it.

Finish with one line: backend and location.

Switching backends does not move existing data. Mention that once if the old
store had handoffs or reminders in it.
