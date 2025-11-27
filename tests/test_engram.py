import argparse
import time
from pathlib import Path

import pytest

import engram
from engram_storage import write_entry


@pytest.fixture
def engram_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = engram.ensure_engram()
    return path


def build_remember_args(
    category,
    content,
    *,
    title=None,
    tags=None,
    links=None,
    importance=None,
    retention=None,
    region=None,
    critical=False,
    require_confirm=False,
):
    return argparse.Namespace(
        category=category,
        content=content,
        title=title,
        tags=tags,
        links=links,
        importance=importance,
        retention=retention,
        region=region,
        critical=critical,
        require_confirm=require_confirm,
        pin_until=None,
        expiry=None,
    )


def build_edit_args(mem_id, content, **kwargs):
    return argparse.Namespace(
        id=mem_id,
        content=content,
        tags=kwargs.get("tags"),
        links=kwargs.get("links"),
        importance=kwargs.get("importance"),
        retention=kwargs.get("retention"),
        region=kwargs.get("region"),
    )


def recall_args(query=None, tag=None, latest=None, sort="relevance"):
    return argparse.Namespace(query=query, tag=tag, latest=latest, sort=sort)


def test_ensure_and_find_engram(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    created = engram.ensure_engram()
    assert (created / "hippocampus").exists()
    assert (created / "cortex").exists()
    nested = tmp_path / "nested" / "child"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert engram.get_engram_path() == created


def test_file_lock_creates_and_removes_lock(tmp_path):
    lock_path = tmp_path / engram.LOCK_FILE
    with engram.FileLock(lock_path, timeout=0.1):
        assert lock_path.exists()
    assert not lock_path.exists()


def test_remember_defaults_to_hippocampus(engram_env):
    args = build_remember_args("decisions", "Document deploy flow", tags="ops,backend")
    engram.cmd_remember(args)

    entries = engram.list_all_entries(engram_env)
    decision = next(e for e in entries if e.category == "decisions")
    assert decision.region == "hippocampus"
    assert "Document deploy flow" in decision.content
    assert set(decision.tags) == {"ops", "backend"}
    assert Path(decision.path).parent.name == "decisions"


def test_remember_reference_goes_to_cortex(engram_env):
    args = build_remember_args(
        "patterns",
        "CI/CD rollout doc",
        tags="ops",
        retention="reference",
    )
    engram.cmd_remember(args)
    entries = engram.list_all_entries(engram_env)
    stored = next(e for e in entries if e.category == "patterns")
    assert stored.region == "cortex"
    assert stored.retention == "reference"


def test_remember_requires_confirmation_for_critical(engram_env):
    args = build_remember_args("decisions", "Critical constraint", critical=True, require_confirm=False)
    with pytest.raises(SystemExit) as excinfo:
        engram.cmd_remember(args)
    assert excinfo.value.code == 1
    amygdala_files = list((engram_env / "amygdala").glob("*.md"))
    assert not amygdala_files


def test_deprecate_marks_entry(engram_env):
    args = build_remember_args("context", "Legacy thing", tags="general")
    engram.cmd_remember(args)
    entry = engram.list_all_entries(engram_env)[0]
    dep_args = argparse.Namespace(id=entry.id)
    engram.cmd_deprecate(dep_args)

    deprecated_entry = engram.find_entry(engram_env, entry.id)
    assert deprecated_entry.deprecated
    assert deprecated_entry.retention == "deprecated"


def test_edit_moves_region_and_updates_content(engram_env):
    args = build_remember_args("decisions", "Old content", tags="alpha")
    engram.cmd_remember(args)
    entry = engram.list_all_entries(engram_env)[0]

    edit = build_edit_args(entry.id, "New content", region="cortex", tags="beta")
    engram.cmd_edit(edit)

    updated = engram.find_entry(engram_env, entry.id)
    assert updated.region == "cortex"
    assert "New content" in updated.content
    assert updated.tags == ["beta"]


def test_recall_pins_critical_first(engram_env, capsys):
    normal = build_remember_args("decisions", "ops note", tags="ops")
    critical = build_remember_args("decisions", "ops constraint", tags="critical", critical=True, require_confirm=True)
    engram.cmd_remember(normal)
    engram.cmd_remember(critical)

    engram.cmd_recall(recall_args(query="ops"))
    output = capsys.readouterr().out
    assert "CRITICAL PROJECT CONSTRAINTS" in output
    assert output.find("constraint") < output.find("note")


def test_recall_latest_orders_by_time(engram_env, capsys):
    first = build_remember_args("journal", "Older note", tags="general")
    second = build_remember_args("journal", "Newer note", tags="general")
    engram.cmd_remember(first)
    time.sleep(1)
    engram.cmd_remember(second)

    engram.cmd_recall(recall_args(latest=2))
    output = capsys.readouterr().out
    search_section = output.split("--- SEARCHING")[-1]
    assert search_section.find("Newer note") < search_section.find("Older note")


def test_tags_lists_all_tags(engram_env, capsys):
    engram.cmd_remember(build_remember_args("decisions", "Alpha entry", tags="alpha,gamma"))
    engram.cmd_remember(build_remember_args("patterns", "Beta entry", tags="beta"))

    engram.cmd_tags(argparse.Namespace())
    lines = [line for line in capsys.readouterr().out.strip().splitlines() if line and not line.startswith("Memory stored")]
    assert lines[0] == "--- KNOWN TAGS ---"
    assert lines[1] == "alpha, beta, gamma"


def test_audit_shows_only_critical(engram_env, capsys):
    engram.cmd_remember(build_remember_args("decisions", "Non critical", tags="ops"))
    engram.cmd_remember(
        build_remember_args("decisions", "Critical rule", tags="critical", critical=True, require_confirm=True)
    )
    engram.cmd_audit(argparse.Namespace())
    output = capsys.readouterr().out
    assert "--- CRITICAL MEMORIES AUDIT ---" in output
    assert "Critical rule" in output
    assert "Non critical" not in output


def test_backlinks_are_added(engram_env):
    root = build_remember_args("context", "Root note", tags="root")
    engram.cmd_remember(root)
    entries = engram.list_all_entries(engram_env)
    root_entry = entries[0]

    child = build_remember_args("notes", "Child note", tags="child", links=root_entry.id)
    engram.cmd_remember(child)

    updated_root = engram.find_entry(engram_env, root_entry.id)
    child_entry = next(e for e in engram.list_all_entries(engram_env) if e.id != root_entry.id)
    assert updated_root
    assert child_entry.id in updated_root.links


def test_consolidate_promotes_recalled_items(engram_env):
    args = build_remember_args("journal", "Recurring note", tags="log")
    engram.cmd_remember(args)
    entry = engram.list_all_entries(engram_env)[0]
    # Simulate frequent recalls
    entry.recall_count = 4
    write_entry(entry)

    engram.cmd_consolidate(argparse.Namespace())
    promoted = engram.find_entry(engram_env, entry.id)
    assert promoted.region == "cortex"
    assert promoted.retention == "reference"


def test_recall_prefers_cortex_over_old_hippocampus(engram_env, capsys):
    cortex_args = build_remember_args("decisions", "Stable rule", tags="ops", retention="reference")
    hippo_args = build_remember_args("decisions", "Old scratch", tags="ops")
    engram.cmd_remember(cortex_args)
    engram.cmd_remember(hippo_args)

    # Age the hippocampus entry by tweaking updated timestamp to far past
    hippo_entry = [e for e in engram.list_all_entries(engram_env) if e.region == "hippocampus"][0]
    hippo_entry.updated = "2023-01-01T00:00:00"
    write_entry(hippo_entry)

    engram.cmd_recall(recall_args(query="ops", sort="relevance"))
    out = capsys.readouterr().out
    assert out.find("Stable rule") < out.find("Old scratch")


# --- Additional coverage ---


def test_recall_tag_filter_excludes_other_tags(engram_env, capsys):
    engram.cmd_remember(build_remember_args("context", "Backend note", tags="backend"))
    engram.cmd_remember(build_remember_args("context", "Frontend note", tags="frontend"))

    engram.cmd_recall(recall_args(query=None, tag="backend"))
    out = capsys.readouterr().out
    assert "Backend note" in out
    assert "Frontend note" not in out


def test_recall_uses_graph_bonus_for_neighbors(engram_env, capsys):
    root = build_remember_args("context", "Root about deployments", tags="ops")
    engram.cmd_remember(root)
    root_entry = engram.list_all_entries(engram_env)[0]
    neighbor = build_remember_args("notes", "Linked neighbor", tags="misc", links=root_entry.id)
    engram.cmd_remember(neighbor)

    # Query matches root strongly; neighbor should be pulled via graph bonus
    engram.cmd_recall(recall_args(query="deployments"))
    out = capsys.readouterr().out
    assert "Root about deployments" in out
    assert "Linked neighbor" in out


def test_promote_sets_reference_and_cortex(engram_env):
    args = build_remember_args("patterns", "To be promoted", tags="ops")
    engram.cmd_remember(args)
    entry = engram.list_all_entries(engram_env)[0]

    engram.cmd_promote(argparse.Namespace(id=entry.id))
    promoted = engram.find_entry(engram_env, entry.id)
    assert promoted.region == "cortex"
    assert promoted.retention == "reference"


def test_edit_critical_creates_amygdala_pointer(engram_env):
    args = build_remember_args("decisions", "Non critical", tags="ops")
    engram.cmd_remember(args)
    entry = engram.list_all_entries(engram_env)[0]

    engram.cmd_edit(build_edit_args(entry.id, "Now critical", importance="critical", tags="ops,critical"))
    pointer = list((engram_env / "amygdala").glob("*.md"))
    assert pointer


def test_edit_drops_amygdala_on_downgrade(engram_env):
    args = build_remember_args("decisions", "Critical note", tags="critical", critical=True, require_confirm=True)
    engram.cmd_remember(args)
    entry = engram.list_all_entries(engram_env)[0]
    assert list((engram_env / "amygdala").glob("*.md"))

    engram.cmd_edit(build_edit_args(entry.id, "No longer critical", importance="normal", tags="ops"))
    assert not list((engram_env / "amygdala").glob("*.md"))


def test_consolidate_promotes_high_importance(engram_env):
    args = build_remember_args("journal", "Important but new", tags="ops", importance="high")
    engram.cmd_remember(args)
    engram.cmd_consolidate(argparse.Namespace())
    entry = engram.list_all_entries(engram_env)[0]
    assert entry.region == "cortex"
    assert entry.retention == "reference"


def test_consolidate_promotes_reference_retention(engram_env):
    args = build_remember_args("journal", "Reference item", tags="ops", retention="reference")
    engram.cmd_remember(args)
    engram.cmd_consolidate(argparse.Namespace())
    entry = engram.list_all_entries(engram_env)[0]
    assert entry.region == "cortex"
    assert entry.retention == "reference"


def test_recall_latest_respects_tag(engram_env, capsys):
    engram.cmd_remember(build_remember_args("journal", "Ops latest", tags="ops"))
    time.sleep(1)
    engram.cmd_remember(build_remember_args("journal", "Frontend latest", tags="frontend"))

    engram.cmd_recall(recall_args(latest=1, tag="ops"))
    out = capsys.readouterr().out
    assert "Ops latest" in out
    assert "Frontend latest" not in out


def test_remember_respects_forced_region(engram_env):
    args = build_remember_args("decisions", "Force cortex", tags="ops", region="cortex")
    engram.cmd_remember(args)
    entry = engram.list_all_entries(engram_env)[0]
    assert entry.region == "cortex"


def test_tags_are_sorted(engram_env, capsys):
    engram.cmd_remember(build_remember_args("context", "Tag order", tags="gamma,alpha,beta"))
    engram.cmd_tags(argparse.Namespace())
    lines = [line for line in capsys.readouterr().out.strip().splitlines() if line and not line.startswith("Memory stored")]
    assert lines[1] == "alpha, beta, gamma"


def test_init_nudges_agent_docs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent_doc = tmp_path / "AGENTS.md"
    agent_doc.write_text("Agent guide", encoding="utf-8")
    engram.cmd_init(argparse.Namespace())
    content = agent_doc.read_text(encoding="utf-8")
    assert "AGENT_PROTOCOLS.md" in content


def test_init_creates_agent_doc_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    engram.cmd_init(argparse.Namespace())
    agent_doc = tmp_path / "AGENTS.md"
    assert agent_doc.exists()
    content = agent_doc.read_text(encoding="utf-8")
    assert "AGENT_PROTOCOLS.md" in content
