"""`wf` command: link and check GitHub repos and boards, and run the workflow shell."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wf import config as cfgmod
from wf import graph
from wf.integrations import GitHubClient, JiraClient


def _cfg_path(args) -> Path:
    return Path(args.config) if args.config else cfgmod.default_path()


def cmd_link_repo(args) -> int:
    path = _cfg_path(args)
    c = cfgmod.load(path)
    if c.add_repo(args.full_name):
        cfgmod.save(c, path)
        print(f"linked repo {args.full_name}")
    else:
        print(f"repo {args.full_name} already linked")
    return 0


def cmd_link_board(args) -> int:
    path = _cfg_path(args)
    c = cfgmod.load(path)
    if c.add_board(args.provider, args.ref, args.label or ""):
        cfgmod.save(c, path)
        print(f"linked {args.provider} board {args.ref}")
    else:
        print(f"{args.provider} board {args.ref} already linked")
    return 0


def cmd_unlink(args) -> int:
    path = _cfg_path(args)
    c = cfgmod.load(path)
    if args.kind == "repo":
        removed = c.remove_repo(args.ref)
    else:
        removed = c.remove_board(args.kind, args.ref)
    if removed:
        cfgmod.save(c, path)
        print(f"unlinked {args.kind} {args.ref}")
        return 0
    print(f"{args.kind} {args.ref} is not linked", file=sys.stderr)
    return 1


def cmd_list(args) -> int:
    c = cfgmod.load(_cfg_path(args))
    if not c.repos and not c.boards:
        print("nothing linked yet")
        return 0
    for r in c.repos:
        print(f"repo   {r.full_name}")
    for b in c.boards:
        label = f"  ({b.label})" if b.label else ""
        print(f"board  {b.provider:<6} {b.ref}{label}")
    return 0


def cmd_check(args) -> int:
    c = cfgmod.load(_cfg_path(args))
    gh = GitHubClient()
    jira = JiraClient()
    failures = 0
    for r in c.repos:
        res = gh.check_repo(r)
        failures += not res.ok
        print(f"{'ok  ' if res.ok else 'FAIL'} repo  {r.full_name}: {res.detail}")
    for b in c.boards:
        res = gh.check_board(b) if b.provider == "github" else jira.check_board(b)
        failures += not res.ok
        print(f"{'ok  ' if res.ok else 'FAIL'} board {b.provider} {b.ref}: {res.detail}")
    if not c.repos and not c.boards:
        print("nothing linked to check")
    return 1 if failures else 0


def cmd_run(args) -> int:
    out = graph.start(Path(args.db), args.thread, args.request)
    _print_run(out)
    return 0


def cmd_usage(args) -> int:
    import os
    from wf import usage

    ledger = usage.UsageLedger(Path(args.db or os.environ.get("WF_DB", "wf.sqlite")))
    print(usage.format_audit(ledger.audit(), ledger.largest_calls()))
    return 0


def cmd_route(args) -> int:
    from wf import orchestrator

    labels = {"hotfix"} if args.hotfix else set()
    d = orchestrator.route(args.status, labels)
    print(f"action: {d.action}\nowner:  {d.owner or '-'}\nwhy:    {d.reason}")
    return 0


def cmd_kill(args) -> int:
    import os
    from wf import orchestrator

    store = orchestrator.LifecycleStore(Path(args.db or os.environ.get("WF_DB", "wf.sqlite")))
    if args.state == "status":
        print("kill switch is", "ON" if store.killed() else "off")
    else:
        store.set_kill(args.state == "on")
        print("kill switch is now", args.state)
    return 0


def cmd_poll(args) -> int:
    import os
    from wf.integrations import JiraClient
    from wf.pipeline import Pipeline

    jql = os.environ.get("WF_POLL_JQL", "updated >= -2h ORDER BY updated DESC")
    jira = JiraClient()
    pipe = Pipeline(
        Path(args.db or os.environ.get("WF_DB", "wf.sqlite")),
        fetch_changelog=jira.get_issue_changelog,
        search_keys=lambda: jira.search_keys(jql),
    )
    decisions = pipe.poll()
    if not decisions:
        print("poll skipped (webhooks recent) or nothing new")
    for d in decisions:
        print(f"{d.action:<9} {d.owner or '-':<14} {d.reason}")
    return 0


def cmd_resume(args) -> int:
    out = graph.resume(Path(args.db), args.thread, approved=args.approve)
    _print_run(out)
    return 0


def _print_run(out: dict) -> None:
    print("steps:", " -> ".join(out["steps"]))
    print("status:", out["status"])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wf", description="Agentic workflow shell")
    p.add_argument("--config", help="path to workflow.json (default: $WF_CONFIG or ./workflow.json)")
    sub = p.add_subparsers(dest="cmd", required=True)

    link = sub.add_parser("link", help="link a repo or board")
    lsub = link.add_subparsers(dest="what", required=True)
    lr = lsub.add_parser("repo", help="link a GitHub repo")
    lr.add_argument("full_name", metavar="OWNER/NAME")
    lr.set_defaults(func=cmd_link_repo)
    lb = lsub.add_parser("board", help="link a Jira board or GitHub Project")
    lb.add_argument("provider", choices=cfgmod.BOARD_PROVIDERS)
    lb.add_argument("ref", help="jira: numeric board id; github: OWNER/NUMBER")
    lb.add_argument("--label", help="a name to show in `wf list`")
    lb.set_defaults(func=cmd_link_board)

    un = sub.add_parser("unlink", help="remove a linked repo or board")
    un.add_argument("kind", choices=["repo", *cfgmod.BOARD_PROVIDERS])
    un.add_argument("ref")
    un.set_defaults(func=cmd_unlink)

    ls = sub.add_parser("list", help="show linked repos and boards")
    ls.set_defaults(func=cmd_list)

    ck = sub.add_parser("check", help="verify every link resolves with current credentials")
    ck.set_defaults(func=cmd_check)

    run = sub.add_parser("run", help="start a workflow run (shell stages only)")
    run.add_argument("request")
    run.add_argument("--thread", required=True, help="run id, reused by `wf resume`")
    run.add_argument("--db", default="runs.sqlite")
    run.set_defaults(func=cmd_run)

    us = sub.add_parser("usage", help="audit token use per agent from the local ledger")
    us.add_argument("--db", default=None, help="SQLite file (default: $WF_DB or ./wf.sqlite)")
    us.set_defaults(func=cmd_usage)

    rt = sub.add_parser("route", help="show which agent owns a ticket status")
    rt.add_argument("status")
    rt.add_argument("--hotfix", action="store_true", help="treat the ticket as carrying the hotfix label")
    rt.set_defaults(func=cmd_route)

    kl = sub.add_parser("kill", help="kill switch: stop all agent dispatch")
    kl.add_argument("state", choices=["on", "off", "status"])
    kl.add_argument("--db", default=None)
    kl.set_defaults(func=cmd_kill)

    pl = sub.add_parser("poll", help="hourly fallback: pull recent Jira changes and route them")
    pl.add_argument("--db", default=None)
    pl.set_defaults(func=cmd_poll)

    res = sub.add_parser("resume", help="answer the approval gate for a run")
    res.add_argument("thread")
    res.add_argument("--db", default="runs.sqlite")
    g = res.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true")
    g.add_argument("--reject", dest="approve", action="store_false")
    res.set_defaults(func=cmd_resume)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except cfgmod.ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
