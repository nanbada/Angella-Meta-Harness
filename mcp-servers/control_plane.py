#!/usr/bin/env python3
"""Helpers for Angella control-plane artifact normalization and persistence."""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path
from typing import Any


ANGELLA_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTROL_PLANE_PATH = ANGELLA_ROOT / ".cache" / "angella" / "control-plane"
REQUIRED_INTENT_FIELDS = (
    "ideal_state_8_12_words",
    "metric_key",
    "success_threshold",
    "binary_acceptance_checks",
    "non_goals",
    "operator_constraints",
)


def resolve_control_plane_path() -> Path:
    configured = os.environ.get("ANGELLA_CONTROL_PLANE_DIR")
    if configured:
        return Path(os.path.abspath(os.path.expanduser(configured)))
    return DEFAULT_CONTROL_PLANE_PATH


def ensure_control_plane_layout() -> dict[str, str]:
    root = resolve_control_plane_path()
    paths = {
        "root": root,
        "runs": root / "runs",
        "failures_open": root / "failures" / "open",
        "failures_closed": root / "failures" / "closed",
        "knowledge_sops": root / "knowledge" / "sops",
        "knowledge_skills": root / "knowledge" / "skills",
        "meta_loop": root / "queue" / "meta-loop",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return {key: str(value) for key, value in paths.items()}


def safe_run_id(run_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(run_id)).strip("-") or "angella-run"


def run_dir(run_id: str) -> Path:
    layout = ensure_control_plane_layout()
    path = Path(layout["runs"]) / safe_run_id(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_jsonl(path: str | Path, payload: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []

    items: list[dict[str, Any]] = []
    with open(file_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, set):
        return sorted(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value).strip()]


def _missing_field(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def normalize_intent_contract(
    intent_contract: dict[str, Any] | None,
    *,
    metric_key: str = "",
    success_threshold: Any = "",
) -> dict[str, Any]:
    source = dict(intent_contract or {})
    ideal_state = str(source.get("ideal_state_8_12_words", "")).strip()
    normalized = {
        "ideal_state_8_12_words": ideal_state,
        "metric_key": str(source.get("metric_key") or metric_key or "").strip(),
        "success_threshold": source.get("success_threshold", success_threshold),
        "binary_acceptance_checks": _coerce_list(source.get("binary_acceptance_checks")),
        "non_goals": _coerce_list(source.get("non_goals")),
        "operator_constraints": _coerce_list(source.get("operator_constraints")),
        "intent_summary": str(source.get("intent_summary", "")).strip(),
        "metric_reason": str(source.get("metric_reason", "")).strip(),
        "first_hypotheses": _coerce_list(source.get("first_hypotheses")),
    }

    for key, value in source.items():
        if key not in normalized:
            normalized[key] = value

    word_count = len([part for part in re.split(r"\s+", ideal_state) if part])
    missing = [field for field in REQUIRED_INTENT_FIELDS if _missing_field(normalized.get(field))]
    normalized["validation"] = {
        "missing_required_fields": missing,
        "ideal_state_word_count": word_count,
        "ideal_state_target_ok": 8 <= word_count <= 12,
    }
    return normalized


def normalize_harness_metadata(harness_metadata: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(harness_metadata or {})
    selected_model_ids = source.get("selected_model_ids")
    if not isinstance(selected_model_ids, dict):
        selected_model_ids = {
            role: str(source.get(f"{role}_model_id", "")).strip()
            for role in ("lead", "planner", "worker")
            if str(source.get(f"{role}_model_id", "")).strip()
        }

    resolved_models = source.get("resolved_models")
    if not isinstance(resolved_models, dict):
        resolved_models = {}
        for role in ("lead", "planner", "worker"):
            role_meta = source.get(role)
            provider = ""
            model = ""
            if isinstance(role_meta, dict):
                provider = str(
                    role_meta.get("provider")
                    or role_meta.get("harness_provider")
                    or source.get(f"{role}_provider", "")
                ).strip()
                model = str(role_meta.get("model") or source.get(f"{role}_model", "")).strip()
            else:
                provider = str(source.get(f"{role}_provider", "")).strip()
                model = str(source.get(f"{role}_model", "")).strip()
            if provider or model:
                resolved_models[role] = {
                    "provider": provider,
                    "model": model,
                }

    env_snapshot = source.get("env_capability_snapshot")
    if not isinstance(env_snapshot, dict):
        env_snapshot = {}

    capability_block = source.get("capabilities")
    if isinstance(capability_block, dict):
        for key, value in capability_block.items():
            env_snapshot.setdefault(key, value)

    for key in ("mlx_preview_enabled", "nvfp4_enabled", "apfel_enabled"):
        if key in source:
            env_snapshot.setdefault(key, _boolish(source[key]))

    normalized = {
        "profile_id": str(
            source.get("profile_id")
            or source.get("harness_profile_id")
            or source.get("ANGELLA_HARNESS_PROFILE_ID", "")
        ).strip(),
        "selected_model_ids": selected_model_ids,
        "resolved_models": resolved_models,
        "env_capability_snapshot": env_snapshot,
        "objective_component": str(source.get("objective_component", "")).strip(),
    }

    if source:
        normalized["raw"] = source
    return normalized


def _expected_outcome(
    normalized_intent: dict[str, Any],
    metric_key: str,
    improvement_percent: float,
) -> str:
    threshold = normalized_intent.get("success_threshold")
    if threshold not in (None, "", []):
        return f"{metric_key} meets success threshold: {threshold}"
    if improvement_percent:
        return f"{metric_key} improves by at least {improvement_percent}%"
    return f"{metric_key} improves without violating acceptance checks"


def _failure_payload(
    *,
    run_id: str,
    iteration: int,
    decision: str,
    metric_key: str,
    metric_value: float,
    baseline_value: float,
    improvement_percent: float,
    benchmark_command: str,
    summary: str,
    failure_reason: str,
    proposals: str,
    normalized_intent: dict[str, Any],
    normalized_harness: dict[str, Any],
    aux_metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "component": normalized_harness.get("objective_component") or "unspecified",
        "failure_type": failure_reason,
        "reproduction": benchmark_command,
        "expected": _expected_outcome(normalized_intent, metric_key, improvement_percent),
        "observed": {
            "decision": decision,
            "metric_key": metric_key,
            "metric_value": metric_value,
            "baseline_value": baseline_value,
            "improvement_percent": improvement_percent,
            "aux_metrics": aux_metrics,
        },
        "candidate_fix_area": proposals or summary,
        "source_run_id": run_id,
        "source_iteration": iteration,
    }


def record_loop_iteration(
    *,
    run_id: str,
    project_name: str,
    iteration: int,
    decision: str,
    metric_key: str,
    metric_value: float,
    baseline_value: float,
    improvement_percent: float,
    start_commit: str,
    candidate_commit: str,
    benchmark_command: str,
    working_directory: str,
    summary: str,
    failure_reason: str = "",
    proposals: str = "",
    intent_contract: dict[str, Any] | None = None,
    harness_metadata: dict[str, Any] | None = None,
    aux_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_path = run_dir(run_id)
    normalized_intent = normalize_intent_contract(intent_contract, metric_key=metric_key)
    normalized_harness = normalize_harness_metadata(harness_metadata)
    aux_metrics = dict(aux_metrics or {})

    intent_path = run_path / "intent.json"
    if decision == "baseline" or not intent_path.exists():
        with open(intent_path, "w", encoding="utf-8") as handle:
            json.dump(normalized_intent, handle, indent=2, ensure_ascii=False)

    telemetry_event = {
        "event_type": "loop_iteration",
        "timestamp": now,
        "run_id": run_id,
        "project_name": project_name,
        "iteration": iteration,
        "decision": decision,
        "metric_key": metric_key,
        "metric_value": metric_value,
        "baseline_value": baseline_value,
        "improvement_percent": improvement_percent,
        "start_commit": start_commit,
        "candidate_commit": candidate_commit,
        "benchmark_command": benchmark_command,
        "working_directory": working_directory,
        "summary": summary,
        "proposals": proposals,
        "failure_reason": failure_reason,
        "intent_contract": normalized_intent,
        "harness_metadata": normalized_harness,
        "aux_metrics": aux_metrics,
    }
    append_jsonl(run_path / "telemetry.jsonl", telemetry_event)

    failure_path = ""
    if decision in {"failure", "revert"} and failure_reason:
        layout = ensure_control_plane_layout()
        failure_path = os.path.join(
            layout["failures_open"],
            f"{safe_run_id(run_id)}-iter-{iteration}.json",
        )
        with open(failure_path, "w", encoding="utf-8") as handle:
            json.dump(
                _failure_payload(
                    run_id=run_id,
                    iteration=iteration,
                    decision=decision,
                    metric_key=metric_key,
                    metric_value=metric_value,
                    baseline_value=baseline_value,
                    improvement_percent=improvement_percent,
                    benchmark_command=benchmark_command,
                    summary=summary,
                    failure_reason=failure_reason,
                    proposals=proposals,
                    normalized_intent=normalized_intent,
                    normalized_harness=normalized_harness,
                    aux_metrics=aux_metrics,
                ),
                handle,
                indent=2,
                ensure_ascii=False,
            )

    return {
        "run_dir": str(run_path),
        "intent_path": str(intent_path),
        "telemetry_path": str(run_path / "telemetry.jsonl"),
        "failure_path": failure_path,
        "normalized_intent": normalized_intent,
        "normalized_harness": normalized_harness,
    }


def write_final_summary(
    *,
    run_id: str,
    project_name: str,
    total_iterations: int,
    initial_metric: float,
    final_metric: float,
    metric_key: str,
    improvements_kept: int,
    summary: str,
    start_commit: str,
    final_commit: str,
    run_branch: str,
    benchmark_command: str,
    working_directory: str,
    failure_reasons: list[str] | None = None,
    intent_contract: dict[str, Any] | None = None,
    harness_metadata: dict[str, Any] | None = None,
    aux_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_path = run_dir(run_id)
    telemetry_path = run_path / "telemetry.jsonl"
    telemetry_events = load_jsonl(telemetry_path)
    normalized_intent = normalize_intent_contract(intent_contract, metric_key=metric_key)
    normalized_harness = normalize_harness_metadata(harness_metadata)
    aux_metrics = dict(aux_metrics or {})

    benchmark_results = []
    kept_changes = []
    reverted_changes = []
    failure_changes = []
    derived_failure_causes: list[str] = []

    for event in telemetry_events:
        if event.get("event_type") != "loop_iteration":
            continue
        benchmark_results.append(
            {
                "iteration": event.get("iteration"),
                "decision": event.get("decision"),
                "metric_key": event.get("metric_key"),
                "metric_value": event.get("metric_value"),
                "baseline_value": event.get("baseline_value"),
                "improvement_percent": event.get("improvement_percent"),
                "candidate_commit": event.get("candidate_commit", ""),
                "failure_reason": event.get("failure_reason", ""),
                "summary": event.get("summary", ""),
            }
        )

        record = {
            "iteration": event.get("iteration"),
            "candidate_commit": event.get("candidate_commit", ""),
            "metric_value": event.get("metric_value"),
            "improvement_percent": event.get("improvement_percent"),
            "summary": event.get("summary", ""),
        }
        decision = event.get("decision")
        if decision == "keep":
            kept_changes.append(record)
        elif decision == "revert":
            reverted_changes.append(record)
        elif decision == "failure":
            failure_changes.append(record)

        failure_reason = str(event.get("failure_reason", "")).strip()
        if failure_reason:
            derived_failure_causes.append(failure_reason)

    combined_failure_causes = []
    for reason in list(failure_reasons or []) + derived_failure_causes:
        if reason and reason not in combined_failure_causes:
            combined_failure_causes.append(reason)

    summary_payload = {
        "run_id": run_id,
        "project_name": project_name,
        "total_iterations": total_iterations,
        "metric_key": metric_key,
        "initial_metric": initial_metric,
        "final_metric": final_metric,
        "improvements_kept": improvements_kept,
        "summary": summary,
        "start_commit": start_commit,
        "final_commit": final_commit,
        "run_branch": run_branch,
        "benchmark_command": benchmark_command,
        "working_directory": working_directory,
        "intent_contract": normalized_intent,
        "selected_model_ids": normalized_harness.get("selected_model_ids", {}),
        "resolved_models": normalized_harness.get("resolved_models", {}),
        "env_capability_snapshot": normalized_harness.get("env_capability_snapshot", {}),
        "benchmark_results": benchmark_results,
        "failure_causes": combined_failure_causes,
        "kept_changes": kept_changes,
        "reverted_changes": reverted_changes,
        "failed_changes": failure_changes,
        "aux_metrics": aux_metrics,
    }

    raw_harness = normalized_harness.get("raw")
    if raw_harness:
        summary_payload["harness_metadata"] = raw_harness

    with open(run_path / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, indent=2, ensure_ascii=False)

    return {
        "run_dir": str(run_path),
        "summary_path": str(run_path / "summary.json"),
        "summary_payload": summary_payload,
    }
