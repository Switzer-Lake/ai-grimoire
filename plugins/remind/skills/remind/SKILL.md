---
name: remind
description: Set, list, snooze, clear, or work dated reminders so something you need to come back to is raised by the agent on the day it's due instead of being remembered all weekend. Use whenever the user says "remind me", "remind us", "set a reminder", "don't let me forget", "come back to this on/next ...", "what reminders do I have", "what's due", "snooze that", "push it to Thursday", "clear that reminder", "that one's done", or "work that reminder". Also use when a "REMINDERS DUE" block or /shift:start has raised a reminder and the user answers with work it, snooze, or clear.
argument-hint: "What to be reminded about and when, e.g. \"review #447 early next week\""
---

A reminder is a dated note to ourselves. Agents raise it on the day it comes
due:

- a **SessionStart hook** in this plugin injects a "REMINDERS DUE" block into
  each new session when something is due, and
- **`/shift:start`** (if installed) checks before resuming a handoff.

Reminders are not per workspace: any session can raise them. `from` only records
where one was set. Storage is shared with the `shift` plugin and configured by
`/shift:setup` (default: `~/grimoire/reminders.md`).

All mechanics go through the CLI; don't edit the store by hand from here. If
`python3` is not found use `python`, then `py -3`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" remind add --text '<what>' --due 2026-09-14 --context '<link>'
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" remind list
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" remind due
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" remind snooze --id R3 --due 2026-09-17
python3 "${CLAUDE_PLUGIN_ROOT}/lib/run.py" remind clear --id R3
```

## Setting one

1. **Turn the when into a real date yourself.** The CLI accepts only
   `yyyy-MM-dd`. Read today's date from the environment; don't guess it.
   Defaults: "next week" and "early next week" mean next Monday, "end of week"
   means this Friday, "in a few days" means today + 3. A date that lands on a
   weekend moves to the following Monday.
2. **Write it so a cold agent can act on it.** Say what to do, not just the
   topic: `Review #447 - check the fleet is on v1.5.18, then start the teardown`
   rather than `#447`. Put the issue, PR or doc link in `--context`.
3. Run `add`, then confirm in one line: ID, weekday + date, text. For example
   `Set R3 for Mon 2026-09-14: review #447.`

## When one is raised

Give each one line: ID, how overdue, text. Offer the three choices once and
don't act until the user picks:

- **work it** - start a background agent (the `Agent` tool) with a prompt built
  from the reminder text and its context, plus anything this session knows that
  the agent would need. Then return to the current task. Clear the reminder only
  when the user says the work is done.
- **snooze** - resolve the new date as above, then `snooze`.
- **clear** - `clear`. Nothing is archived, so if the reminder was the only
  record of something, say so first.

After the user answers, drop the subject. Raise a reminder once per session.

## Notes

- `list` and `due` return `status`: `overdue`, `due`, `upcoming`, `later`, or
  `unparseable-date` (a hand-edited date the CLI can't read). Raise the last as
  due and fix it with `snooze`.
- IDs are `R<n>` and never reused.
- `--today` (before the subcommand) overrides the date for testing; use it with
  `--config` pointing at a scratch config, never against real data.
