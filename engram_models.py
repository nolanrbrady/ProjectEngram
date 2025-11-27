"""
Data model for Engram entries.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import engram_config as cfg
from engram_utils import compute_capsule, now_ts, to_json


def _default_meta(meta: dict) -> dict:
    meta.setdefault("region", "hippocampus")
    meta.setdefault("importance", cfg.DEFAULT_IMPORTANCE)
    meta.setdefault("retention", cfg.DEFAULT_RETENTION)
    meta.setdefault("tags", [])
    meta.setdefault("links", [])
    meta.setdefault("strength", cfg.DEFAULT_STRENGTH_FLOOR)
    meta.setdefault("strength_floor", cfg.DEFAULT_STRENGTH_FLOOR)
    meta.setdefault("recall_count", 0)
    meta.setdefault("deprecated", False)
    meta.setdefault("summary", "")
    meta.setdefault("title", meta.get("summary", ""))
    meta.setdefault("created", now_ts())
    meta.setdefault("updated", meta["created"])
    meta.setdefault("category", "journal")
    meta.setdefault("pin_until", None)
    meta.setdefault("expiry", None)
    meta.setdefault("last_recalled", None)
    return meta


@dataclass
class EngramEntry:
    id: str
    title: str
    category: str
    region: str
    importance: str
    retention: str
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    strength: float = cfg.DEFAULT_STRENGTH_FLOOR
    strength_floor: float = cfg.DEFAULT_STRENGTH_FLOOR
    created: str = field(default_factory=now_ts)
    updated: str = field(default_factory=now_ts)
    recall_count: int = 0
    last_recalled: Optional[str] = None
    pin_until: Optional[str] = None
    expiry: Optional[str] = None
    summary: str = ""
    deprecated: bool = False
    content: str = ""
    path: Optional[Path] = None

    @classmethod
    def from_file(cls, path: Path) -> Optional["EngramEntry"]:
        raw = path.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            return None
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return None
        meta_str = parts[1].strip()
        body = parts[2].strip()
        try:
            meta = json.loads(meta_str)
        except json.JSONDecodeError:
            return None
        meta = _default_meta(meta)
        meta["title"] = meta.get("title") or compute_capsule(body)[:80]
        return cls(
            id=meta["id"],
            title=meta["title"],
            category=meta["category"],
            region=meta["region"],
            importance=meta["importance"],
            retention=meta["retention"],
            tags=meta["tags"],
            links=meta["links"],
            strength=meta["strength"],
            strength_floor=meta["strength_floor"],
            created=meta["created"],
            updated=meta["updated"],
            recall_count=int(meta["recall_count"]),
            last_recalled=meta.get("last_recalled"),
            pin_until=meta.get("pin_until"),
            expiry=meta.get("expiry"),
            summary=meta.get("summary", ""),
            deprecated=bool(meta.get("deprecated", False)),
            content=body,
            path=path,
        )

    def to_frontmatter(self) -> str:
        meta = {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "region": self.region,
            "importance": self.importance,
            "retention": self.retention,
            "tags": self.tags,
            "links": self.links,
            "strength": self.strength,
            "strength_floor": self.strength_floor,
            "created": self.created,
            "updated": self.updated,
            "recall_count": self.recall_count,
            "last_recalled": self.last_recalled,
            "pin_until": self.pin_until,
            "expiry": self.expiry,
            "summary": self.summary or compute_capsule(self.content),
            "deprecated": self.deprecated,
        }
        return to_json(meta)

    def to_file_content(self) -> str:
        return f"---\n{self.to_frontmatter()}\n---\n{self.content.strip()}\n"

    def add_tags(self, tags: List[str]):
        self.tags = sorted(set(self.tags + tags))

    def add_links(self, links: List[str]):
        self.links = sorted(set(self.links + links))
