"""
Storage and filesystem helpers for Engram.
"""
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import engram_config as cfg
from engram_lock import FileLock
from engram_models import EngramEntry
from engram_utils import now_ts


def ensure_engram() -> Path:
    path = Path.cwd() / cfg.ENGRAM_DIR
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    for region in ["hippocampus", "cortex"]:
        for cat in cfg.CATEGORIES:
            (path / region / cat).mkdir(parents=True, exist_ok=True)
    (path / "amygdala").mkdir(parents=True, exist_ok=True)
    return path


def get_engram_path() -> Optional[Path]:
    cwd = Path.cwd()
    for part in [cwd] + list(cwd.parents):
        possible = part / cfg.ENGRAM_DIR
        if possible.exists():
            return possible
    return None


def write_entry(entry: EngramEntry, target_path: Optional[Path] = None):
    path = target_path or entry.path
    if not path:
        raise ValueError("Entry path is required to write.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(entry.to_file_content(), encoding="utf-8")
    entry.path = path


def list_all_entries(engram_path: Path, include_deprecated: bool = False) -> List[EngramEntry]:
    entries: List[EngramEntry] = []
    for region in ["hippocampus", "cortex"]:
        for cat in cfg.CATEGORIES:
            folder = engram_path / region / cat
            if not folder.exists():
                continue
            for file in folder.glob("*.md"):
                entry = EngramEntry.from_file(file)
                if not entry:
                    continue
                entry.region = region
                entry.category = cat
                if entry.deprecated and not include_deprecated:
                    continue
                entries.append(entry)
    return entries


def find_entry(engram_path: Path, mem_id: str) -> Optional[EngramEntry]:
    for region in ["hippocampus", "cortex"]:
        for cat in cfg.CATEGORIES:
            file = engram_path / region / cat / f"{mem_id}.md"
            if file.exists():
                return EngramEntry.from_file(file)
    return None


def recalc_path(engram_path: Path, entry: EngramEntry) -> Path:
    return engram_path / entry.region / entry.category / f"{entry.id}.md"


def add_backlinks(engram_path: Path, new_entry: EngramEntry, links: List[str]):
    if not links:
        return
    existing = {e.id: e for e in list_all_entries(engram_path, include_deprecated=True)}
    for lid in links:
        if lid not in existing:
            continue
        linked = existing[lid]
        if new_entry.id not in linked.links:
            linked.add_links([new_entry.id])
            linked.updated = now_ts()
            write_entry(linked)


def sync_backlinks(engram_path: Path, entry: EngramEntry, old_links: List[str]):
    """
    Ensure backlinks match the current link set:
    - Add backlinks for new links
    - Remove backlinks from links that were removed
    """
    existing = {e.id: e for e in list_all_entries(engram_path, include_deprecated=True)}
    old_set = set(old_links or [])
    new_set = set(entry.links or [])

    # Add new backlinks
    for lid in new_set - old_set:
        target = existing.get(lid)
        if not target:
            continue
        if entry.id not in target.links:
            target.add_links([entry.id])
            target.updated = now_ts()
            write_entry(target)

    # Remove backlinks no longer referenced
    for lid in old_set - new_set:
        target = existing.get(lid)
        if not target:
            continue
        if entry.id in target.links:
            target.links = [l for l in target.links if l != entry.id]
            target.updated = now_ts()
            write_entry(target)


def ensure_amygdala_pointer(engram_path: Path, entry: EngramEntry):
    pointer_path = engram_path / "amygdala" / f"{entry.id}.md"
    pointer = EngramEntry(
        id=entry.id,
        title=entry.title,
        category=entry.category,
        region="amygdala",
        importance="critical",
        retention="reference",
        tags=entry.tags,
        links=entry.links,
        strength=1.0,
        strength_floor=entry.strength_floor,
        created=entry.created,
        updated=now_ts(),
        recall_count=entry.recall_count,
        last_recalled=entry.last_recalled,
        pin_until=entry.pin_until,
        expiry=entry.expiry,
        summary=entry.summary,
        deprecated=entry.deprecated,
        content=f"Pointer to critical engram {entry.id} stored at {entry.path}.",
        path=pointer_path,
    )
    write_entry(pointer, target_path=pointer_path)


def maybe_remove_amygdala_pointer(engram_path: Path, entry_id: str):
    pointer = engram_path / "amygdala" / f"{entry_id}.md"
    if pointer.exists():
        pointer.unlink()


def update_recall_stats(engram_path: Path, entries: List[EngramEntry]):
    for e in entries:
        e.recall_count = int(e.recall_count) + 1
        e.last_recalled = now_ts()
        if not e.updated:
            e.updated = e.created
        write_entry(e)


def move_entry(engram_path: Path, entry: EngramEntry, new_region: str):
    old_path = entry.path
    entry.region = new_region
    target = recalc_path(engram_path, entry)
    write_entry(entry, target_path=target)
    if old_path and Path(old_path) != target and Path(old_path).exists():
        Path(old_path).unlink()


def mark_deprecated(engram_path: Path, entry: EngramEntry):
    entry.deprecated = True
    entry.retention = "deprecated"
    entry.add_tags(["deprecated"])
    entry.strength = 0.1
    entry.updated = now_ts()
    write_entry(entry)
    maybe_remove_amygdala_pointer(engram_path, entry.id)


def consolidate_entries(engram_path: Path, entries: List[EngramEntry]) -> List[EngramEntry]:
    """
    Promote hippocampus entries that qualify to cortex.
    """
    promoted: List[EngramEntry] = []
    upgraded: List[EngramEntry] = []
    for e in entries:
        if e.region != "hippocampus":
            continue
        if e.importance in cfg.DEFAULT_PROMOTION_IMPORTANCE or e.retention in cfg.DEFAULT_PROMOTION_RETENTION:
            e.retention = "reference"
            e.strength = max(e.strength, 0.9)
            e.updated = now_ts()
            move_entry(engram_path, e, "cortex")
            promoted.append(e)
            continue
        if e.recall_count >= cfg.DEFAULT_PROMOTION_RECALLS:
            e.retention = "reference"
            e.strength = max(e.strength, 0.9)
            e.updated = now_ts()
            move_entry(engram_path, e, "cortex")
            promoted.append(e)
    # Upgrade cortex items to reference if they are high/critical but still ephemeral/log
    for e in entries:
        if e.region != "cortex":
            continue
        if e.retention == "reference":
            continue
        if e.importance in cfg.DEFAULT_PROMOTION_IMPORTANCE:
            e.retention = "reference"
            e.strength = max(e.strength, 0.9)
            e.updated = now_ts()
            write_entry(e)
            upgraded.append(e)
    return promoted + upgraded
