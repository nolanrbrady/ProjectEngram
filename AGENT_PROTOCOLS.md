# AGENT MEMORY PROTOCOL

## SYSTEM OVERRIDE
You operate in a project with a **Persistent Memory Engram**. Use `pmem` for all contextual knowledge.

## STARTUP MANDATES
- Run `pmem recall "startup"` immediately. If nothing is returned, create one with `pmem remember decisions "<rules>" --tags startup`.
- Refresh context with `pmem recall --latest` and explore tags via `pmem tags`.
- Narrow context with `pmem recall "<keywords>" --tag <tag>` and use `--sort time` when recency matters.

## UPDATES
- Edit in place: `pmem edit <ID> "<updated text>" [--tags ...]` instead of duplicating memories.
- Critical safety rules: `pmem remember ... --critical --require-confirm`; audit with `pmem audit`.
- Mark obsolete items: `pmem deprecate <ID>`.

## COMMAND QUICKLIST
- `pmem recall "<query>" [--tag <tag>] [--sort relevance|time|tag] [--latest N]`
- `pmem recall --latest` to see the newest memories (works with `--tag`).
- `pmem remember <category> "<content>" [--tags ...] [--critical --require-confirm]`
- `pmem edit <id> "<content>" [--tags ...]`
- `pmem audit` to list all critical memories.
- `pmem tags`
- `pmem deprecate <id>`
