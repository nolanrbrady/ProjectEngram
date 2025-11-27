# AGENT MEMORY PROTOCOL

## SYSTEM OVERRIDE
You operate in a project with a **Persistent Memory Engram**. Use `pmem` for contextual knowledge.

## REGIONS (think brain areas)
- hippocampus: fresh/volatile (default destination)
- cortex: stable references and high-importance items
- amygdala: critical mirrors (safety constraints)

## STARTUP CHECKS
- Run `pmem recall "startup"` on arrival. If empty, create one with `pmem remember decisions "<rules>" --tags startup --retention reference`.
- Refresh context: `pmem recall --latest` and `pmem tags`.
- Narrow: `pmem recall "<keywords>" --tag <tag>`; use `--sort time` when recency matters.

## WRITE / UPDATE (pick the right retention)
- Default (ephemeral/log): `pmem remember <category> "<content>" [--tags ...]` → hippocampus.
- Long-lived/reference: add `--retention reference` or `--importance high`; this goes to cortex.
- Critical safety: `pmem remember ... --critical --require-confirm` (mirrors to amygdala).
- Edit in place: `pmem edit <ID> "<updated text>" [--tags ... --links ... --importance ... --retention ... --region ...]`
- Promote hippocampus → cortex: `pmem promote <ID>` (sets retention=reference).
- Consolidate promotions: `pmem consolidate` (auto-promotes high/critical/reference or frequently recalled hippocampus items).
- Deprecate obsolete: `pmem deprecate <ID>`.

## RECALL (how to fetch)
- `pmem recall "<query>" [--tag <tag>] [--sort relevance|time|tag] [--latest N]`
- Criticals (amygdala / importance=critical) are always pinned first.
- Graph-aware: links expand related engrams; hippocampus is downweighted unless recent.
- `pmem recall --latest` shows newest across regions (critical first), respects `--tag`.

## LINKS / IDS
- Use `--links ID1,ID2` when remembering/editing to connect related engrams; backlinks are auto-added.
- IDs are shown in recall output (format `ABC-123456`); use them for edit/promote/deprecate/link.

## QUICK EXAMPLES
- New reference rule to cortex: `pmem remember decisions "Deploy requires canary" --tags ops,deployment --retention reference`
- Critical guardrail: `pmem remember decisions "Do not deploy without approvals" --critical --require-confirm --tags ops,critical`
- Update with links: `pmem edit DEC-123456 "Add rollback step" --links PAT-0001,CTX-2222`
- Promote a proven scratch note: `pmem promote JOU-ABC123`
- Consolidate promotions: `pmem consolidate`

## AUDIT / TAGS
- `pmem audit` lists critical memories.
- `pmem tags` shows all tags.
