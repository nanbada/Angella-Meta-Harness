#!/usr/bin/env python3
"""Regression checks for normalized control-plane artifacts."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

from control_plane import record_loop_iteration, write_final_summary  # noqa: E402


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp_root:
        control_plane_dir = Path(tmp_root) / "control-plane"
        os.environ["ANGELLA_CONTROL_PLANE_DIR"] = str(control_plane_dir)

        run_id = "angella-demo-build"
        harness_metadata = {
            "profile_id": "default",
            "lead_model_id": "openai_gpt_5_2_pro",
            "planner_model_id": "anthropic_claude_sonnet_4",
            "worker_model_id": "ollama_gemma4_26b",
            "lead_provider": "openai",
            "lead_model": "gpt-5.2-pro",
            "planner_provider": "anthropic",
            "planner_model": "claude-sonnet-4-20250514",
            "worker_provider": "ollama",
            "worker_model": "gemma4:26b",
            "mlx_preview_enabled": False,
            "nvfp4_enabled": False,
            "apfel_enabled": False,
            "objective_component": "setup-check",
        }
        intent_contract = {
            "ideal_state_8_12_words": "Ship faster builds without changing user visible behavior today",
            "success_threshold": ">= 5% faster",
            "binary_acceptance_checks": ["build succeeds", "tests pass"],
            "non_goals": ["No feature changes"],
            "operator_constraints": ["Keep the worktree clean"],
            "intent_summary": "Reduce build time without changing behavior.",
            "metric_reason": "Build time is the optimization target.",
            "first_hypotheses": ["Tighten caching", "Reduce redundant work"],
        }

        baseline = record_loop_iteration(
            run_id=run_id,
            project_name="demo-project",
            iteration=0,
            decision="baseline",
            metric_key="build_time",
            metric_value=12.5,
            baseline_value=12.5,
            improvement_percent=0.0,
            start_commit="abc123",
            candidate_commit="",
            benchmark_command="npm run build",
            working_directory="/tmp/demo-project",
            summary="Baseline established.",
            intent_contract=intent_contract,
            harness_metadata=harness_metadata,
            aux_metrics={"metric_source": "duration_fallback"},
        )

        run_dir = Path(baseline["run_dir"])
        intent_path = Path(baseline["intent_path"])
        telemetry_path = Path(baseline["telemetry_path"])
        assert run_dir.is_dir()
        assert intent_path.is_file()
        assert telemetry_path.is_file()

        intent_payload = _read_json(intent_path)
        assert intent_payload["metric_key"] == "build_time"
        assert intent_payload["validation"]["ideal_state_target_ok"] is True
        assert intent_payload["binary_acceptance_checks"] == ["build succeeds", "tests pass"]

        revert = record_loop_iteration(
            run_id=run_id,
            project_name="demo-project",
            iteration=1,
            decision="revert",
            metric_key="build_time",
            metric_value=12.2,
            baseline_value=12.5,
            improvement_percent=2.4,
            start_commit="abc123",
            candidate_commit="def456",
            benchmark_command="npm run build",
            working_directory="/tmp/demo-project",
            summary="Not enough improvement to keep.",
            failure_reason="threshold_not_met",
            proposals="Investigate cache reuse",
            intent_contract=intent_contract,
            harness_metadata=harness_metadata,
            aux_metrics={"failure_reason": "threshold_not_met"},
        )
        failure_path = Path(revert["failure_path"])
        assert failure_path.is_file()

        failure_payload = _read_json(failure_path)
        assert failure_payload["component"] == "setup-check"
        assert failure_payload["failure_type"] == "threshold_not_met"
        assert failure_payload["source_run_id"] == run_id
        assert failure_payload["source_iteration"] == 1

        summary = write_final_summary(
            run_id=run_id,
            project_name="demo-project",
            total_iterations=1,
            initial_metric=12.5,
            final_metric=12.5,
            metric_key="build_time",
            improvements_kept=0,
            summary="No ratchet kept yet.",
            start_commit="abc123",
            final_commit="abc123",
            run_branch="codex/demo-control-plane",
            benchmark_command="npm run build",
            working_directory="/tmp/demo-project",
            failure_reasons=["threshold_not_met"],
            intent_contract=intent_contract,
            harness_metadata=harness_metadata,
            aux_metrics={"benchmark_runs": 2},
        )

        summary_path = Path(summary["summary_path"])
        assert summary_path.is_file()

        summary_payload = _read_json(summary_path)
        assert summary_payload["selected_model_ids"]["worker"] == "ollama_gemma4_26b"
        assert summary_payload["resolved_models"]["lead"]["provider"] == "openai"
        assert summary_payload["env_capability_snapshot"]["apfel_enabled"] is False
        assert len(summary_payload["benchmark_results"]) == 2
        assert summary_payload["reverted_changes"][0]["candidate_commit"] == "def456"
        assert "threshold_not_met" in summary_payload["failure_causes"]

    print("control plane logging tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
