---
name: end
description: Write an end-of-session handoff and file it under this workspace's name so the next session in the same workspace can pick it up. Use whenever the user says "end of day", "eod", "end shift", "wrapping up", "shutting down for the day", "log today's work", "call it a day", or otherwise signals they are finishing a work session and want its state captured before they stop.
argument-hint: "Optional: what the next session should focus on"
---

Capture this session's work as a handoff document and file it under the name of
the **workspace** it came from. `/shift:start` in the same workspace will find
it, check it against live state, and consume it.

The unit of work is the workspace, not the repo: several workspaces often sit in
one directory (one per issue), so the workspace name is what tells them apart.

## Running the CLI

Every step runs `python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" ...`. If `python3`
is not found, use `python`, then `py -3` (Windows). If it reports that Python
3.11+ is required, tell the user and stop.

## Step 1 - get the target

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" handoff new
```

Add `--name '<name>'` if the user named the workspace in their request.

Prints JSON: `date`, `workspace`, `source`, `path`, `store`.

`source` says where the name came from: `arg` (passed), `pinned` (set with
`/shift:name`), `wmux` / `cmux` / `tmux` / `zellij` (the terminal's own
workspace or session name), or `git` / `cwd` (a guess from the repo or folder
name). A guess still works; it is marked `(cwd)` in listings so it never reads
as a real workspace title. If the source is a guess and the user runs several
sessions in this directory, mention once that `/shift:name <tag>` pins a
stable name.

Pass `workspace` and `source` through to step 3 unchanged.

## Step 2 - write the handoff to `path`

Write the document with the Write tool to exactly the `path` from step 1. Keep
it tight: a fresh agent should be able to pick up the work from this document
plus the artifacts it references. Cover:

- **Goal** - what the user is trying to accomplish, in one or two sentences.
- **Current state** - what is done, in flight, and blocked. Exact file paths,
  branch names, and command outputs that matter.
- **Next steps** - the concrete actions the next session should take first.
- **Open questions** - decisions the user hasn't made yet.
- **Suggested skills** - skills the next session is likely to need, if any.
- **Gotchas** - environment quirks and things that nearly tripped this session.

Do not copy content that already lives in PRDs, plans, issues, commits, diffs or
files on disk; reference it by path or URL. The handoff is a pointer document.

Write for the next session in this workspace, not for a stranger mid-thought. If
the user passed an argument, treat it as the next session's focus and trim
anything unrelated to it.

## Step 3 - record it

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" handoff record --path '<path>' --workspace '<workspace>' --source '<source>' --summary '<one line>'
```

The summary is what the user scans later across many rows, so say what changed
or what is now blocked: `issue #5 shipped in .12, live-verified` earns its
place; `worked on the app` does not. One line.

With a database backend, `record` stores the document in the database and
deletes the local temp file; that is expected.

## Step 4 - tell the user

Two lines: where it was filed (the `store` from step 1) and the summary. They
are trying to stop working, not read a report.

## Notes

- Run the CLI rather than editing index files or tables by hand. It handles
  naming collisions, pipe escaping, and inserting rows without corrupting a
  file the user reads for months.
- If the user asks for several workspaces at once, run the whole sequence per
  workspace, each with `--name`.
- If `record` says the table was missing and was re-added, tell the user their
  hand edit was worked around.
