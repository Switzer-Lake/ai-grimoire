---
name: start
description: Pick up the last handoff filed for this workspace, verify what it claims against live state, and propose next steps. Use whenever the user says "start of day", "sod", "start shift", "good morning", "pick up where we left off", "what was I doing", "resume yesterday", or otherwise signals they are starting a work session and want the previous session's context restored. Counterpart to /shift:end - it reads the newest handoff for this workspace, then consumes it.
argument-hint: "Optional: a workspace name to resume instead of this one"
---

Restore the last session's context for **this workspace**, check it still
holds, and say what to do first. Then consume the handoff: it is a message to
this session, not an archive.

"The newest handoff" is the wrong thing to grab; the newest handoff *for this
workspace's name* is the right one.

## Running the CLI

Every step runs `python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" ...`. If `python3`
is not found, use `python`, then `py -3` (Windows). If it reports that Python
3.11+ is required, tell the user and stop.

## Step 0 - reminders

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" remind due
```

Prints `{ today, store, due[], upcoming[] }`. Reminders belong to the user, not
the workspace, so report them whatever workspace this is. If a "REMINDERS DUE"
block already raised them this session, skip the repeat and just list
`upcoming`. Answers (work it / snooze / clear) go through the `remind` skill.
Carry on with step 1 either way.

## Step 1 - find this workspace's handoff

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" handoff find
```

Add `--name '<name>'` if the user named a workspace to resume.

Prints JSON: `workspace`, `source`, `found`, `path`, `date`, `summary`,
`exists`, `machine`, `extra`, `rows`, `store`. The name is resolved exactly the
way `/shift:end` resolves it, so the two agree.

- **`found: false`** - say there is no handoff for this workspace, list `rows`
  (date / workspace / summary) so the user can name one to resume, and stop. Do
  not fall back to the newest row overall: resuming another workspace's work by
  accident is worse than starting cold.
- **`found: true`, `exists: false`** - the row points at a document that isn't
  on disk. Say so, show the summary as the only surviving context, and ask
  before consuming it.
- **`extra` not empty** - older handoffs for this workspace that step 4 will
  also remove. Name them (date + summary) so nothing disappears silently.
- **`machine`** (database backends) - if it differs from this machine, mention
  where the handoff was written; local paths in it may not exist here.

## Step 2 - read it

Read the document at `path`. Treat its "next steps" as a proposal from the last
session, not a verdict; step 3 exists because it may no longer be true.

## Step 3 - verify before you propose

Check only what the handoff actually claims, against live state:

- **Repo state** - current branch, `git status`, whether commits it calls
  unpushed are still unpushed, whether branches it names still exist.
- **Issues and PRs** - if `gh` is available, the state of every one it
  references: still open, merged, reviewed? Someone may have acted overnight.
- **Blocked or deferred items** - "blocked on X being down" is a thing to test,
  not to repeat.
- **Time-sensitive claims** - deploys in flight, jobs running.

Report drift plainly. "The PR it says is awaiting review was merged last night"
is the most valuable line this skill produces.

## Step 4 - consume the handoff

After step 2, never before:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" handoff consume --workspace '<workspace from step 1>'
```

This removes every handoff for that workspace and deletes their documents.
There is no undo, which is why the content must already be in this session.
With a shared database, it removes them for every machine.

Skip this step if the user is only browsing ("what was I doing?") rather than
starting work.

## Step 5 - hand them the session

Short, in order:

0. Reminders from step 0: one line per due reminder (ID, how overdue, text,
   plus the work it / snooze / clear offer), then upcoming ones as one "coming
   up" line. Omit if both are empty.
1. One line of where things stand, from the handoff.
2. Drift found in step 3.
3. A short numbered list of next steps, most likely first.
4. One line confirming the handoff was consumed.

Then stop and wait. Do not start on step 1 of the plan until the user says so.

## Notes

- `handoff list` shows everything waiting across all workspaces without
  resuming anything.
- To resume several workspaces, run the whole sequence per workspace; two
  handoffs read into one session blur into one plan.
