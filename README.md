## Project Engram (pmem)
A zero-dependency, drop-in persistent memory layer for CLI coding agents.

## The Problem
CLI agents are stateless. They forget architectural decisions and safety rules, leading to inconsistency and repeated mistakes.

## The Solution
Engram acts as a "hive mind" for your agents. It creates a `.engram/` directory where it stores semantic memories in Markdown, and ships a CLI tool (`pmem`) that agents are instructed to use.

## Installation
```
pip install -e .
```

## Quick Start
1) Initialize the workspace: `pmem init` (creates `.engram/` and `AGENT_PROTOCOLS.md`).
2) Prime yourself: `pmem recall "startup"` then `pmem recall --latest`.
3) Save context: `pmem remember decisions "Document the deploy flow" --tags startup,ops`.

## Command Guide
- Remember: `pmem remember <category> "<content>" [--tags ...] [--critical --require-confirm]`
- Edit in place: `pmem edit <id> "<updated content>" [--tags ...]`
- Recall: `pmem recall "<query>" [--tag <tag>] [--latest N] [--sort relevance|time|tag]`
- Latest snapshot: `pmem recall --latest` (shows newest notes even with no query)
- Audit criticals: `pmem audit`
- Deprecate: `pmem deprecate <id>`
- Tags: `pmem tags`

Categories: `decisions`, `patterns`, `context`, `journal`.

## Behaviors & Ergonomics
- Search uses substring + fuzzy matching and can sort by relevance, time, or tag.
- `--latest` surfaces the newest few memories without needing a query.
- Startup assist: if `pmem recall "startup"` is empty, you're prompted to create one and shown recent `general` notes.
- Metadata first: recall output always shows timestamps, tags, category, and IDs.
- Safety rails: `--critical` requires `--require-confirm`, and `pmem audit` lists all critical entries quickly.
- Edits, not duplicates: update entries in-place with `pmem edit` to avoid churn.

## Agent Instructions
Include `AGENT_PROTOCOLS.md` in your agent bootstrap prompt. It describes the startup checks (`pmem recall "startup"`, `pmem recall --latest`), how to edit vs. deprecate, and the critical-memory rules.
