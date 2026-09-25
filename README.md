# ai-grimoire

Claude Code plugins for carrying work across sessions.

- **shift** - `/shift:end` writes a handoff filed under your workspace's name;
  `/shift:start` in the same workspace finds it, checks it against live state
  (git, PRs, anything time-sensitive), proposes next steps, and consumes it.
- **remind** - dated reminders the agent raises at the start of any session on
  the day they come due.

Both share one store: markdown files (Obsidian-friendly), SQLite, or a shared
Postgres/MySQL database when you work from more than one machine.

## Install

Requires Python 3.11+ on PATH (`python3`, `python`, or `py -3`).

```
/plugin marketplace add Switzer-Lake/ai-grimoire
/plugin install shift@ai-grimoire
/plugin install remind@ai-grimoire
```

Then optionally run `/shift:setup` to pick a storage backend. Without it,
everything is stored under `~/grimoire`.

To test an install end to end (including a branch before it's merged), follow
[docs/testing.md](docs/testing.md).

## Workspace names

A handoff is filed under the name of the workspace it came from, so several
sessions in one repo don't collide. The name is taken from the first of these
that answers:

1. a name you pass (`/shift:end` with `--name`, or `/shift:start <name>`)
2. a name pinned with `/shift:name <tag>` (per pane, or per folder outside a multiplexer)
3. wmux workspace title
4. [cmux](https://cmux.com) workspace title
5. tmux `session:window`
6. zellij session name
7. git repo name, then folder name (marked `(cwd)` as a guess)

The order is configurable.

## Configuration

`~/.config/ai-grimoire/config.toml` (override with `AI_GRIMOIRE_CONFIG`):

```toml
[storage]
backend = "files"            # files | sqlite | postgres | mysql

[storage.files]
dir = "~/grimoire"           # handoffs/, handoffs.md, reminders.md
# handoff_dir   = "~/work/handoffs"          # optional per-item overrides
# handoff_index = "~/vault/handoffs.md"
# reminders     = "~/vault/reminders.md"

[storage.sqlite]
path = "~/.local/share/ai-grimoire/grimoire.db"

[storage.postgres]           # [storage.mysql] has the same shape
dsn_env = "AI_GRIMOIRE_DSN"  # env var holding the connection string

[identity]
order = ["arg", "pinned", "wmux", "cmux", "tmux", "zellij", "git", "cwd"]
```

Connection strings are only ever read from the environment variable named by
`dsn_env`, never stored in the file. Postgres needs `psycopg[binary]`, MySQL
needs `PyMySQL` (`/shift:setup` installs them). Percent-encode special
characters in the password (e.g. `/` as `%2F`).

## Development

```
python -m pip install "pytest>=8"
python -m pytest
python scripts/build.py          # after editing core/, regenerate plugins/*/lib
python scripts/build.py --check  # CI fails if plugins/*/lib drifted from core/
```

Edit only `core/`. `plugins/*/lib/` is generated and committed so the plugins
install straight from the repo.

The SQL contract tests (`tests/test_store_contract.py`) skip unless
`AI_GRIMOIRE_TEST_PG_DSN` / `AI_GRIMOIRE_TEST_MYSQL_DSN` are set. To stand up
local servers to test against, run `dev/postgres-standup.sql` with `psql` as a
superuser and `dev/mysql-standup.sql` as root; each creates a `grimoire` user
plus `grimoire` and `grimoire_test` databases. Point the test DSNs at
`grimoire_test` only - the tests delete every row in it.

```
psql -h localhost -U postgres -v pw=localdev -f dev/postgres-standup.sql
docker exec -i mysql mysql -uroot -pmysql < dev/mysql-standup.sql
```

## License

MIT
