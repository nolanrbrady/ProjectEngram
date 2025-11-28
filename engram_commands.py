"""
Command handlers for the pmem CLI.
"""
import argparse
import sys
from pathlib import Path
from typing import List

import engram_config as cfg
from engram_lock import FileLock
from engram_models import EngramEntry
from engram_recall import compute_scores, compute_match_score
from engram_storage import (
    add_backlinks,
    consolidate_entries,
    ensure_amygdala_pointer,
    ensure_engram,
    find_entry,
    get_engram_path,
    list_all_entries,
    mark_deprecated,
    maybe_remove_amygdala_pointer,
    move_entry,
    recalc_path,
    update_recall_stats,
    write_entry,
    sync_backlinks,
)
from engram_utils import base_strength, compute_capsule, generate_id, normalize_links, normalize_tags, now_ts

# Link suggestion tuning
SUGGESTION_THRESHOLD = 10
SUGGESTION_LIMIT = 3


def _nudge_agent_doc(agent_path: Path, protocol_path: Path):
    """
    If an agent-facing doc exists (e.g., AGENTS.md, CLAUDE.md), append a reminder to read AGENT_PROTOCOLS.md.
    If it does not exist, create it with the reminder.
    """
    note = (
        "You have persistent memories managed by `pmem` (hippocampus/cortex/amygdala).\n"
        f"Read {protocol_path.name} before continuing. Quick start: "
        '`pmem recall "startup"`, `pmem recall --latest`, '
        "`pmem remember <category> \"...\" [--tags --links --importance --retention]`, "
        "`pmem edit <ID> \"...\"`, critical uses `--require-confirm`.\n"
    )
    is_existing = agent_path.exists()
    if is_existing:
        text = agent_path.read_text(encoding="utf-8")
    else:
        text = f"# Agent Guide\n\n{note}"
    marker = protocol_path.name
    if is_existing and marker.lower() in text.lower():
        return
    nudge = f"\n\n> {note}See {marker} for full protocol.\n"
    agent_path.write_text(text.rstrip() + nudge, encoding="utf-8")


def display_entry(entry: EngramEntry):
    tags = ", ".join(entry.tags)
    region = entry.region.upper()
    ts = entry.updated or entry.created
    print(f"[{region} | {entry.category.upper()} | {ts} | ID: {entry.id}]")
    if entry.summary:
        print(f"Summary: {entry.summary}")
    print(f"Tags: {tags}")
    print(entry.content.strip())
    print("-" * 50)


def ensure_category(category: str):
    if category not in cfg.CATEGORIES:
        print(f"Error: category must be one of {cfg.CATEGORIES}")
        sys.exit(1)


def cmd_init(args):
    engram_path = ensure_engram()
    protocols_path = Path("AGENT_PROTOCOLS.md")
    instruction_content = """# AGENT MEMORY PROTOCOL

## SYSTEM OVERRIDE
You operate in a project with a **Persistent Memory Engram**. Use `pmem` for contextual knowledge.

## REGIONS
- hippocampus: fresh/volatile (default destination)
- cortex: stable references and high-importance items
- amygdala: critical mirrors (safety constraints)

## STARTUP MANDATES
- Run `pmem recall "startup"` immediately. If empty, create one with `pmem remember decisions "<rules>" --tags startup`.
- Refresh context with `pmem recall --latest` and explore tags via `pmem tags`.
- Narrow context with `pmem recall "<keywords>" --tag <tag>`; use `--sort time` when recency matters.

## WRITING / UPDATING
- Default: `pmem remember <category> "<content>" [--tags ...]` (lands in hippocampus).
- Long-lived/important: add `--retention reference` or `--importance high`; critical: `--critical --require-confirm` (mirrors to amygdala).
- Edit in place: `pmem edit <ID> "<updated text>" [--tags ... --links ... --importance ... --retention ... --region ...]`
- Promote hippocampus → cortex: `pmem promote <ID>` (sets retention to reference).
- Mark obsolete: `pmem deprecate <ID>`.
- Consolidate promotions: `pmem consolidate` (promotes hippocampus items meeting thresholds).

## RECALL
- `pmem recall "<query>" [--tag <tag>] [--sort relevance|time|tag] [--latest N]`
- Criticals (amygdala / importance=critical) are always pinned.
- Graph-aware: links expand related engrams; hippocampus is downweighted unless recent.

## AUDIT / TAGS
- `pmem audit` lists critical memories.
- `pmem tags` shows all tags.
"""
    protocols_path.write_text(instruction_content, encoding="utf-8")
    for name in ["AGENTS.md", "CLAUDE.md"]:
        _nudge_agent_doc(Path(name), protocols_path)
    print(f"Project Engram initialized at {engram_path}")
    print("Memory regions created: hippocampus, cortex, amygdala.")


def suggest_links(engram_path: Path, new_entry: EngramEntry):
    """
    Suggest related engrams based on lexical similarity to encourage explicit linking.
    """
    others = [e for e in list_all_entries(engram_path) if e.id != new_entry.id]
    if not others:
        return
    terms = (new_entry.content + " " + " ".join(new_entry.tags)).lower().split()
    scored = []
    for e in others:
        text = f"{e.title} {e.summary} {e.content} {' '.join(e.tags)}"
        score = compute_match_score(text, terms)
        if score >= SUGGESTION_THRESHOLD:
            scored.append((score, e))
    scored.sort(key=lambda t: t[0], reverse=True)
    scored = scored[:SUGGESTION_LIMIT]
    if not scored:
        return
    print("\nSuggested links (consider linking to):")
    for score, e in scored:
        print(f"- {e.id} [{e.category}] {e.title} (score {int(score)})")
    print()


def build_entry(category: str, content: str, tags, links, importance, retention, region, title, pin_until, expiry) -> EngramEntry:
    capsule = compute_capsule(content)
    created_ts = now_ts()
    return EngramEntry(
        id=generate_id(category),
        title=title or capsule[:80],
        category=category,
        region=region,
        importance=importance,
        retention=retention,
        tags=tags,
        links=links,
        strength=base_strength(region, importance, retention),
        strength_floor=0.6 if importance == "critical" else cfg.DEFAULT_STRENGTH_FLOOR,
        created=created_ts,
        updated=created_ts,
        recall_count=0,
        last_recalled=None,
        pin_until=pin_until,
        expiry=expiry,
        summary=capsule,
        deprecated=False,
        content=content,
    )


def cmd_remember(args):
    engram_path = get_engram_path()
    if not engram_path:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    category = args.category.lower()
    ensure_category(category)
    tags = normalize_tags(args.tags)
    links = normalize_links(args.links)
    importance = args.importance or cfg.DEFAULT_IMPORTANCE
    retention = args.retention or cfg.DEFAULT_RETENTION

    if args.critical:
        if not args.require_confirm:
            print("Refusing to store CRITICAL memory without --require-confirm.")
            sys.exit(1)
        importance = "critical"
        retention = "reference"
        if "critical" not in [t.lower() for t in tags]:
            tags.append("critical")

    region = args.region or ("cortex" if importance in ["critical", "high"] or retention == "reference" else "hippocampus")

    entry = build_entry(
        category=category,
        content=args.content,
        tags=tags,
        links=links,
        importance=importance,
        retention=retention,
        region=region,
        title=args.title,
        pin_until=args.pin_until,
        expiry=args.expiry,
    )

    with FileLock(engram_path / cfg.LOCK_FILE):
        target_path = engram_path / region / category / f"{entry.id}.md"
        write_entry(entry, target_path=target_path)
        add_backlinks(engram_path, entry, links)
        if importance == "critical":
            ensure_amygdala_pointer(engram_path, entry)

    print(f"Memory stored as {entry.id} in {region}/{category}.")
    suggest_links(engram_path, entry)


def cmd_promote(args):
    engram_path = get_engram_path()
    if not engram_path:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    entry = find_entry(engram_path, args.id)
    if not entry:
        print(f"Memory ID {args.id} not found.")
        return

    if entry.region == "cortex":
        print(f"Memory {args.id} already in cortex.")
        return

    entry.region = "cortex"
    entry.retention = "reference"
    entry.strength = max(entry.strength, 0.9)
    entry.updated = now_ts()

    with FileLock(engram_path / cfg.LOCK_FILE):
        move_entry(engram_path, entry, "cortex")
    print(f"Memory {args.id} promoted to cortex.")


def cmd_edit(args):
    engram_path = get_engram_path()
    if not engram_path:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    entry = find_entry(engram_path, args.id)
    if not entry:
        print(f"Memory ID {args.id} not found.")
        return
    if entry.deprecated:
        print(f"Memory {args.id} is deprecated; create a new entry instead.")
        return
    old_path = entry.path
    old_links = list(entry.links)

    if args.tags is not None:
        entry.tags = normalize_tags(args.tags)
    if args.links is not None:
        entry.links = normalize_links(args.links)
    if args.importance:
        entry.importance = args.importance
    if args.retention:
        entry.retention = args.retention
    if args.region:
        entry.region = args.region

    entry.content = args.content
    entry.summary = compute_capsule(args.content)
    entry.updated = now_ts()
    entry.strength = base_strength(entry.region, entry.importance, entry.retention)

    with FileLock(engram_path / cfg.LOCK_FILE):
        target = recalc_path(engram_path, entry)
        write_entry(entry, target_path=target)
        if old_path and Path(old_path) != target and Path(old_path).exists():
            Path(old_path).unlink()
        sync_backlinks(engram_path, entry, old_links)
        if entry.importance == "critical":
            ensure_amygdala_pointer(engram_path, entry)
        else:
            maybe_remove_amygdala_pointer(engram_path, entry.id)
    print(f"Memory {args.id} updated.")


def cmd_deprecate(args):
    engram_path = get_engram_path()
    if not engram_path:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    entry = find_entry(engram_path, args.id)
    if not entry:
        print(f"Memory ID {args.id} not found.")
        return

    with FileLock(engram_path / cfg.LOCK_FILE):
        mark_deprecated(engram_path, entry)
    print(f"Memory {args.id} marked as deprecated.")


def cmd_recall(args):
    engram_path = get_engram_path()
    if not engram_path:
        print("Error: Engram not found.")
        sys.exit(1)

    if not args.query and not args.tag and not args.latest:
        print("Error: Provide a search query, --tag, or --latest.")
        sys.exit(1)

    entries = list_all_entries(engram_path)
    if not entries:
        print("No memories found.")
        return

    tag_filter = args.tag.lower() if args.tag else None
    query_terms = args.query.lower().split() if args.query else []

    print(f"--- SEARCHING ENGRAM FOR: '{args.query or ''}' ---")

    if args.latest:
        latest_count = args.latest if isinstance(args.latest, int) else 5
        filtered = []
        for e in entries:
            tags = [t.lower() for t in e.tags]
            if tag_filter and tag_filter not in tags:
                continue
            filtered.append(e)
        filtered.sort(key=lambda e: e.updated or e.created, reverse=True)
        criticals = [e for e in filtered if e.importance == "critical" or "critical" in [t.lower() for t in e.tags]]
        non_critical = [e for e in filtered if e not in criticals]
        for e in criticals[:latest_count]:
            display_entry(e)
        for e in non_critical[:latest_count]:
            display_entry(e)
        update_recall_stats(engram_path, criticals[:latest_count] + non_critical[:latest_count])
        return

    criticals, candidates = compute_scores(entries, query_terms, tag_filter)
    seen = set()
    if criticals:
        print("\n" + "!" * 40)
        print("!!! CRITICAL PROJECT CONSTRAINTS !!!")
        print("!" * 40)
        for c in criticals:
            display_entry(c)
            seen.add(c.id)
        print("!" * 40 + "\n")

    if args.sort == "time":
        hits = sorted(candidates, key=lambda e: e.updated or e.created, reverse=True)
    elif args.sort == "tag":
        hits = sorted(candidates, key=lambda e: (e.tags[:1] or ["zzz"])[0].lower())
    else:
        hits = candidates

    hits = [h for h in hits if h.id not in seen]

    if not hits and not criticals:
        print("No memories found.")
        return

    for h in hits[: max(10, len(criticals))]:
        display_entry(h)
        seen.add(h.id)

    update_recall_stats(engram_path, [h for h in candidates if h.id in seen])


def cmd_tags(args):
    engram_path = get_engram_path()
    if not engram_path:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    entries = list_all_entries(engram_path, include_deprecated=True)
    all_tags = set()
    for e in entries:
        for t in e.tags:
            all_tags.add(t)

    print("--- KNOWN TAGS ---")
    print(", ".join(sorted(all_tags)))


def cmd_audit(args):
    engram_path = get_engram_path()
    if not engram_path:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    entries = list_all_entries(engram_path)
    criticals = [e for e in entries if e.importance == "critical" or "critical" in [t.lower() for t in e.tags]]
    if not criticals:
        print("No critical memories saved.")
        return
    criticals.sort(key=lambda e: e.updated or e.created, reverse=True)
    print("--- CRITICAL MEMORIES AUDIT ---")
    for c in criticals:
        display_entry(c)


def cmd_consolidate(args):
    engram_path = get_engram_path()
    if not engram_path:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    entries = list_all_entries(engram_path)
    with FileLock(engram_path / cfg.LOCK_FILE):
        promoted = consolidate_entries(engram_path, entries)

    if not promoted:
        print("No hippocampus entries met promotion thresholds.")
        return

    for p in promoted:
        print(f"Promoted {p.id} to cortex (retention=reference).")
