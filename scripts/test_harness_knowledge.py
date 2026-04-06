#!/usr/bin/env python3
"""Regression checks for tracked harness wiki sync and builtin search."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

from meta_loop_ops import (  # noqa: E402
    inspect_harness_knowledge,
    lint_harness_knowledge,
    save_harness_query_page,
    search_harness_knowledge,
    sync_harness_knowledge,
)
from output_compactor import compact_output  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_root:
        root = Path(tmp_root)
        repo = root / "repo"
        control_plane = root / "control-plane"
        os.environ["ANGELLA_CONTROL_PLANE_DIR"] = str(control_plane)

        (repo / "knowledge" / "sops").mkdir(parents=True)
        (repo / "knowledge" / "skills").mkdir(parents=True)
        (repo / "docs").mkdir(parents=True)
        (repo / "knowledge" / "schema.md").write_text(
            "# Angella Harness Wiki Schema\n\n"
            "## Layers\n\n"
            "## Entry Points\n\n"
            "## Component Pages\n\n"
            "## Linking Rules\n\n"
            "## Log Rules\n\n"
            "## Addendum Rules\n\n"
            "## Search Rules\n\n"
            "## Non-Goals\n",
            encoding="utf-8",
        )
        (repo / "knowledge" / "skills" / "worker-gemma4-local.md").write_text(
            "# Worker Skill: Gemma4 Local Reasoning\n\n- keep context compact\n",
            encoding="utf-8",
        )
        (repo / "scripts").mkdir(parents=True, exist_ok=True)
        (repo / "scripts" / "run_harness_parity_diff.py").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        os.chmod(repo / "scripts" / "run_harness_parity_diff.py", 0o755)
        (repo / "config").mkdir(parents=True, exist_ok=True)
        (repo / "config" / "knowledge-policy.yaml").write_text(
            json.dumps(
                {
                    "knowledge_policy": {
                        "indexed_paths": ["knowledge", "docs/current-harness-status.md", "PARITY.md"],
                        "canonical_entrypoints": ["knowledge/index.md", "knowledge/log.md"],
                        "search_provider": "builtin",
                        "snippet_chars": 240,
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (repo / "docs" / "current-harness-status.md").write_text("# Current Harness Status\n", encoding="utf-8")
        (repo / "PARITY.md").write_text(
            "# Parity Status — Temp\n\n- Canonical document: `scripts/run_harness_parity_diff.py`\n\n## Lane 1 — temp lane\n\n- Status: implemented\n- Evidence: `docs/current-harness-status.md`\n",
            encoding="utf-8",
        )

        _write_json(
            control_plane / "runs" / "accepted-run" / "summary.json",
            {
                "run_id": "accepted-run",
                "metric_key": "build_time",
                "summary": "Accepted setup-check hardening with deterministic install behavior.",
                "improvements_kept": 1,
                "kept_changes": [{"iteration": 1, "candidate_commit": "abc123"}],
                "failure_causes": ["threshold_not_met"],
                "selected_model_ids": {"worker": "ollama_gemma4_26b"},
                "resolved_models": {"worker": {"provider": "ollama", "model": "gemma4:26b"}},
                "harness_metadata": {"objective_component": "setup-check"},
            },
        )
        _write_json(
            control_plane / "runs" / "verification-run" / "summary.json",
            {
                "run_id": "verification-run",
                "run_kind": "verification_only",
                "verification_only": True,
                "metric_key": "build_time",
                "summary": "Verification-only recipe runtime benchmark passed without a patch.",
                "report_path": str(control_plane / "runs" / "verification-run" / "report.md"),
                "harness_metadata": {"objective_component": "recipe-runtime"},
            },
        )
        _write_json(
            control_plane / "failures" / "open" / "failure-open.json",
            {
                "component": "setup-check",
                "failure_type": "threshold_not_met",
                "source_run_id": "accepted-run",
            },
        )
        draft_path = control_plane / "knowledge" / "skills" / "worker-ollama-gemma4-26b.md"
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text("# Worker Pattern: ollama_gemma4_26b\n\n- deterministic execution\n", encoding="utf-8")
        _write_json(
            control_plane / "knowledge" / "skills" / "worker-ollama-gemma4-26b.md.meta.json",
            {
                "status": "promoted",
                "target_relpath": "knowledge/skills/worker-ollama-gemma4-26b.md",
            },
        )

        sync_result = sync_harness_knowledge(
            run_id="accepted-run",
            source_kind="run",
            repo_root=repo,
        )
        assert sync_result["indexed_document_count"] >= 4
        assert (repo / "knowledge" / "index.md").is_file()
        assert (repo / "knowledge" / "log.md").is_file()
        assert (repo / "knowledge" / "sources" / "index.md").is_file()
        assert (repo / "knowledge" / "components" / "setup-check.md").is_file()
        assert (repo / "knowledge" / "components" / "recipe-runtime.md").is_file()
        assert (repo / "knowledge" / "skills" / "worker-ollama-gemma4-26b.md").is_file()
        assert any((repo / "knowledge" / "sources").glob("source-*.md"))

        search_result = search_harness_knowledge("setup-check deterministic", repo_root=repo)
        assert search_result["success"] is True
        assert search_result["results"]
        first = search_result["results"][0]
        assert first["compaction"]["raw_chars"] >= first["compaction"]["compact_chars"]
        assert "setup-check" in json.dumps(search_result, ensure_ascii=False)

        inspection = inspect_harness_knowledge(format="markdown", repo_root=repo)
        assert inspection["format"] == "markdown"
        assert "## Components" in inspection["content"]
        assert "knowledge/index.md" in inspection["content"]
        assert "## Sources" in inspection["content"]

        query_page = save_harness_query_page(
            query="What changed for setup-check?",
            answer_summary="Accepted setup-check hardening is the latest reusable result.",
            cited_paths=["knowledge/components/setup-check.md"],
            generated_artifacts=["knowledge/queries/placeholder.md"],
            save_reason="operator note",
            title="setup-check recap",
            repo_root=repo,
        )
        assert Path(query_page["page_path"]).is_file()
        assert (repo / "knowledge" / "queries").is_dir()

        lint_result = lint_harness_knowledge(repo_root=repo)
        assert lint_result["success"] is True, lint_result["issues"]
        assert lint_result["issue_count"] == 0

        compacted = compact_output(
            "test_output",
            "warning: flaky\nwarning: flaky\nassertion failed\nassertion failed\n",
            budget_chars=80,
        )
        assert compacted["estimated_tokens_saved"] > 0
        assert "(x2)" in compacted["text"]

    print("harness knowledge tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
