#!/usr/bin/env python3
"""Integration checks for accepted meta-loop finalization automation."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

from meta_loop_ops import (
    export_meta_loop_change,
    finalize_accepted_meta_loop_run,
    generate_knowledge_drafts_from_run,
    prune_stale_control_plane_artifacts,
)  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _run(args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return result.stdout.strip()


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_root:
        tmp = Path(tmp_root)
        repo = tmp / "repo"
        remote = tmp / "remote.git"
        fake_bin = tmp / "bin"
        fake_bin.mkdir()

        gh_script = fake_bin / "gh"
        gh_script.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"create\" ]; then\n"
            "  echo \"https://example.com/pr/123\"\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"view\" ]; then\n"
            "  echo \"https://example.com/pr/123\"\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n",
            encoding="utf-8",
        )
        gh_script.chmod(gh_script.stat().st_mode | stat.S_IEXEC)

        env = dict(os.environ)
        env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
        env["ANGELLA_CONTROL_PLANE_DIR"] = str(repo / ".cache" / "angella" / "control-plane")
        os.environ["PATH"] = env["PATH"]
        os.environ["ANGELLA_CONTROL_PLANE_DIR"] = env["ANGELLA_CONTROL_PLANE_DIR"]

        repo.mkdir()
        _run(["git", "init", "-b", "main"], cwd=repo, env=env)
        _run(["git", "config", "user.name", "Angella Test"], cwd=repo, env=env)
        _run(["git", "config", "user.email", "angella@example.com"], cwd=repo, env=env)

        (repo / "knowledge" / "sops").mkdir(parents=True)
        (repo / "knowledge" / "skills").mkdir(parents=True)
        (repo / "README.md").write_text("# Temp Repo\n", encoding="utf-8")
        (repo / "knowledge" / "sops" / "failure-threshold-not-met.md").write_text(
            "# Existing SOP\n\n- keep original guidance\n",
            encoding="utf-8",
        )
        (repo / "knowledge" / "skills" / "worker-ollama-gemma4-26b.md").write_text(
            "# Existing Skill\n\n- preserve existing worker guidance\n",
            encoding="utf-8",
        )
        _run(["git", "add", "README.md"], cwd=repo, env=env)
        _run(["git", "add", "knowledge/sops/failure-threshold-not-met.md"], cwd=repo, env=env)
        _run(["git", "add", "knowledge/skills/worker-ollama-gemma4-26b.md"], cwd=repo, env=env)
        _run(["git", "commit", "-m", "init"], cwd=repo, env=env)

        _run(["git", "init", "--bare", str(remote)], cwd=tmp, env=env)
        _run(["git", "remote", "add", "origin", str(remote)], cwd=repo, env=env)
        _run(["git", "push", "-u", "origin", "main"], cwd=repo, env=env)

        control_plane = Path(env["ANGELLA_CONTROL_PLANE_DIR"])
        run_id = "angella-meta-run"
        run_dir = control_plane / "runs" / run_id
        _write_json(
            run_dir / "summary.json",
            {
                "run_id": run_id,
                "project_name": "Angella",
                "total_iterations": 2,
                "metric_key": "build_time",
                "initial_metric": 12.5,
                "final_metric": 10.2,
                "improvements_kept": 1,
                "summary": "Accepted harness change reduced setup-check runtime and stabilized retries.",
                "start_commit": _run(["git", "rev-parse", "HEAD"], cwd=repo, env=env),
                "final_commit": "",
                "run_branch": "",
                "benchmark_command": "bash setup.sh --check",
                "working_directory": str(repo),
                "intent_contract": {
                    "ideal_state_8_12_words": "Cut setup check time without changing installer behavior today",
                    "metric_key": "build_time",
                    "success_threshold": ">= 5% faster",
                    "binary_acceptance_checks": ["setup check passes", "templates still render"],
                    "non_goals": ["No config regressions"],
                    "operator_constraints": ["Keep repo portable"],
                },
                "selected_model_ids": {
                    "lead": "openai_gpt_5_2_pro",
                    "planner": "anthropic_claude_sonnet_4",
                    "worker": "ollama_gemma4_26b",
                },
                "resolved_models": {
                    "worker": {"provider": "ollama", "model": "gemma4:26b"},
                },
                "env_capability_snapshot": {
                    "mlx_preview_enabled": False,
                    "nvfp4_enabled": False,
                    "apfel_enabled": False,
                },
                "kept_changes": [{"iteration": 2, "candidate_commit": "def456"}],
                "failure_causes": ["threshold_not_met"],
                "harness_metadata": {"objective_component": "setup-check"},
            },
        )
        _write_json(
            control_plane / "runs" / "older-run" / "summary.json",
            {
                "run_id": "older-run",
                "improvements_kept": 1,
                "summary": "Previous accepted worker tuning.",
                "selected_model_ids": {"worker": "ollama_gemma4_26b"},
                "kept_changes": [{"iteration": 1, "candidate_commit": "abc123"}],
            },
        )
        _write_json(
            control_plane / "failures" / "open" / "failure-one.json",
            {"failure_type": "threshold_not_met"},
        )
        _write_json(
            control_plane / "failures" / "closed" / "failure-two.json",
            {"failure_type": "threshold_not_met"},
        )

        dry_run_drafts = generate_knowledge_drafts_from_run(
            run_id,
            objective_component="setup-check",
            dry_run=True,
        )
        assert dry_run_drafts["dry_run"] is True
        for item in dry_run_drafts["drafts_created"]:
            assert not Path(item["draft_path"]).exists()
            assert not Path(item["metadata_path"]).exists()

        queue_before = sorted(
            path.name for path in (control_plane / "queue" / "meta-loop").glob("*")
        )
        (repo / "harness-change.txt").write_text("accepted change\n", encoding="utf-8")
        dry_run_finalize = finalize_accepted_meta_loop_run(
            run_id,
            objective_component="setup-check",
            base_branch="main",
            pr_summary="Dry run should not change git or control-plane state.",
            operator_confirmed=False,
            dry_run=True,
            repo_root=repo,
        )
        assert dry_run_finalize["export"]["pr_url"] == "dry-run"
        assert _run(["git", "branch", "--show-current"], cwd=repo, env=env) == "main"
        assert not any((control_plane / "knowledge" / "sops").glob("failure-threshold-not-met.md.meta.json"))
        assert not any((control_plane / "knowledge" / "skills").glob("worker-ollama-gemma4-26b.md.meta.json"))
        queue_after = sorted(
            path.name for path in (control_plane / "queue" / "meta-loop").glob("*")
        )
        assert queue_before == queue_after
        assert "harness-change.txt" in _run(["git", "status", "--short"], cwd=repo, env=env)

        result = finalize_accepted_meta_loop_run(
            run_id,
            objective_component="setup-check",
            base_branch="main",
            pr_summary="Accepted setup-check ratchet.",
            operator_confirmed=False,
            repo_root=repo,
        )

        promoted_targets = {str(Path(path).resolve()) for path in result["promoted_targets"]}
        assert str((repo / "knowledge" / "sops" / "failure-threshold-not-met.md").resolve()) in promoted_targets
        assert str((repo / "knowledge" / "skills" / "worker-ollama-gemma4-26b.md").resolve()) in promoted_targets
        assert (repo / "knowledge" / "sops" / "failure-threshold-not-met.md").is_file()
        assert (repo / "knowledge" / "skills" / "worker-ollama-gemma4-26b.md").is_file()
        sop_content = (repo / "knowledge" / "sops" / "failure-threshold-not-met.md").read_text(encoding="utf-8")
        skill_content = (repo / "knowledge" / "skills" / "worker-ollama-gemma4-26b.md").read_text(encoding="utf-8")
        assert "keep original guidance" in sop_content
        assert "Accepted Run Addendum - `angella-meta-run`" in sop_content
        assert "preserve existing worker guidance" in skill_content
        assert "Accepted Run Addendum - `angella-meta-run`" in skill_content
        assert result["export"]["branch_name"].startswith("codex/")
        assert result["export"]["pr_url"] == "https://example.com/pr/123"
        assert Path(result["finalize_path"]).is_file()
        summary_payload = json.loads(Path(result["summary_path"]).read_text(encoding="utf-8"))
        assert summary_payload["export"]["pr_url"] == "https://example.com/pr/123"
        assert summary_payload["promotion"]["promoted"]
        assert "Meta-loop export: branch=" in summary_payload["summary"]

        current_branch = _run(["git", "branch", "--show-current"], cwd=repo, env=env)
        assert current_branch.startswith("codex/")

        remote_head = _run(
            ["git", "--git-dir", str(remote), "for-each-ref", "--format=%(refname:short)", "refs/heads"],
            cwd=repo,
            env=env,
        )
        assert current_branch in remote_head.splitlines()

        _run(["git", "switch", "-c", "retry-source"], cwd=repo, env=env)
        (repo / "retry-change.txt").write_text("retry export state\n", encoding="utf-8")
        retry_export = export_meta_loop_change(
            run_id,
            objective_component="setup-check",
            base_branch="main",
            pr_summary="Retry export should follow current source head.",
            repo_root=repo,
        )
        retry_branch = retry_export["branch_name"]
        assert retry_branch == current_branch
        assert _run(["git", "branch", "--show-current"], cwd=repo, env=env) == retry_branch
        assert (repo / "retry-change.txt").is_file()
        assert "retry-change.txt" in _run(["git", "show", "--stat", "--oneline", "HEAD"], cwd=repo, env=env)

        stale_metadata = control_plane / "knowledge" / "sops" / "stale-item.md.meta.json"
        stale_markdown = control_plane / "knowledge" / "sops" / "stale-item.md"
        stale_queue = control_plane / "queue" / "meta-loop" / "old-entry.json"
        _write_json(stale_metadata, {"draft_id": "stale-item", "status": "draft"})
        stale_markdown.write_text("# stale\n", encoding="utf-8")
        _write_json(stale_queue, {"action": "stale"})
        old_time = time.time() - (3 * 86400)
        os.utime(stale_metadata, (old_time, old_time))
        os.utime(stale_markdown, (old_time, old_time))
        os.utime(stale_queue, (old_time, old_time))

        prune_result = prune_stale_control_plane_artifacts(max_age_days=1)
        removed_paths = {item["path"] for item in prune_result["removed"]}
        assert str(stale_metadata) in removed_paths
        assert str(stale_markdown) in removed_paths
        assert str(stale_queue) in removed_paths
        assert not stale_metadata.exists()
        assert not stale_markdown.exists()
        assert not stale_queue.exists()

    print("meta loop admin tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
