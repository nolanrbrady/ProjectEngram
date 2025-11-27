"""
Scoring and retrieval logic.
"""
import difflib
from typing import Dict, List, Optional, Tuple

import engram_config as cfg
from engram_models import EngramEntry
from engram_utils import parse_dt


def compute_match_score(text: str, terms: List[str]) -> float:
    if not terms:
        return 0.0
    score = 0.0
    lowered = text.lower()
    words = lowered.split()
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


def _recency_score(entry: EngramEntry) -> float:
    import datetime

    updated_dt = parse_dt(entry.updated or entry.created)
    if not updated_dt:
        return 0.0
    days_old = (datetime.datetime.now() - updated_dt).days
    if entry.region == "hippocampus":
        if days_old <= 2:
            return 6
        if days_old <= 7:
            return 3
        return 0
    if days_old <= 7:
        return 4
    if days_old <= 30:
        return 2
    return 0


def region_component(region: str) -> float:
    return cfg.REGION_WEIGHTS.get(region, 1.0) * 5


def importance_component(importance: str) -> float:
    return cfg.IMPORTANCE_WEIGHTS.get(importance, 1.0) * 4


def retention_component(retention: str) -> float:
    return cfg.RETENTION_WEIGHTS.get(retention, 1.0) * 3


def build_adjacency(entries: List[EngramEntry]) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = {}
    for e in entries:
        graph.setdefault(e.id, [])
    for e in entries:
        for target in e.links:
            if target not in graph:
                graph[target] = []
            if target not in graph[e.id]:
                graph[e.id].append(target)
            if e.id not in graph[target]:
                graph[target].append(e.id)
    return graph


def compute_scores(entries: List[EngramEntry], query_terms: List[str], tag_filter: Optional[str]) -> Tuple[List[EngramEntry], List[EngramEntry]]:
    adjacency = build_adjacency(entries)
    criticals: List[EngramEntry] = []
    candidates: List[EngramEntry] = []

    seeds = []
    for e in entries:
        tags = [t.lower() for t in e.tags]
        if tag_filter and tag_filter not in tags:
            continue
        text_to_search = f"{e.summary} {e.content} {' '.join(tags)}"
        lexical = compute_match_score(text_to_search, query_terms) if query_terms else 0
        e.lexical_score = lexical  # type: ignore
        if lexical > 0 or tag_filter:
            seeds.append(e.id)

    seeds = sorted(seeds, key=lambda sid: next((x.lexical_score for x in entries if x.id == sid), 0), reverse=True)[:5]

    graph_bonus: Dict[str, float] = {}
    for sid in seeds:
        for neighbor in adjacency.get(sid, [])[:3]:
            graph_bonus[neighbor] = graph_bonus.get(neighbor, 0) + 6

    for e in entries:
        tags = [t.lower() for t in e.tags]
        if tag_filter and tag_filter not in tags:
            continue
        lexical = getattr(e, "lexical_score", 0)
        graph_extra = graph_bonus.get(e.id, 0)
        if query_terms and lexical <= 0 and graph_extra <= 0:
            continue
        score = (
            lexical
            + _recency_score(e)
            + graph_extra
            + region_component(e.region)
            + importance_component(e.importance)
            + retention_component(e.retention)
            + (e.strength * 2)
        )
        e.score = score  # type: ignore
        if e.importance == "critical" or "critical" in tags or e.region == "amygdala":
            criticals.append(e)
        candidates.append(e)

    candidates.sort(key=lambda e: getattr(e, "score", 0), reverse=True)
    criticals = list({c.id: c for c in criticals}.values())
    criticals.sort(key=lambda e: getattr(e, "score", 0), reverse=True)
    return criticals, candidates
