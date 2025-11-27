#!/usr/bin/env python3
"""
Thin CLI entrypoint for Project Engram.

Business logic lives in dedicated modules:
- engram_config: constants
- engram_utils: helpers and strength/capsule/id generation
- engram_models: EngramEntry dataclass + serialization
- engram_storage: filesystem interactions
- engram_recall: scoring/ranking logic
- engram_commands: CLI command handlers
"""
import argparse

import engram_commands as cmd
import engram_config as cfg
from engram_lock import FileLock
from engram_storage import ensure_engram, find_entry, get_engram_path, list_all_entries
from engram_utils import now_ts
from engram_commands import (
    cmd_init,
    cmd_remember,
    cmd_recall,
    cmd_deprecate,
    cmd_edit,
    cmd_tags,
    cmd_audit,
    cmd_promote,
    cmd_consolidate,
)

# Re-export common constants for convenience/tests
LOCK_FILE = cfg.LOCK_FILE
CATEGORIES = cfg.CATEGORIES


def build_parser():
    parser = argparse.ArgumentParser(description="Project Engram: Agent Memory Bridge")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init")

    mem = subparsers.add_parser("remember")
    mem.add_argument("category")
    mem.add_argument("content")
    mem.add_argument("--title", help="Optional title for the engram")
    mem.add_argument("--tags", help="Comma separated tags")
    mem.add_argument("--links", help="Comma separated list of related engram IDs")
    mem.add_argument("--importance", choices=["critical", "high", "normal", "low"], help="How important this is")
    mem.add_argument("--retention", choices=["reference", "ephemeral", "log", "deprecated"], help="Retention policy")
    mem.add_argument("--region", choices=["hippocampus", "cortex"], help="Force region placement")
    mem.add_argument("--critical", action="store_true", help="Mark as critical (mirrors to amygdala)")
    mem.add_argument("--require-confirm", action="store_true", help="Required when using --critical")
    mem.add_argument("--pin-until", help="Pin until ISO date")
    mem.add_argument("--expiry", help="Optional expiry ISO date")

    rec = subparsers.add_parser("recall")
    rec.add_argument("query", nargs="?", help="Search keywords")
    rec.add_argument("--tag", help="Filter by tag (case-insensitive)")
    rec.add_argument("--latest", nargs="?", const=5, type=int, help="Show the newest N memories (default 5)")
    rec.add_argument("--sort", choices=["relevance", "time", "tag"], default="relevance", help="Sorting for recall results")

    subparsers.add_parser("tags")

    dep = subparsers.add_parser("deprecate")
    dep.add_argument("id")

    edit = subparsers.add_parser("edit")
    edit.add_argument("id")
    edit.add_argument("content")
    edit.add_argument("--tags", help="Replace tags with a comma separated list")
    edit.add_argument("--links", help="Replace links with a comma separated list")
    edit.add_argument("--importance", choices=["critical", "high", "normal", "low"])
    edit.add_argument("--retention", choices=["reference", "ephemeral", "log", "deprecated"])
    edit.add_argument("--region", choices=["hippocampus", "cortex"])

    subparsers.add_parser("audit")
    subparsers.add_parser("status")

    promo = subparsers.add_parser("promote")
    promo.add_argument("id")

    subparsers.add_parser("consolidate")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        cmd.cmd_init(args)
    elif args.command == "remember":
        cmd.cmd_remember(args)
    elif args.command == "recall":
        cmd.cmd_recall(args)
    elif args.command == "deprecate":
        cmd.cmd_deprecate(args)
    elif args.command == "edit":
        cmd.cmd_edit(args)
    elif args.command == "tags":
        cmd.cmd_tags(args)
    elif args.command == "audit":
        cmd.cmd_audit(args)
    elif args.command == "status":
        print("Engram Active.")
    elif args.command == "promote":
        cmd.cmd_promote(args)
    elif args.command == "consolidate":
        cmd.cmd_consolidate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
