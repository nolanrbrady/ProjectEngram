#!/usr/bin/env python3
import os
import sys
import re
import argparse
import datetime
import difflib
import hashlib
import time
from pathlib import Path

# --- Configuration ---
ENGRAM_DIR = ".engram"
LOCK_FILE = "engram.lock"
MEMORY_FILES = {
    "decisions": "decisions.md",   # Architecture choices
    "patterns": "patterns.md",     # Coding standards
    "context": "context.md",       # Team info, assumptions
    "journal": "journal.md"        # Chronological log
}

# --- File Locking for Concurrency Safety ---
class FileLock:
    def __init__(self, lock_path, timeout=5):
        self.lock_path = lock_path
        self.timeout = timeout

    def __enter__(self):
        start_time = time.time()
        while os.path.exists(self.lock_path):
            if time.time() - start_time > self.timeout:
                try:
                    os.remove(self.lock_path)
                except OSError:
                    pass
                break
            time.sleep(0.1)
        open(self.lock_path, 'w').close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

# --- Core Logic ---

def get_engram_path():
    """Finds the .engram directory walking up the tree."""
    cwd = Path(os.getcwd())
    for part in [cwd] + list(cwd.parents):
        path = part / ENGRAM_DIR
        if path.exists():
            return path
    return None

def ensure_engram():
    """Ensures local .engram exists (for init)."""
    path = Path(os.getcwd()) / ENGRAM_DIR
    if not path.exists():
        os.makedirs(path)
        print(f"Initialized Project Engram at {path}")
    return path

def generate_id(content):
    return hashlib.md5(content.encode('utf-8')).hexdigest()[:6]

def format_entry(content, tags=None, critical=False, mem_id=None, timestamp=None, include_leading_newline=True):
    """Render a memory entry with metadata."""
    timestamp = timestamp or datetime.datetime.now().isoformat(timespec='minutes')
    mem_id = mem_id or generate_id(content + timestamp)

    tag_list = tags[:] if tags else ["general"]
    normalized = [t.lower() for t in tag_list]
    if critical and "critical" not in normalized:
        tag_list.append("CRITICAL")

    tag_str = f"Tags: {', '.join(tag_list)}"
    prefix = "\n" if include_leading_newline else ""
    return f"{prefix}## [{timestamp}] {{{mem_id}}} {tag_str}\n{content}\n"

def parse_entries(content):
    pattern = r'\n## \[(.*?)\] \{(.*?)\} (.*?)\n'
    raw_entries = re.split(pattern, content)
    parsed = []
    if len(raw_entries) < 4: return []

    for i in range(1, len(raw_entries), 4):
        date_str = raw_entries[i]
        try:
            dt = datetime.datetime.fromisoformat(date_str)
        except ValueError:
            dt = None
        tags_line = raw_entries[i+2]
        tags_list = list_tags(tags_line)
        parsed.append({
            'date': date_str,
            'dt': dt,
            'id': raw_entries[i+1],
            'tags': tags_line,
            'tags_list': tags_list,
            'content': raw_entries[i+3].strip(),
            'full_match': f"## [{raw_entries[i]}] {{{raw_entries[i+1]}}} {raw_entries[i+2]}\n{raw_entries[i+3]}\n"
        })
    return parsed

def list_tags(tag_field):
    tag_str = tag_field.replace("Tags:", "")
    return [t.strip() for t in tag_str.split(",") if t.strip()]

# --- Helpers ---

def normalize_tags(tags):
    return [t.strip() for t in tags if t.strip()]

def is_critical_tag(tag_list):
    return any(t.lower() == "critical" for t in tag_list)

def load_entries(engram_path, include_deprecated=False):
    entries = []
    for category, filename in MEMORY_FILES.items():
        path = engram_path / filename
        if not path.exists():
            continue
        with open(path, "r") as f:
            file_entries = parse_entries(f.read())
        for entry in file_entries:
            entry["category"] = category
            entry["is_critical"] = is_critical_tag(entry.get("tags_list", []))
            entry["is_deprecated"] = "[DEPRECATED]" in entry["full_match"]
            if not include_deprecated and entry["is_deprecated"]:
                continue
            entries.append(entry)
    return entries

def entry_timestamp(entry):
    return entry.get("dt") or datetime.datetime.min

def compute_match_score(text, terms):
    if not terms:
        return 0
    score = 0
    lowered = text.lower()
    words = re.findall(r"[a-z0-9]+", lowered)
    for term in terms:
        if not term:
            continue
        if term in lowered:
            score += 10
            continue
        best_ratio = 0
        for w in words:
            ratio = difflib.SequenceMatcher(None, term, w).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
        score += best_ratio * 5
    return score

def display_entry(entry):
    tag_display = ", ".join(entry.get("tags_list", []))
    print(f"[{entry['category'].upper()} | {entry.get('date', 'unknown')} | ID: {entry['id']}]")
    print(f"Tags: {tag_display}")
    print(entry["content"])
    print("-" * 40)

# --- Commands ---

def cmd_init(args):
    path = ensure_engram()
    for key, filename in MEMORY_FILES.items():
        file_path = path / filename
        if not file_path.exists():
            with open(file_path, "w") as f:
                f.write(f"# Project {key.capitalize()}\n\n")

    instruction_content = """# AGENT MEMORY PROTOCOL

## SYSTEM OVERRIDE
You are an intelligent agent operating in a project with a **Persistent Memory Engram**.
You MUST use the `pmem` CLI tool to persist knowledge.

## STARTUP MANDATES
1. Run `pmem recall "startup"` on arrival. If nothing is returned, create one via `pmem remember decisions "<rules>" --tags startup`.
2. Refresh context with `pmem recall --latest` and `pmem tags` before new work.
3. Narrow context with `pmem recall "<keywords>" --tag <tag>` and `pmem recall --sort time` when needed.

## UPDATES
- Amend memories in-place with `pmem edit <ID> "<updated text>" [--tags ...]` instead of duplicating and deprecating.
- Use `pmem remember ... --critical --require-confirm` ONLY for safety constraints; audit with `pmem audit`.
- Mark outdated memories with `pmem deprecate <ID>`.

## COMMANDS
- `pmem recall "<query>" [--tag <tag>] [--sort relevance|time|tag] [--latest N]`
- `pmem recall --latest` : show newest notes (honors --tag).
- `pmem remember <category> "<content>" [--tags ...] [--critical --require-confirm]`
- `pmem edit <id> "<content>" [--tags ...]`
- `pmem audit` : list all critical memories quickly.
- `pmem tags` : list known tags.
- `pmem deprecate <id>` : mark obsolete.
"""
    with open("AGENT_PROTOCOLS.md", "w") as f:
        f.write(instruction_content)
    
    print("Project Engram initialized.")
    print("\n[IMPORTANT] Memory is stored in .engram/")
    print("Ensure you run: git add .engram && git commit -m 'Init memory'")

def cmd_remember(args):
    engram = get_engram_path()
    if not engram:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    if args.critical and not args.require_confirm:
        print("Refusing to store CRITICAL memory without --require-confirm.")
        sys.exit(1)

    category = args.category.lower()
    if category not in MEMORY_FILES:
        print(f"Error: Category must be one of {list(MEMORY_FILES.keys())}")
        sys.exit(1)

    # Use lock for writing
    with FileLock(engram / LOCK_FILE):
        target_file = engram / MEMORY_FILES[category]
        tags = normalize_tags(args.tags.split(',')) if args.tags else []
        entry = format_entry(args.content, tags=tags, critical=args.critical)
        
        with open(target_file, "a") as f:
            f.write(entry)
        
        # Log to journal
        j_entry = format_entry(f"Updated {category} ({'CRITICAL' if args.critical else 'Normal'}): {args.content[:40]}...", tags=["auto-log"])
        with open(engram / MEMORY_FILES['journal'], "a") as f:
            f.write(j_entry)

    print(f"Memory stored in {category}.")

def cmd_deprecate(args):
    engram = get_engram_path()
    if not engram:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    mem_id = args.id

    with FileLock(engram / LOCK_FILE):
        for key, filename in MEMORY_FILES.items():
            path = engram / filename
            if not path.exists():
                continue

            with open(path, "r") as f:
                content = f.read()
                entries = parse_entries(content)

            for entry in entries:
                if entry["id"] != mem_id:
                    continue

                if "[DEPRECATED]" in entry["full_match"]:
                    print(f"Memory {mem_id} already deprecated.")
                    return

                deprecated_entry = entry["full_match"].replace(
                    f"{{{mem_id}}}", f"{{{mem_id}}} [DEPRECATED]", 1
                )
                new_content = content.replace(entry["full_match"], deprecated_entry, 1)
                with open(path, "w") as f:
                    f.write(new_content)
                print(f"Memory {mem_id} deprecated.")
                return

    print(f"Memory ID {mem_id} not found.")

def cmd_edit(args):
    engram = get_engram_path()
    if not engram:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    mem_id = args.id
    new_tags = normalize_tags(args.tags.split(',')) if args.tags else None

    with FileLock(engram / LOCK_FILE):
        for key, filename in MEMORY_FILES.items():
            path = engram / filename
            if not path.exists():
                continue

            with open(path, "r") as f:
                content = f.read()
                entries = parse_entries(content)

            for entry in entries:
                if entry["id"] != mem_id:
                    continue
                if "[DEPRECATED]" in entry["full_match"]:
                    print(f"Memory {mem_id} is deprecated; create a new entry instead.")
                    return

                tags_to_use = new_tags if new_tags is not None else entry.get("tags_list", list_tags(entry["tags"]))
                if not tags_to_use:
                    tags_to_use = ["general"]
                critical_flag = is_critical_tag(tags_to_use)

                updated_entry = format_entry(
                    args.content,
                    tags=tags_to_use,
                    critical=critical_flag,
                    mem_id=mem_id,
                    include_leading_newline=False,
                )
                new_content = content.replace(entry["full_match"], updated_entry, 1)
                with open(path, "w") as f:
                    f.write(new_content)

                log_entry = format_entry(
                    f"Edited {key} ({mem_id}): {args.content[:60]}...",
                    tags=["auto-log"]
                )
                with open(engram / MEMORY_FILES['journal'], "a") as jf:
                    jf.write(log_entry)

                print(f"Memory {mem_id} updated in {key}.")
                return

    print(f"Memory ID {mem_id} not found.")

def cmd_recall(args):
    engram = get_engram_path()
    if not engram:
        print("Error: Engram not found.")
        sys.exit(1)

    if not args.query and not args.tag and not args.latest:
        print("Error: Provide a search query, --tag, or --latest.")
        sys.exit(1)

    query_terms = args.query.lower().split() if args.query else []
    tag_filter = args.tag.lower() if args.tag else None
    latest_count = args.latest
    sort_mode = args.sort or "relevance"

    entries = load_entries(engram)
    hits = []
    critical_hits = []

    tag_label = f" | tag: {args.tag}" if args.tag else ""
    latest_label = f" | latest: {latest_count}" if latest_count else ""
    print(f"--- SEARCHING ENGRAM FOR: '{args.query or ''}'{tag_label}{latest_label} ---")

    now = datetime.datetime.now()
    for entry in entries:
        tags_lower = [t.lower() for t in entry.get("tags_list", [])]
        if tag_filter and tag_filter not in tags_lower:
            continue

        if entry["is_critical"]:
            critical_hits.append(entry)

        text_to_search = f"{entry['content']} {' '.join(entry.get('tags_list', []))}"
        recency_bonus = 0
        try:
            age = (now - entry_timestamp(entry)).days
            recency_bonus = max(0, 5 - age)
        except Exception:
            recency_bonus = 0

        if latest_count:
            if query_terms:
                score = compute_match_score(text_to_search, query_terms)
                if score <= 0:
                    continue
                entry["score"] = score + recency_bonus
            else:
                entry["score"] = recency_bonus
            hits.append(entry)
            continue

        score = compute_match_score(text_to_search, query_terms)
        entry["score"] = score + recency_bonus

        if score > 0 or tag_filter:
            hits.append(entry)

    critical_ids = {c["id"] for c in critical_hits}

    if latest_count:
        hits.sort(key=lambda e: entry_timestamp(e), reverse=True)
        hits = hits[:latest_count]
    elif sort_mode == "time":
        hits.sort(key=lambda e: entry_timestamp(e), reverse=True)
    elif sort_mode == "tag":
        hits.sort(key=lambda e: entry_timestamp(e), reverse=True)
        hits.sort(key=lambda e: e.get("tags_list", [""])[0].lower())
    else:
        hits.sort(key=lambda e: e.get("score", 0), reverse=True)

    critical_hits.sort(key=lambda e: entry_timestamp(e), reverse=True)

    if critical_hits:
        print("\n" + "!"*40)
        print("!!! CRITICAL PROJECT CONSTRAINTS !!!")
        print("!"*40)
        for data in critical_hits:
            display_entry(data)
        print("!"*40 + "\n")

    filtered_hits = [h for h in hits if h["id"] not in critical_ids]

    if not filtered_hits and not critical_hits:
        if args.query and "startup" in args.query.lower():
            print("No startup memory found. Create one with `pmem remember decisions \"<constraints>\" --tags startup`.")
            general_entries = [
                e for e in entries
                if "general" in [t.lower() for t in e.get("tags_list", [])]
            ]
            if general_entries:
                print("\nShowing recent 'general' memories instead:")
                general_entries.sort(key=lambda e: entry_timestamp(e), reverse=True)
                for e in general_entries[:3]:
                    display_entry(e)
            else:
                print("No general memories available either.")
        else:
            print("No memories found.")
    else:
        for data in filtered_hits:
            display_entry(data)

def cmd_tags(args):
    engram = get_engram_path()
    if not engram:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    all_tags = set()
    for key, filename in MEMORY_FILES.items():
        path = engram / filename
        if path.exists():
            entries = parse_entries(open(path).read())
            for e in entries:
                for t in list_tags(e['tags']):
                    all_tags.add(t)
    
    print("--- KNOWN TAGS ---")
    print(", ".join(sorted(list(all_tags))))

def cmd_audit(args):
    engram = get_engram_path()
    if not engram:
        print("Error: Engram not found. Run 'pmem init'.")
        sys.exit(1)

    entries = load_entries(engram)
    critical_entries = [e for e in entries if e["is_critical"]]
    if not critical_entries:
        print("No critical memories saved.")
        return

    critical_entries.sort(key=lambda e: entry_timestamp(e), reverse=True)
    print("--- CRITICAL MEMORIES AUDIT ---")
    for entry in critical_entries:
        display_entry(entry)

def main():
    parser = argparse.ArgumentParser(description="Project Engram: Agent Memory Bridge")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init")
    
    mem = subparsers.add_parser("remember")
    mem.add_argument("category")
    mem.add_argument("content")
    mem.add_argument("--tags", help="Comma separated tags")
    mem.add_argument("--critical", action="store_true", help="Always show this memory")
    mem.add_argument("--require-confirm", action="store_true", help="Required when using --critical")

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

    subparsers.add_parser("audit")

    subparsers.add_parser("status")

    args = parser.parse_args()

    if args.command == "init": cmd_init(args)
    elif args.command == "remember": cmd_remember(args)
    elif args.command == "recall": cmd_recall(args)
    elif args.command == "deprecate": cmd_deprecate(args)
    elif args.command == "edit": cmd_edit(args)
    elif args.command == "tags": cmd_tags(args)
    elif args.command == "audit": cmd_audit(args)
    elif args.command == "status": print("Engram Active.")
    else: parser.print_help()

if __name__ == "__main__":
    main()
