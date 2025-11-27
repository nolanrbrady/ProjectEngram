## Project Engram (pmem)
A zero-dependency, drop-in persistent memory layer for CLI coding agents. Memories live as individual Markdown “engrams” that mirror brain regions: hippocampus (fresh), cortex (stable), and an amygdala mirror for critical constraints.

## The Problem
CLI agents are stateless. They forget architectural decisions and safety rules, leading to inconsistency and repeated mistakes.

## The Solution
Engram creates a `.engram/` directory with per-memory Markdown files, a lightweight graph (links), and a recall flow that blends lexical match, recency, region/importance weights, and graph neighbors. Criticals are always pinned.

### Layout
```
.engram/
  hippocampus/<category>/<ID>.md   # probationary/volatile
  cortex/<category>/<ID>.md        # stable/reference
  amygdala/<ID>.md                 # critical mirrors/pointers
```
Categories: `decisions`, `patterns`, `context`, `journal`, `notes`.

Each engram file uses JSON frontmatter:
```markdown
---
{"id":"DEC-123456","title":"Deploy flow","category":"decisions","region":"cortex","importance":"high","retention":"reference","tags":["ops","deploy"],"links":["PAT-0001"],"strength":1.0,"strength_floor":0.5,"created":"2024-01-01T10:00:00","updated":"2024-01-02T09:00:00","recall_count":3,"last_recalled":"2024-01-05T12:00:00","pin_until":null,"expiry":null,"summary":"Blue/green; staging→canary→prod.","deprecated":false}
---
Full content here...
```

## Installation
```
pip install -e .
```

## Quick Start
1) Initialize: `pmem init` (creates `.engram/` and `AGENT_PROTOCOLS.md`).
2) Prime: `pmem recall "startup"` then `pmem recall --latest`.
3) Save: `pmem remember decisions "Document the deploy flow" --tags startup,ops --retention reference`.

## Command Guide (how to write/edit/promote/recall)
- Remember: `pmem remember <category> "<content>" [--title ...] [--tags ...] [--links ...] [--importance critical|high|normal|low] [--retention reference|ephemeral|log] [--region hippocampus|cortex] [--critical --require-confirm] [--pin-until ISO] [--expiry ISO]`
  - Default goes to hippocampus; `--retention reference` or `--importance high|critical` lands in cortex; `--critical` mirrors to amygdala and requires `--require-confirm`.
- Edit: `pmem edit <id> "<updated content>" [--tags ... --links ... --importance ... --retention ... --region ...]`
- Promote: `pmem promote <id>` (hippocampus → cortex, retention=reference)
- Consolidate: `pmem consolidate` (promotes hippocampus items meeting thresholds such as high importance, reference retention, or recall streaks)
- Recall: `pmem recall "<query>" [--tag <tag>] [--sort relevance|time|tag] [--latest N]`
- Audit criticals: `pmem audit`
- Deprecate: `pmem deprecate <id>`
- Tags: `pmem tags`

## Behaviors & Retrieval
- Per-memory files with JSON frontmatter; links provide graph expansion and backlinks are auto-added.
- Scoring blends lexical match, recency, graph neighbors, region weight (cortex > hippocampus), importance, retention, and strength.
- Hippocampus is downweighted unless recent; cortex/reference items decay slowly; criticals are pinned to the top.
- `--latest` surfaces newest across regions (critical first) and respects `--tag`.
- Promotion paths: high/critical/reference items and frequently recalled hippocampus notes can be promoted via `pmem promote` or `pmem consolidate` (auto).

## Code Structure
- `engram.py`: CLI entrypoint and argument parsing.
- `engram_commands.py`: command handlers (remember/edit/recall/promote/consolidate/etc.).
- `engram_models.py`: EngramEntry dataclass + serialization.
- `engram_storage.py`: filesystem layout, reads/writes, backlinks, amygdala pointers, promotion.
- `engram_recall.py`: scoring/ranking and graph adjacency logic.
- `engram_utils.py`, `engram_config.py`, `engram_lock.py`: shared helpers, constants, and file locking.

## Agent Instructions
Include `AGENT_PROTOCOLS.md` in your agent bootstrap prompt. It documents startup checks, region meanings, retention/importance guidance, how to write/edit/promote/consolidate, link usage, and the critical-memory rules. If `AGENTS.md` or `CLAUDE.md` already exists, `pmem init` appends a reminder to read `AGENT_PROTOCOLS.md`.
