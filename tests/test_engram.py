import argparse

import pytest

import engram


@pytest.fixture
def engram_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = engram.ensure_engram()
    for filename in engram.MEMORY_FILES.values():
        (path / filename).write_text(f"# {filename}\n", encoding="utf-8")
    return path


def add_entry(engram_path, category, content, mem_id, tags=None, timestamp="2024-01-01T00:00"):
    file_path = engram_path / engram.MEMORY_FILES[category]
    entry_text = engram.format_entry(content, tags=tags, mem_id=mem_id, timestamp=timestamp)
    existing = file_path.read_text(encoding="utf-8")
    file_path.write_text(existing + entry_text, encoding="utf-8")
    return entry_text


def test_ensure_and_find_engram(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    created = engram.ensure_engram()
    assert created.exists()

    nested = tmp_path / "nested" / "child"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert engram.get_engram_path() == created


def test_file_lock_creates_and_removes_lock(tmp_path):
    lock_path = tmp_path / engram.LOCK_FILE
    with engram.FileLock(lock_path, timeout=0.1):
        assert lock_path.exists()
    assert not lock_path.exists()


def test_format_entry_adds_critical_tag():
    entry_text = engram.format_entry(
        "Deploy infra",
        tags=["ops"],
        critical=True,
        mem_id="ABC123",
        timestamp="2024-01-01T00:00",
    )
    assert entry_text.startswith("\n## [2024-01-01T00:00] {ABC123} Tags: ops, CRITICAL\n")
    assert entry_text.strip().endswith("Deploy infra")


def test_parse_entries_extracts_metadata():
    raw = "# Header\n" + engram.format_entry(
        "Keep notes",
        tags=["General", "Backend"],
        mem_id="ID123",
        timestamp="2024-02-01T12:30",
    )
    parsed = engram.parse_entries(raw)

    assert len(parsed) == 1
    entry = parsed[0]
    assert entry["id"] == "ID123"
    assert entry["date"] == "2024-02-01T12:30"
    assert entry["tags_list"] == ["General", "Backend"]
    assert entry["dt"].isoformat(timespec="minutes") == "2024-02-01T12:30"
    assert entry["content"] == "Keep notes"


def test_load_entries_skips_deprecated_by_default(engram_env):
    file_path = engram_env / engram.MEMORY_FILES["decisions"]
    active = engram.format_entry("Active decision", mem_id="LIVE1", timestamp="2024-01-01T00:00")
    deprecated = engram.format_entry("Old decision", mem_id="OLD1", timestamp="2023-01-01T00:00")
    deprecated = deprecated.replace("{OLD1}", "{OLD1} [DEPRECATED]", 1)
    file_path.write_text("# decisions\n" + active + deprecated, encoding="utf-8")

    entries = engram.load_entries(engram_env)
    ids = {e["id"] for e in entries}
    assert "LIVE1" in ids
    assert "OLD1" not in ids

    entries_with_deprecated = engram.load_entries(engram_env, include_deprecated=True)
    ids_with = {e["id"] for e in entries_with_deprecated}
    assert {"LIVE1", "OLD1"} <= ids_with
    deprecated_entry = next(e for e in entries_with_deprecated if e["id"] == "OLD1")
    assert deprecated_entry["is_deprecated"]
    assert deprecated_entry["category"] == "decisions"


def test_compute_match_score_rewards_multiple_terms():
    score_single = engram.compute_match_score("deploy pipeline to staging", ["deploy"])
    score_multiple = engram.compute_match_score("deploy pipeline to staging", ["deploy", "pipeline"])
    score_fuzzy = engram.compute_match_score("deploy pipeline to staging", ["pipline"])

    assert score_multiple > score_single >= 10
    assert 0 < score_fuzzy < score_single


def test_cmd_remember_creates_entry_and_journal_log(engram_env):
    args = argparse.Namespace(
        category="decisions",
        content="Document deploy flow",
        tags="ops,backend",
        critical=False,
        require_confirm=False,
    )
    engram.cmd_remember(args)

    entries = engram.load_entries(engram_env)
    decision = next(e for e in entries if e["category"] == "decisions")
    assert "Document deploy flow" in decision["content"]
    assert set(t.lower() for t in decision["tags_list"]) == {"ops", "backend"}

    journal_entries = [e for e in entries if e["category"] == "journal"]
    assert any("Updated decisions" in e["content"] for e in journal_entries)
    assert any(
        "auto-log" in [t.lower() for t in entry["tags_list"]]
        for entry in journal_entries
    )


def test_cmd_remember_requires_confirmation_for_critical(engram_env):
    args = argparse.Namespace(
        category="decisions",
        content="Critical constraint",
        tags=None,
        critical=True,
        require_confirm=False,
    )
    with pytest.raises(SystemExit) as excinfo:
        engram.cmd_remember(args)

    assert excinfo.value.code == 1
    decisions_text = (engram_env / engram.MEMORY_FILES["decisions"]).read_text()
    assert "Critical constraint" not in decisions_text


def test_cmd_deprecate_marks_entry(engram_env):
    add_entry(engram_env, "decisions", "Use Postgres", "ABC123", tags=["general"], timestamp="2024-01-01T00:00")
    args = argparse.Namespace(id="ABC123")
    engram.cmd_deprecate(args)

    content = (engram_env / engram.MEMORY_FILES["decisions"]).read_text()
    assert "[DEPRECATED]" in content

    entries = engram.load_entries(engram_env, include_deprecated=True)
    deprecated_entry = next(e for e in entries if e["id"] == "ABC123")
    assert deprecated_entry["is_deprecated"]


def test_cmd_edit_updates_content_and_tags(engram_env):
    add_entry(engram_env, "decisions", "Old content", "EDIT1", tags=["general"], timestamp="2024-01-01T00:00")
    args = argparse.Namespace(id="EDIT1", content="Revised content", tags="updated")
    engram.cmd_edit(args)

    entries = engram.load_entries(engram_env, include_deprecated=True)
    edited = next(e for e in entries if e["id"] == "EDIT1")
    assert "Revised content" in edited["content"]
    assert edited["tags_list"] == ["updated"]

    journal_entries = [e for e in entries if e["category"] == "journal"]
    assert any("Edited decisions" in e["content"] for e in journal_entries)


def test_cmd_recall_filters_and_excludes_critical_from_hits(engram_env, capsys):
    add_entry(engram_env, "decisions", "ops note", "SAFE1", tags=["ops"], timestamp="2024-01-02T00:00")
    add_entry(engram_env, "decisions", "ops constraint", "CRIT1", tags=["critical"], timestamp="2024-01-01T00:00")

    args = argparse.Namespace(query="ops", tag=None, latest=None, sort="relevance")
    engram.cmd_recall(args)
    output = capsys.readouterr().out

    assert "CRITICAL PROJECT CONSTRAINTS" in output
    assert "CRIT1" in output and "SAFE1" in output
    assert output.count("CRIT1") == 1


def test_cmd_recall_latest_shows_newest_entries_first(engram_env, capsys):
    add_entry(engram_env, "decisions", "Older note", "OLD123", tags=["general"], timestamp="2024-01-01T00:00")
    add_entry(engram_env, "decisions", "Newer note", "NEW123", tags=["general"], timestamp="2024-02-01T00:00")

    args = argparse.Namespace(query=None, tag=None, latest=2, sort="relevance")
    engram.cmd_recall(args)
    output = capsys.readouterr().out

    first_idx = output.find("NEW123")
    second_idx = output.find("OLD123")
    assert first_idx != -1 and second_idx != -1
    assert first_idx < second_idx


def test_cmd_recall_startup_hint_when_missing(engram_env, capsys):
    args = argparse.Namespace(query="startup checklist", tag=None, latest=None, sort="relevance")
    engram.cmd_recall(args)

    output = capsys.readouterr().out
    assert "No startup memory found" in output
    assert "pmem remember decisions" in output


def test_cmd_tags_lists_all_tags(engram_env, capsys):
    add_entry(engram_env, "decisions", "Alpha entry", "ID1", tags=["alpha", "gamma"])
    add_entry(engram_env, "patterns", "Beta entry", "ID2", tags=["beta"])

    args = argparse.Namespace()
    engram.cmd_tags(args)
    output = capsys.readouterr().out.strip().splitlines()

    assert output[0] == "--- KNOWN TAGS ---"
    assert output[1] == "alpha, beta, gamma"


def test_cmd_audit_shows_only_critical(engram_env, capsys):
    add_entry(engram_env, "decisions", "Non critical", "SAFE", tags=["ops"])
    add_entry(engram_env, "decisions", "Critical rule", "CRIT", tags=["critical"])

    args = argparse.Namespace()
    engram.cmd_audit(args)
    output = capsys.readouterr().out

    assert "--- CRITICAL MEMORIES AUDIT ---" in output
    assert "CRIT" in output
    assert "SAFE" not in output
