---
name: name
description: Show, pin, or clear the workspace name that /shift:end and /shift:start file handoffs under. Use when the user says "name this workspace", "call this session X", "tag this as X", "what workspace is this", "which name will the handoff use", or when /shift:end reported a guessed (cwd) name and the user wants a stable one. Useful in terminals without wmux, cmux, tmux or zellij, or when several sessions share one folder.
argument-hint: "A name to pin, --clear to remove the pin, or nothing to show the current name"
---

A pinned name overrides the terminal's own workspace name for this pane (or,
outside a multiplexer, this folder) on this machine. Every later `/shift:end`,
`/shift:start` and reminder "set from" uses it.

Run `python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" ...`; if `python3` is not found
use `python`, then `py -3`.

- **Show:** `python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" name`
- **Pin:** `python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" name '<name>'`
- **Clear:** `python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" name --clear`

Output is JSON with `workspace`, `source` and `key` (what the pin is attached
to: `cmux:...`, `wmux:...`, `tmux:%N`, `zellij:...`, or `cwd:<folder>`).

Reply in one line: the name now in effect and where it came from. If `key`
starts with `cwd:`, add that the pin applies to this folder, so other sessions
in the same folder share it.

Pins are per machine. On another machine, pin the same name there to pick up
the same handoffs from a shared database.
