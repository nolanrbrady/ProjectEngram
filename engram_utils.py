"""
Shared utility helpers.
"""
import datetime
import hashlib
import json
import time
from typing import List, Optional

import engram_config as cfg


def now_ts() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def parse_dt(ts: Optional[str]) -> Optional[datetime.datetime]:
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None


def generate_id(category: str) -> str:
    prefix = category[:3].upper()
    suffix = hashlib.md5(f"{category}-{time.time_ns()}".encode("utf-8")).hexdigest()[:6].upper()
    return f"{prefix}-{suffix}"


def compute_capsule(content: str, limit: int = 180) -> str:
    clean = " ".join(content.strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def base_strength(region: str, importance: str, retention: str) -> float:
    base = 0.4 if region == "hippocampus" else 0.9
    if importance == "critical":
        base += 0.35
    elif importance == "high":
        base += 0.2
    elif importance == "low":
        base -= 0.05

    if retention == "reference":
        base += 0.1
    elif retention == "log":
        base -= 0.05
    elif retention == "deprecated":
        base = 0.1

    return max(0.1, min(1.3, base))


def to_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=True)


def normalize_tags(tags: Optional[str]) -> List[str]:
    if not tags:
        return []
    return [t.strip() for t in tags.split(",") if t.strip()]


def normalize_links(links: Optional[str]) -> List[str]:
    if not links:
        return []
    seen = []
    for l in links.split(","):
        val = l.strip()
        if not val:
            continue
        if val not in seen:
            seen.append(val)
    return seen
