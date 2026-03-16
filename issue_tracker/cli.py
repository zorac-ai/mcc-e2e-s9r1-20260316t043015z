from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .notifier import EmailNotifier
from .store import IssueStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple issue tracker")
    parser.add_argument(
        "--db",
        default=os.environ.get("ISSUE_TRACKER_DB", "issues.json"),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Create a new issue")
    add_parser.add_argument("title")

    list_parser = subparsers.add_parser("list", help="List issues")
    list_parser.add_argument("--status", choices=("open", "closed"))

    close_parser = subparsers.add_parser("close", help="Close an issue")
    close_parser.add_argument("issue_id", type=int)

    # MCC-LIVE-E2E: parser anchor

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = IssueStore(Path(args.db))
    notifier = EmailNotifier.from_env()

    if args.command == "add":
        result = store.add(args.title)
        if notifier is not None:
            try:
                notifier.notify_created(result)
            except Exception:
                print("Warning: failed to send notification", file=sys.stderr)
    elif args.command == "list":
        result = store.list(status=args.status)
    elif args.command == "close":
        result = store.close(args.issue_id)
        if notifier is not None:
            try:
                notifier.notify_closed(result)
            except Exception:
                print("Warning: failed to send notification", file=sys.stderr)
    # MCC-LIVE-E2E: command anchor
    else:
        parser.error(f"unknown command: {args.command}")
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
