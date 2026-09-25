"""grimoire CLI: the only thing skills and hooks call. JSON on stdout for data,
one-line errors on stderr with exit code 1."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import pins
from .config import BACKENDS, RESOLVERS, config_path, load, render
from .errors import GrimoireError
from .fsutil import write_atomic
from .identity import Context, pane_key, resolve
from .reminders import DUE_STATUSES, hook_message, parse_date, parse_id, with_status
from .store import open_stores
from .store.base import find, label_for


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def today(args) -> date:
    return parse_date(args.today, "--today") if args.today else date.today()


def _stores(args):
    cfg = load(args.config)
    hs, rs = open_stores(cfg)
    opened = getattr(args, "_opened_stores", None)
    if opened is None:
        opened = args._opened_stores = []
    for s in (hs, rs):
        if s not in opened:
            opened.append(s)
    return cfg, hs, rs


# -- handoff -------------------------------------------------------------------
def cmd_handoff_new(args):
    cfg, hs, _ = _stores(args)
    ident = resolve(cfg.identity_order, args.name, Context())
    t = today(args).isoformat()
    emit({"date": t, "workspace": ident.name, "source": ident.source,
          "path": hs.new_target(t, ident.name), "store": hs.describe()})


def cmd_handoff_record(args):
    _, hs, _ = _stores(args)
    print(hs.record(args.path, args.workspace, args.source, args.summary))


def cmd_handoff_find(args):
    cfg, hs, _ = _stores(args)
    ident = resolve(cfg.identity_order, args.name, Context())
    newest, extra = find(hs, ident.name)
    path = None
    if newest:
        path = hs.open(newest) if newest.exists else newest.path
    emit({"workspace": ident.name, "source": ident.source, "found": bool(newest), "path": path,
          "date": newest.date if newest else None, "summary": newest.summary if newest else None,
          "exists": bool(newest and newest.exists), "machine": newest.machine if newest else None,
          "extra": [r.public() for r in extra], "rows": [r.public() for r in hs.rows()],
          "store": hs.describe()})


def cmd_handoff_list(args):
    _, hs, _ = _stores(args)
    emit([r.public() for r in hs.rows()])


def cmd_handoff_consume(args):
    _, hs, _ = _stores(args)
    for line in hs.consume(args.workspace):
        print(line)


# -- remind --------------------------------------------------------------------
def cmd_remind_add(args):
    cfg, _, rs = _stores(args)
    due = parse_date(args.due, "--due").isoformat()
    ident = resolve(cfg.identity_order, None, Context())
    t = today(args)
    r = rs.add(args.text, due, args.context, label_for(ident.name, ident.source), t.isoformat())
    if getattr(rs, "warning", None):
        print(f"warning: {rs.warning}", file=sys.stderr)
    emit(with_status(r, t, 3))


def cmd_remind_list(args):
    _, _, rs = _stores(args)
    t = today(args)
    emit([with_status(r, t, args.ahead) for r in rs.all()])


def cmd_remind_due(args):
    _, _, rs = _stores(args)
    t = today(args)
    items = [with_status(r, t, args.ahead) for r in rs.all()]
    emit({"today": t.isoformat(), "store": rs.describe(),
          "due": [i for i in items if i["status"] in DUE_STATUSES],
          "upcoming": [i for i in items if i["status"] == "upcoming"]})


def cmd_remind_hook(args):
    # Must never fail a session: a broken file, config or database prints nothing.
    try:
        _, _, rs = _stores(args)
        t = today(args)
        due = [i for i in (with_status(r, t, args.ahead) for r in rs.all()) if i["status"] in DUE_STATUSES]
        if due:
            emit({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": hook_message(rs.describe(), due)}})
    except Exception:
        pass
    return 0


def cmd_remind_snooze(args):
    _, _, rs = _stores(args)
    old, r = rs.update_due(parse_id(args.id), parse_date(args.due, "--due").isoformat())
    print(f"snoozed R{r.num} from {old} to {r.due}: {r.text}")


def cmd_remind_clear(args):
    _, _, rs = _stores(args)
    r = rs.remove(parse_id(args.id))
    print(f"cleared R{r.num}: {r.text}")


# -- name ----------------------------------------------------------------------
def cmd_name(args):
    cfg = load(args.config)
    ctx = Context()
    key = pane_key(ctx)
    if args.clear:
        emit({"key": key, "cleared": pins.clear_pin(key)})
        return
    if args.tag:
        pins.set_pin(key, args.tag.strip())
    ident = resolve(cfg.identity_order, None, ctx)
    emit({"workspace": ident.name, "source": ident.source, "key": key})


# -- config --------------------------------------------------------------------
def cmd_config_path(args):
    print(args.config or config_path())


def cmd_config_show(args):
    cfg = load(args.config)
    emit({"file": str(cfg.loaded_from) if cfg.loaded_from else None,
          "expected_at": str(args.config or config_path()), "backend": cfg.backend,
          "store": cfg.describe(), "identity_order": cfg.identity_order})


def cmd_config_check(args):
    cfg, hs, rs = _stores(args)
    print(f"ok - {cfg.describe()}: {len(hs.rows())} handoff(s), {len(rs.all())} reminder(s)")


def cmd_config_init(args):
    target = Path(args.config or config_path())
    if target.exists() and not args.force:
        raise GrimoireError(f"{target} already exists; pass --force to replace it")
    write_atomic(target, render(args.backend, files_dir=args.dir, sqlite_path=args.sqlite_path,
                                dsn_env=args.dsn_env))
    print(f"wrote {target}")


# -- parser --------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="grimoire")
    p.add_argument("--config", type=Path, help="config file (default: $AI_GRIMOIRE_CONFIG or ~/.config/ai-grimoire/config.toml)")
    p.add_argument("--today", help="override today's date (yyyy-MM-dd), for testing")
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("handoff").add_subparsers(dest="action", required=True)
    x = h.add_parser("new")
    x.add_argument("--name")
    x.set_defaults(func=cmd_handoff_new)
    x = h.add_parser("record")
    x.add_argument("--path", required=True)
    x.add_argument("--workspace", required=True)
    x.add_argument("--source", required=True, choices=RESOLVERS)
    x.add_argument("--summary", default="")
    x.set_defaults(func=cmd_handoff_record)
    x = h.add_parser("find")
    x.add_argument("--name")
    x.set_defaults(func=cmd_handoff_find)
    h.add_parser("list").set_defaults(func=cmd_handoff_list)
    x = h.add_parser("consume")
    x.add_argument("--workspace", required=True)
    x.set_defaults(func=cmd_handoff_consume)

    r = sub.add_parser("remind").add_subparsers(dest="action", required=True)
    x = r.add_parser("add")
    x.add_argument("--text", required=True)
    x.add_argument("--due", required=True)
    x.add_argument("--context", default="")
    x.set_defaults(func=cmd_remind_add)
    for name, func in (("list", cmd_remind_list), ("due", cmd_remind_due), ("hook", cmd_remind_hook)):
        x = r.add_parser(name)
        x.add_argument("--ahead", type=int, default=3)
        x.set_defaults(func=func)
    x = r.add_parser("snooze")
    x.add_argument("--id", required=True)
    x.add_argument("--due", required=True)
    x.set_defaults(func=cmd_remind_snooze)
    x = r.add_parser("clear")
    x.add_argument("--id", required=True)
    x.set_defaults(func=cmd_remind_clear)

    x = sub.add_parser("name")
    x.add_argument("tag", nargs="?")
    x.add_argument("--clear", action="store_true")
    x.set_defaults(func=cmd_name)

    c = sub.add_parser("config").add_subparsers(dest="action", required=True)
    c.add_parser("path").set_defaults(func=cmd_config_path)
    c.add_parser("show").set_defaults(func=cmd_config_show)
    c.add_parser("check").set_defaults(func=cmd_config_check)
    x = c.add_parser("init")
    x.add_argument("--backend", required=True, choices=BACKENDS)
    x.add_argument("--dir")
    x.add_argument("--sqlite-path")
    x.add_argument("--dsn-env")
    x.add_argument("--force", action="store_true")
    x.set_defaults(func=cmd_config_init)
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except GrimoireError as e:
        print(f"grimoire: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"grimoire: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        for s in getattr(args, "_opened_stores", None) or ():
            close = getattr(s, "close", None)
            if close:
                try:
                    close()
                except Exception:
                    pass
