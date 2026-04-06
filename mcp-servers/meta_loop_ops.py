#!/usr/bin/env python3
"""Automation helpers for accepted harness meta-loop runs."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from string import Template
from typing import Any

from control_plane import append_jsonl, ensure_control_plane_layout, run_dir, safe_run_id


ANGELLA_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_ROOT = ANGELLA_ROOT / "logs" / "Goose Logs"
META_LOOP_PR_TEMPLATE_PATH = ANGELLA_ROOT / "templates" / "meta-loop-pr.md.tmpl"
BOOTSTRAP_PYTHON = ANGELLA_ROOT / ".cache" / "angella" / "bootstrap-venv" / "bin" / "python"
BRANCH_PREFIX = "codex/meta-loop"
MAX_BRANCH_LENGTH = 96
BRANCH_OBJECTIVE_SLUG_MAX = 20
BRANCH_RUN_SLUG_MAX = 28
DEFAULT_DRAFT_RETENTION_DAYS = 14
QUEUE_RETENTION_POLICY_DAYS = {
    "draft_pr": 14,
    "promotion_report": 21,
    "export": 30,
    "finalize": 30,
    "prune_report": 7,
    "default": 21,
}


def queue_retention_policy_days() -> dict[str, Any]:
    return {
        "drafts": DEFAULT_DRAFT_RETENTION_DAYS,
        "queue": dict(QUEUE_RETENTION_POLICY_DAYS),
    }


def harness_component_context(objective_component: str) -> dict[str, Any]:
    component = objective_component.strip() or "recipe-runtime"
    contexts = {
        "setup-check": {
            "component": "setup-check",
            "metric_key": "build_time",
            "benchmark_command": "bash setup.sh --check",
            "working_directory": str(ANGELLA_ROOT),
            "binary_acceptance_checks": [
                "setup check exits 0",
                "template rendering checks passed",
            ],
            "success_signal": "setup.sh --check exits 0 and reports template rendering checks passed",
            "priority_files": [
                "setup.sh",
                "scripts/setup-bootstrap.sh",
                "scripts/setup-install.sh",
                "scripts/setup-common.sh",
            ],
            "allowed_fix_surface": [
                "setup.sh",
                "scripts/setup-bootstrap.sh",
                "scripts/setup-install.sh",
                "scripts/setup-common.sh",
            ],
            "notes": "Focus on installer preflight and render-time behavior. Avoid repo-wide exploration.",
        },
        "setup-yes-warm": {
            "component": "setup-yes-warm",
            "metric_key": "build_time",
            "benchmark_command": "bash scripts/test_setup_flows.sh",
            "working_directory": str(ANGELLA_ROOT),
            "binary_acceptance_checks": [
                "setup flow tests pass",
                "bootstrap/install/yes flows all complete",
            ],
            "success_signal": "setup flow regression stays green across bootstrap, install, and --yes paths",
            "priority_files": [
                "scripts/test_setup_flows.sh",
                "scripts/setup-common.sh",
                "scripts/setup-install.sh",
            ],
            "allowed_fix_surface": [
                "scripts/test_setup_flows.sh",
                "scripts/setup-common.sh",
                "scripts/setup-install.sh",
            ],
            "notes": "Use the existing setup flow test as the warm-path benchmark.",
        },
        "setup-yes-cold": {
            "component": "setup-yes-cold",
            "metric_key": "build_time",
            "benchmark_command": "bash scripts/test_setup_flows.sh",
            "working_directory": str(ANGELLA_ROOT),
            "binary_acceptance_checks": [
                "setup flow tests pass",
                "cold-path assumptions are still portable",
            ],
            "success_signal": "cold-path setup flow test passes without host-specific shortcuts",
            "priority_files": [
                "scripts/test_setup_flows.sh",
                "scripts/setup-bootstrap.sh",
                "scripts/setup-common.sh",
            ],
            "allowed_fix_surface": [
                "scripts/test_setup_flows.sh",
                "scripts/setup-bootstrap.sh",
                "scripts/setup-common.sh",
            ],
            "notes": "Cold-path work should stay deterministic and avoid host-specific shortcuts.",
        },
        "profile-resolution": {
            "component": "profile-resolution",
            "metric_key": "build_time",
            "benchmark_command": f"{BOOTSTRAP_PYTHON} scripts/harness_catalog.py list-profiles",
            "working_directory": str(ANGELLA_ROOT),
            "binary_acceptance_checks": [
                "profile listing exits 0",
                "default resolves to Gemma4",
            ],
            "success_signal": "profile listing exits 0 and default worker resolves to Gemma4",
            "priority_files": [
                "config/harness-models.yaml",
                "config/harness-profiles.yaml",
                "scripts/harness_catalog.py",
            ],
            "allowed_fix_surface": [
                "config/harness-models.yaml",
                "config/harness-profiles.yaml",
                "scripts/harness_catalog.py",
            ],
            "notes": "Keep role resolution deterministic and avoid broad codebase scans.",
        },
        "recipe-runtime": {
            "component": "recipe-runtime",
            "metric_key": "build_time",
            "benchmark_command": f"{BOOTSTRAP_PYTHON} scripts/test_harness_self_optimize_adapter.py",
            "working_directory": str(ANGELLA_ROOT),
            "binary_acceptance_checks": [
                "harness self-optimize adapter tests pass",
                "inspection, promotion, export, and retention paths stay callable",
            ],
            "success_signal": (
                "adapter benchmark completes and the recipe exits via accepted, revert, or verification-only"
            ),
            "priority_files": [
                "recipes/harness-self-optimize.yaml",
                "mcp-servers/meta_loop_ops.py",
                "mcp-servers/control_plane_admin.py",
                "scripts/test_harness_self_optimize_adapter.py",
                "scripts/test_meta_loop_admin.py",
            ],
            "allowed_fix_surface": [
                "recipes/harness-self-optimize.yaml",
                "mcp-servers/meta_loop_ops.py",
                "mcp-servers/control_plane_admin.py",
                "scripts/test_harness_self_optimize_adapter.py",
                "scripts/test_meta_loop_admin.py",
            ],
            "notes": (
                "Stay tightly scoped to the self-optimize recipe and control-plane admin flow. "
                "Do not tree/analyze the entire repository when these files are sufficient."
            ),
        },
    }
    return contexts.get(component, contexts["recipe-runtime"])


def _now_timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def _stable_suffix(*parts: str, length: int = 8) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]


def _bounded_slug(value: str, max_len: int) -> str:
    slug = _slug(value)
    if len(slug) <= max_len:
        return slug
    suffix = _stable_suffix(slug, length=6)
    head = slug[: max(1, max_len - 7)].rstrip("-")
    return f"{head}-{suffix}"


def _default_meta_loop_branch_name(objective_component: str, run_id: str) -> str:
    objective_slug = _bounded_slug(objective_component or "harness", BRANCH_OBJECTIVE_SLUG_MAX)
    run_slug = _bounded_slug(safe_run_id(run_id), BRANCH_RUN_SLUG_MAX)
    suffix = _stable_suffix(objective_component or "harness", run_id, length=8)
    branch = f"{BRANCH_PREFIX}-{objective_slug}-{run_slug}-{suffix}"
    return branch[:MAX_BRANCH_LENGTH].rstrip("-")


def _normalize_requested_branch_name(branch_name: str, run_id: str) -> str:
    requested = branch_name.strip()
    if not requested:
        return ""
    if requested.startswith("codex/"):
        requested = requested[len("codex/") :]
    normalized = _bounded_slug(requested.replace("/", "-"), MAX_BRANCH_LENGTH - len("codex/") - 9)
    suffix = _stable_suffix(requested, run_id, length=8)
    return f"codex/{normalized}-{suffix}"[:MAX_BRANCH_LENGTH].rstrip("-")


def _content_fingerprint(content: str) -> str:
    normalized = "\n".join(line.rstrip() for line in content.strip().splitlines())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _draft_fingerprint_marker(fingerprint: str) -> str:
    return f"<!-- angella-draft-fingerprint:{fingerprint} -->"


def _repo_root(repo_root: str | Path | None = None) -> Path:
    if repo_root is None:
        return ANGELLA_ROOT
    return Path(repo_root).resolve()


def _summary_path(run_id: str) -> Path:
    return run_dir(run_id) / "summary.json"


def load_run_summary(run_id: str) -> dict[str, Any]:
    path = _summary_path(run_id)
    if not path.exists():
        raise RuntimeError(f"summary.json not found for run_id={run_id}")
    return _json_load(path)


def _all_run_summaries() -> list[dict[str, Any]]:
    layout = ensure_control_plane_layout()
    runs_root = Path(layout["runs"])
    summaries: list[dict[str, Any]] = []
    for path in sorted(runs_root.glob("*/summary.json")):
        try:
            payload = _json_load(path)
        except Exception:
            continue
        payload["_summary_path"] = str(path)
        summaries.append(payload)
    return summaries


def _is_accepted_summary(summary: dict[str, Any]) -> bool:
    if int(summary.get("improvements_kept", 0)) > 0:
        return True
    kept_changes = summary.get("kept_changes", [])
    if isinstance(kept_changes, list) and kept_changes:
        return True
    benchmark_results = summary.get("benchmark_results", [])
    return any(item.get("decision") == "keep" for item in benchmark_results if isinstance(item, dict))


def _selected_worker_id(summary: dict[str, Any]) -> str:
    selected = summary.get("selected_model_ids", {})
    if isinstance(selected, dict):
        worker = str(selected.get("worker", "")).strip()
        if worker:
            return worker
    harness_metadata = summary.get("harness_metadata", {})
    if isinstance(harness_metadata, dict):
        worker = str(harness_metadata.get("worker_model_id", "")).strip()
        if worker:
            return worker
    return ""


def collect_failure_counts() -> dict[str, int]:
    layout = ensure_control_plane_layout()
    counts: dict[str, int] = {}
    for folder in (Path(layout["failures_open"]), Path(layout["failures_closed"])):
        for path in sorted(folder.glob("*.json")):
            try:
                payload = _json_load(path)
            except Exception:
                continue
            failure_type = str(payload.get("failure_type", "")).strip()
            if not failure_type:
                continue
            counts[failure_type] = counts.get(failure_type, 0) + 1
    return counts


def collect_accepted_run_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for summary in _all_run_summaries():
        if not _is_accepted_summary(summary):
            continue
        worker_id = _selected_worker_id(summary)
        if not worker_id:
            continue
        counts[worker_id] = counts.get(worker_id, 0) + 1
    return counts


def _knowledge_dir(kind: str) -> Path:
    layout = ensure_control_plane_layout()
    if kind == "sop":
        return Path(layout["knowledge_sops"])
    if kind == "skill":
        return Path(layout["knowledge_skills"])
    raise ValueError(f"Unsupported knowledge draft kind: {kind}")


def _draft_paths(kind: str, slug: str) -> tuple[Path, Path]:
    draft_dir = _knowledge_dir(kind)
    markdown_path = draft_dir / f"{slug}.md"
    metadata_path = draft_dir / f"{slug}.md.meta.json"
    return markdown_path, metadata_path


def _draft_addendum_marker(source_run_id: str) -> str:
    return f"## Accepted Run Addendum - `{source_run_id}`"


def _strip_h1(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _is_list_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(("- ", "* ")) or bool(re.match(r"[0-9]+\.\s", stripped))


def _normalized_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def _dedupe_addendum_body(target_content: str, draft_body: str) -> str:
    existing_lines = {
        _normalized_line(line)
        for line in target_content.splitlines()
        if _is_list_line(line) and _normalized_line(line)
    }
    seen_new: set[str] = set()
    output: list[str] = []
    for line in draft_body.splitlines():
        normalized = _normalized_line(line)
        if not normalized:
            output.append(line)
            continue
        if _is_list_line(line):
            if normalized in existing_lines or normalized in seen_new:
                continue
            seen_new.add(normalized)
        elif normalized in seen_new:
            continue
        output.append(line)
    return "\n".join(output).strip()


def _queue_artifact_kind(path: Path) -> str:
    name = path.name
    if name.endswith("-draft-pr.md"):
        return "draft_pr"
    if name.endswith("-promotion-report.json"):
        return "promotion_report"
    if name.endswith("-export.json"):
        return "export"
    if name.endswith("-finalize.json"):
        return "finalize"
    if name.endswith("-prune-report.json"):
        return "prune_report"
    return "default"


def _merge_existing_target_content(
    *,
    target_content: str,
    draft_content: str,
    source_run_id: str,
    fingerprint: str,
) -> tuple[str, str]:
    marker = _draft_addendum_marker(source_run_id)
    fingerprint_marker = _draft_fingerprint_marker(fingerprint)
    if marker in target_content or fingerprint_marker in target_content:
        return target_content, "already_merged"

    draft_body = _strip_h1(draft_content)
    if not draft_body:
        draft_body = draft_content.strip()
    draft_body = _dedupe_addendum_body(target_content, draft_body)
    if not draft_body:
        return target_content, "already_merged"

    merged = (
        target_content.rstrip()
        + "\n\n---\n\n"
        + fingerprint_marker
        + "\n"
        + marker
        + "\n\n"
        + draft_body
        + "\n"
    )
    return merged, "merged_addendum"


def _log_final_report_path(run_id: str) -> Path:
    return DEFAULT_LOG_ROOT / f"{safe_run_id(run_id)}-FINAL.md"


def _verification_report_path(run_id: str) -> Path:
    return run_dir(run_id) / "report.md"


def _compact_text(value: str, limit: int = 240) -> str:
    normalized = re.sub(r"\s+", " ", value.strip())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _bullet_block(items: list[str], empty_text: str = "_None_") -> str:
    cleaned = [item for item in items if str(item).strip()]
    if not cleaned:
        return f"- {empty_text}"
    return "\n".join(f"- {item}" for item in cleaned)


def _build_sop_body(
    *,
    run_id: str,
    failure_type: str,
    summary: dict[str, Any],
    objective_component: str,
    failure_count: int,
) -> str:
    metric_key = str(summary.get("metric_key", "")).strip()
    summary_text = _compact_text(str(summary.get("summary", "")))
    intent = summary.get("intent_contract", {}) if isinstance(summary.get("intent_contract", {}), dict) else {}
    acceptance_checks = [str(item) for item in intent.get("binary_acceptance_checks", []) if str(item).strip()]
    operator_constraints = [str(item) for item in intent.get("operator_constraints", []) if str(item).strip()]
    return (
        f"# Failure Pattern: {failure_type}\n\n"
        f"Generated from accepted run `{run_id}`.\n\n"
        "## Trigger\n\n"
        f"- objective component: `{objective_component or 'unspecified'}`\n"
        f"- recurring failure type: `{failure_type}`\n"
        f"- observed failure count: `{failure_count}`\n"
        f"- metric key: `{metric_key}`\n\n"
        "## Symptoms\n\n"
        f"- accepted evidence summary: {summary_text or 'Review the accepted change and benchmark evidence for reusable repair steps.'}\n\n"
        "## Response Pattern\n\n"
        "- check the accepted run summary, telemetry, and failure artifact together before editing\n"
        "- keep the fix scoped to the component and acceptance boundary that repeated\n"
        "- prefer deterministic config or workflow hardening over ad hoc operator steps\n\n"
        "## Validation Checks\n\n"
        f"{_bullet_block(acceptance_checks, empty_text='Re-run the benchmark path that originally failed.')}\n\n"
        "## Reuse Boundary\n\n"
        f"{_bullet_block(operator_constraints, empty_text='Escalate if the next occurrence needs a broader architectural change.')}\n"
    )


def _build_skill_body(
    *,
    run_id: str,
    worker_model_id: str,
    summary: dict[str, Any],
    objective_component: str,
    accepted_run_count: int,
) -> str:
    resolved_models = summary.get("resolved_models", {})
    worker_meta = resolved_models.get("worker", {}) if isinstance(resolved_models, dict) else {}
    provider = worker_meta.get("provider", "")
    model = worker_meta.get("model", "")
    summary_text = _compact_text(str(summary.get("summary", "")))
    intent = summary.get("intent_contract", {}) if isinstance(summary.get("intent_contract", {}), dict) else {}
    non_goals = [str(item) for item in intent.get("non_goals", []) if str(item).strip()]
    acceptance_checks = [str(item) for item in intent.get("binary_acceptance_checks", []) if str(item).strip()]
    return (
        f"# Worker Pattern: {worker_model_id}\n\n"
        f"Generated from accepted run `{run_id}`.\n\n"
        "## Use When\n\n"
        f"- objective component is `{objective_component or 'unspecified'}`\n"
        f"- worker id is `{worker_model_id}`\n"
        f"- accepted run evidence count is `{accepted_run_count}`\n\n"
        "## Resolved model\n\n"
        f"- provider: `{provider or 'unknown'}`\n"
        f"- model: `{model or 'unknown'}`\n\n"
        "## Execution Pattern\n\n"
        f"- accepted evidence summary: {summary_text or 'Review the accepted run to capture worker-specific execution guidance.'}\n"
        "- keep prompts and eval scope tight around the repeated harness operation\n"
        "- prefer deterministic benchmark and finalize paths over exploratory branching\n\n"
        "## Avoid When\n\n"
        f"{_bullet_block(non_goals, empty_text='Avoid using this skill as a blanket default outside the repeated objective component.')}\n\n"
        "## Validation\n\n"
        f"{_bullet_block(acceptance_checks, empty_text='Re-run the worker-specific benchmark and finalize checks.')}\n"
    )


def _run_entry(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    harness_metadata = payload.get("harness_metadata", {})
    objective_component = str(payload.get("objective_component", "")).strip()
    if isinstance(harness_metadata, dict):
        objective_component = str(harness_metadata.get("objective_component", "")).strip() or objective_component
    return {
        "run_id": payload.get("run_id", path.parent.name),
        "summary_path": str(path),
        "run_kind": str(payload.get("run_kind", "")).strip()
        or ("verification_only" if payload.get("verification_only") else "accepted" if _is_accepted_summary(payload) else "run"),
        "objective_component": objective_component,
        "metric_key": payload.get("metric_key", ""),
        "improvements_kept": payload.get("improvements_kept", 0),
        "run_branch": payload.get("run_branch", ""),
        "export_branch": payload.get("export", {}).get("branch_name", ""),
        "pr_url": payload.get("export", {}).get("pr_url", ""),
        "report_path": payload.get("report_path", ""),
        "summary": payload.get("summary", ""),
    }


def _markdown_section(title: str, items: list[str], *, empty_text: str) -> str:
    lines = [f"## {title}", ""]
    if items:
        lines.extend(items)
    else:
        lines.append(f"- {empty_text}")
    return "\n".join(lines)


def _retention_due_soon(*, draft_limit: int, queue_limit: int, horizon_days: int = 3) -> list[dict[str, Any]]:
    layout = ensure_control_plane_layout()
    now = time.time()
    horizon_seconds = horizon_days * 86400
    due: list[dict[str, Any]] = []

    for kind in ("sop", "skill"):
        for metadata_path in sorted(_knowledge_dir(kind).glob("*.md.meta.json")):
            draft_path = Path(str(metadata_path).removesuffix(".meta.json"))
            newest_mtime = max(
                metadata_path.stat().st_mtime,
                draft_path.stat().st_mtime if draft_path.exists() else 0,
            )
            expires_at = newest_mtime + (DEFAULT_DRAFT_RETENTION_DAYS * 86400)
            if expires_at > now + horizon_seconds:
                continue
            due.append(
                {
                    "path": str(metadata_path),
                    "kind": "draft",
                    "retention_days": DEFAULT_DRAFT_RETENTION_DAYS,
                    "days_until_prune": int((expires_at - now) // 86400),
                }
            )

    queue_root = Path(layout["meta_loop"])
    for path in sorted(queue_root.glob("*")):
        if not path.is_file():
            continue
        kind = _queue_artifact_kind(path)
        retention_days = QUEUE_RETENTION_POLICY_DAYS.get(kind, QUEUE_RETENTION_POLICY_DAYS["default"])
        expires_at = path.stat().st_mtime + (retention_days * 86400)
        if expires_at > now + horizon_seconds:
            continue
        due.append(
            {
                "path": str(path),
                "kind": kind,
                "retention_days": retention_days,
                "days_until_prune": int((expires_at - now) // 86400),
            }
        )

    due.sort(key=lambda item: (item["days_until_prune"], item["path"]))
    return due[: max(draft_limit, queue_limit)]


def _render_control_plane_markdown(payload: dict[str, Any]) -> str:
    accepted_items = [
        (
            f"- `{item['run_id']}`"
            f" (`{item.get('objective_component') or 'unspecified'}`)"
            f" improvements_kept=`{item.get('improvements_kept', 0)}`"
            + (f" pr=`{item.get('pr_url', '')}`" if item.get("pr_url") else "")
        )
        for item in payload.get("recent_accepted_runs", [])
    ]
    verification_items = [
        (
            f"- `{item['run_id']}`"
            f" (`{item.get('objective_component') or 'unspecified'}`)"
            f" report=`{item.get('report_path', '') or 'missing'}`"
        )
        for item in payload.get("recent_verification_only_runs", [])
    ]
    failure_items = [
        f"- `{item['failure_type']}`: `{item['count']}` open"
        for item in payload.get("open_failures_by_type", [])
    ]
    draft_kind_items = [
        f"- `{kind}`: `{count}` pending"
        for kind, count in sorted(payload.get("pending_drafts_by_kind", {}).items())
    ]
    retention_items = [
        (
            f"- `{item['kind']}`: `{item['path']}`"
            f" (`days_until_prune={item.get('days_until_prune', 0)}`)"
        )
        for item in payload.get("retention_due_soon", [])
    ]
    sections = [
        "# Control-Plane Overview",
        "",
        _markdown_section("Recent Accepted Runs", accepted_items, empty_text="_None_"),
        "",
        _markdown_section("Recent Verification-Only Runs", verification_items, empty_text="_None_"),
        "",
        _markdown_section("Open Failures By Type", failure_items, empty_text="_None_"),
        "",
        _markdown_section("Pending Drafts By Kind", draft_kind_items, empty_text="_None_"),
        "",
        _markdown_section("Retention / Prune Due Soon", retention_items, empty_text="_None_"),
    ]
    return "\n".join(sections).strip() + "\n"


def _write_draft(
    *,
    kind: str,
    slug: str,
    body: str,
    metadata: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    markdown_path, metadata_path = _draft_paths(kind, slug)
    if not dry_run:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(body, encoding="utf-8")
        _json_dump(metadata_path, metadata)
    return {
        "draft_path": str(markdown_path),
        "metadata_path": str(metadata_path),
        "draft_kind": kind,
        "draft_id": metadata["draft_id"],
        "target_relpath": metadata["target_relpath"],
        "body_preview": body,
        "metadata_preview": metadata,
        "dry_run": dry_run,
    }


def generate_knowledge_drafts_from_run(
    run_id: str,
    *,
    objective_component: str = "",
    operator_confirmed: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    summary = load_run_summary(run_id)
    if not _is_accepted_summary(summary):
        raise RuntimeError(f"Run {run_id} has no accepted change to promote")

    failure_counts = collect_failure_counts()
    accepted_run_counts = collect_accepted_run_counts()
    objective = objective_component or str(
        summary.get("harness_metadata", {}).get("objective_component", "")
    ).strip()
    created_drafts: list[dict[str, Any]] = []

    seen_failure_types: list[str] = []
    for failure_type in summary.get("failure_causes", []):
        failure_type = str(failure_type).strip()
        if not failure_type or failure_type in seen_failure_types:
            continue
        seen_failure_types.append(failure_type)
        slug = f"failure-{_slug(failure_type)}"
        target_relpath = f"knowledge/sops/{slug}.md"
        body = _build_sop_body(
            run_id=run_id,
            failure_type=failure_type,
            summary=summary,
            objective_component=objective,
            failure_count=failure_counts.get(failure_type, 0),
        )
        metadata = {
            "draft_id": slug,
            "draft_kind": "sop",
            "title": f"Failure Pattern: {failure_type}",
            "source_run_id": run_id,
            "target_relpath": target_relpath,
            "status": "draft",
            "created_at": _now_timestamp(),
            "operator_confirmed": operator_confirmed,
            "allow_overwrite_existing": False,
            "merge_strategy": "append_run_addendum",
            "content_fingerprint": _content_fingerprint(
                "\n".join(
                    [
                        failure_type,
                        objective,
                        str(summary.get("metric_key", "")),
                        str(summary.get("summary", "")),
                    ]
                )
            ),
            "failure_types": [failure_type],
            "promotion_rules": {
                "any_of": [
                    {
                        "type": "failure_occurrences_at_least",
                        "failure_type": failure_type,
                        "count": 2,
                    },
                    {"type": "operator_confirmed"},
                ]
            },
        }
        created_drafts.append(
            _write_draft(
                kind="sop",
                slug=slug,
                body=body,
                metadata=metadata,
                dry_run=dry_run,
            )
        )

    worker_model_id = _selected_worker_id(summary)
    if worker_model_id:
        slug = f"worker-{_slug(worker_model_id)}"
        target_relpath = f"knowledge/skills/{slug}.md"
        body = _build_skill_body(
            run_id=run_id,
            worker_model_id=worker_model_id,
            summary=summary,
            objective_component=objective,
            accepted_run_count=accepted_run_counts.get(worker_model_id, 0),
        )
        metadata = {
            "draft_id": slug,
            "draft_kind": "skill",
            "title": f"Worker Pattern: {worker_model_id}",
            "source_run_id": run_id,
            "target_relpath": target_relpath,
            "status": "draft",
            "created_at": _now_timestamp(),
            "operator_confirmed": operator_confirmed,
            "allow_overwrite_existing": False,
            "merge_strategy": "append_run_addendum",
            "content_fingerprint": _content_fingerprint(
                "\n".join(
                    [
                        worker_model_id,
                        objective,
                        str(summary.get("summary", "")),
                        str(summary.get("metric_key", "")),
                    ]
                )
            ),
            "worker_model_id": worker_model_id,
            "promotion_rules": {
                "any_of": [
                    {
                        "type": "accepted_runs_at_least",
                        "worker_model_id": worker_model_id,
                        "count": 2,
                    },
                    {"type": "operator_confirmed"},
                ]
            },
        }
        created_drafts.append(
            _write_draft(
                kind="skill",
                slug=slug,
                body=body,
                metadata=metadata,
                dry_run=dry_run,
            )
        )

    return {
        "run_id": run_id,
        "dry_run": dry_run,
        "side_effects_applied": not dry_run,
        "drafts_created": created_drafts,
    }


def _iter_draft_metadata_paths(draft_kind: str | None = None) -> list[Path]:
    kinds = [draft_kind] if draft_kind else ["sop", "skill"]
    paths: list[Path] = []
    for kind in kinds:
        for path in sorted(_knowledge_dir(kind).glob("*.md.meta.json")):
            paths.append(path)
    return paths


def _evaluate_rule(
    rule: dict[str, Any],
    *,
    failure_counts: dict[str, int],
    accepted_run_counts: dict[str, int],
    operator_confirmed: bool,
    metadata: dict[str, Any],
) -> str | None:
    rule_type = rule.get("type")
    if rule_type == "failure_occurrences_at_least":
        failure_type = str(rule.get("failure_type", "")).strip()
        threshold = int(rule.get("count", 0))
        if failure_counts.get(failure_type, 0) >= threshold:
            return f"failure_occurrences:{failure_type}>={threshold}"
        return None
    if rule_type == "accepted_runs_at_least":
        worker_model_id = str(rule.get("worker_model_id", "")).strip()
        threshold = int(rule.get("count", 0))
        if accepted_run_counts.get(worker_model_id, 0) >= threshold:
            return f"accepted_runs:{worker_model_id}>={threshold}"
        return None
    if rule_type == "operator_confirmed":
        if operator_confirmed or bool(metadata.get("operator_confirmed")):
            return "operator_confirmed"
        return None
    return None


def promote_knowledge_drafts(
    *,
    run_id: str | None = None,
    draft_kind: str | None = None,
    operator_confirmed: bool = False,
    dry_run: bool = False,
    draft_specs: list[dict[str, Any]] | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    failure_counts = collect_failure_counts()
    accepted_run_counts = collect_accepted_run_counts()
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if draft_specs is None:
        draft_sources: list[dict[str, Any]] = []
        for metadata_path in _iter_draft_metadata_paths(draft_kind=draft_kind):
            metadata = _json_load(metadata_path)
            if run_id and metadata.get("source_run_id") != run_id:
                continue
            draft_path = Path(str(metadata_path).removesuffix(".meta.json"))
            if not draft_path.exists():
                skipped.append(
                    {
                        "draft_id": metadata.get("draft_id", draft_path.stem),
                        "reason": "missing_draft_markdown",
                    }
                )
                continue
            draft_sources.append(
                {
                    "metadata": metadata,
                    "metadata_path": metadata_path,
                    "draft_path": draft_path,
                    "content": draft_path.read_text(encoding="utf-8"),
                }
            )
    else:
        draft_sources = []
        for spec in draft_specs:
            metadata = dict(spec.get("metadata_preview", {}))
            if run_id and metadata.get("source_run_id") != run_id:
                continue
            if draft_kind and metadata.get("draft_kind") != draft_kind:
                continue
            draft_sources.append(
                {
                    "metadata": metadata,
                    "metadata_path": Path(spec.get("metadata_path", "")),
                    "draft_path": Path(spec.get("draft_path", "")),
                    "content": str(spec.get("body_preview", "")),
                }
            )

    for source in draft_sources:
        metadata = source["metadata"]
        metadata_path = source["metadata_path"]
        draft_path = source["draft_path"]
        reasons: list[str] = []
        for rule in metadata.get("promotion_rules", {}).get("any_of", []):
            reason = _evaluate_rule(
                rule,
                failure_counts=failure_counts,
                accepted_run_counts=accepted_run_counts,
                operator_confirmed=operator_confirmed,
                metadata=metadata,
            )
            if reason:
                reasons.append(reason)

        if not reasons:
            skipped.append(
                {
                    "draft_id": metadata.get("draft_id", draft_path.stem),
                    "reason": "promotion_rules_not_satisfied",
                }
            )
            continue

        target_path = repo / metadata["target_relpath"]
        content = source["content"]
        merged = False
        merge_result = "direct_write"
        if target_path.exists() and target_path.read_text(encoding="utf-8") != content:
            merge_strategy = metadata.get("merge_strategy", "")
            if merge_strategy == "append_run_addendum":
                content, merge_result = _merge_existing_target_content(
                    target_content=target_path.read_text(encoding="utf-8"),
                    draft_content=content,
                    source_run_id=str(metadata.get("source_run_id", "")),
                    fingerprint=str(metadata.get("content_fingerprint", "")),
                )
                merged = merge_result == "merged_addendum"
                if merge_result == "already_merged":
                    promoted.append(
                        {
                            "draft_id": metadata.get("draft_id", draft_path.stem),
                            "target_path": str(target_path),
                            "reasons": reasons + ["already_merged"],
                            "merged": False,
                        }
                    )
                    continue
            elif not metadata.get("allow_overwrite_existing", False):
                skipped.append(
                    {
                        "draft_id": metadata.get("draft_id", draft_path.stem),
                        "reason": "existing_target_conflict",
                        "target_path": str(target_path),
                    }
                )
                continue

        if not dry_run:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            metadata["status"] = "promoted"
            metadata["promoted_at"] = _now_timestamp()
            metadata["promoted_target_path"] = str(target_path)
            metadata["promotion_reasons"] = reasons
            metadata["merge_result"] = merge_result
            if metadata_path:
                _json_dump(metadata_path, metadata)

        promoted.append(
            {
                "draft_id": metadata.get("draft_id", draft_path.stem),
                "target_path": str(target_path),
                "reasons": reasons,
                "merged": merged,
            }
        )

    queue_root = Path(ensure_control_plane_layout()["meta_loop"])
    report_path = queue_root / f"{_now_timestamp()}-promotion-report.json"
    report = {
        "action": "promote_knowledge_drafts",
        "run_id": run_id,
        "draft_kind": draft_kind,
        "operator_confirmed": operator_confirmed,
        "dry_run": dry_run,
        "side_effects_applied": not dry_run,
        "promoted": promoted,
        "skipped": skipped,
    }
    report["report_path"] = ""
    if not dry_run:
        _json_dump(report_path, report)
        report["report_path"] = str(report_path)
    return report


def _close_open_failures_for_run(
    *,
    run_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    layout = ensure_control_plane_layout()
    open_root = Path(layout["failures_open"])
    closed_root = Path(layout["failures_closed"])
    closed: list[dict[str, Any]] = []

    for path in sorted(open_root.glob("*.json")):
        try:
            payload = _json_load(path)
        except Exception:
            continue
        if str(payload.get("source_run_id", "")).strip() != run_id:
            continue

        closed_path = closed_root / path.name
        if closed_path.exists():
            closed_path = closed_root / f"{path.stem}-{_now_timestamp()}.json"

        closed_payload = dict(payload)
        closed_payload["status"] = "closed"
        closed_payload["closed_by_run_id"] = run_id
        closed_payload["closed_at"] = _now_timestamp()
        if not dry_run:
            _json_dump(closed_path, closed_payload)
            path.unlink()
        closed.append(
            {
                "from_path": str(path),
                "to_path": str(closed_path),
                "failure_type": closed_payload.get("failure_type", ""),
            }
        )

    return {
        "run_id": run_id,
        "dry_run": dry_run,
        "side_effects_applied": not dry_run,
        "closed": closed,
    }


def _annotate_run_summary_with_finalize(
    *,
    run_id: str,
    promotion_result: dict[str, Any],
    failure_closure_result: dict[str, Any],
    export_result: dict[str, Any],
    finalize_path: Path,
) -> dict[str, Any]:
    path = _summary_path(run_id)
    summary_payload = load_run_summary(run_id)
    finalized_at = _now_timestamp()
    promoted_targets = [item["target_path"] for item in promotion_result.get("promoted", [])]
    summary_payload["promotion"] = {
        "report_path": promotion_result.get("report_path", ""),
        "promoted": promotion_result.get("promoted", []),
        "skipped": promotion_result.get("skipped", []),
    }
    summary_payload["failure_closure"] = failure_closure_result
    summary_payload["export"] = export_result
    summary_payload["finalization"] = {
        "finalized_at": finalized_at,
        "finalize_path": str(finalize_path),
    }

    export_block = (
        f"Meta-loop export: branch={export_result.get('branch_name', '')}, "
        f"pr_url={export_result.get('pr_url', '')}, "
        f"promoted_targets={len(promoted_targets)}"
    )
    summary_text = str(summary_payload.get("summary", "")).strip()
    if export_block not in summary_text:
        summary_payload["summary"] = f"{summary_text}\n\n{export_block}".strip()

    _json_dump(path, summary_payload)

    append_jsonl(
        path.parent / "telemetry.jsonl",
        {
            "event_type": "meta_loop_finalize",
            "timestamp": finalized_at,
            "run_id": run_id,
            "promotion": summary_payload["promotion"],
            "failure_closure": failure_closure_result,
            "export": export_result,
            "finalization": summary_payload["finalization"],
        },
    )

    log_path = _log_final_report_path(run_id)
    if log_path.exists():
        marker = "## Meta-Loop Export"
        log_content = log_path.read_text(encoding="utf-8")
        if marker not in log_content:
            promoted_block = "\n".join(f"- `{item}`" for item in promoted_targets) or "- _None_"
            log_content = (
                log_content.rstrip()
                + "\n\n"
                + marker
                + "\n\n"
                + f"- `branch_name`: `{export_result.get('branch_name', '')}`\n"
                + f"- `pr_url`: `{export_result.get('pr_url', '')}`\n"
                + "### Promoted Targets\n"
                + promoted_block
                + "\n"
            )
            log_path.write_text(log_content, encoding="utf-8")

    return summary_payload


def inspect_control_plane(
    *,
    run_limit: int = 5,
    failure_limit: int = 10,
    draft_limit: int = 10,
    queue_limit: int = 10,
    format: str = "json",
) -> dict[str, Any]:
    layout = ensure_control_plane_layout()
    runs_root = Path(layout["runs"])
    open_failures_root = Path(layout["failures_open"])
    queue_root = Path(layout["meta_loop"])

    recent_runs = []
    recent_accepted_runs = []
    recent_verification_only_runs = []
    run_summaries = sorted(runs_root.glob("*/summary.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in run_summaries:
        try:
            payload = _json_load(path)
        except Exception:
            continue
        entry = _run_entry(path, payload)
        recent_runs.append(entry)
        if entry["run_kind"] == "verification_only":
            recent_verification_only_runs.append(entry)
        elif _is_accepted_summary(payload):
            recent_accepted_runs.append(entry)
    recent_runs = recent_runs[:run_limit]
    recent_accepted_runs = recent_accepted_runs[:run_limit]
    recent_verification_only_runs = recent_verification_only_runs[:run_limit]

    open_failures = []
    open_failures_by_type: dict[str, int] = {}
    for path in sorted(open_failures_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:failure_limit]:
        try:
            payload = _json_load(path)
        except Exception:
            continue
        failure_type = payload.get("failure_type", "")
        open_failures.append(
            {
                "path": str(path),
                "failure_type": failure_type,
                "component": payload.get("component", ""),
                "source_run_id": payload.get("source_run_id", ""),
            }
        )
        if failure_type:
            open_failures_by_type[str(failure_type)] = open_failures_by_type.get(str(failure_type), 0) + 1

    pending_drafts = []
    pending_drafts_by_kind: dict[str, int] = {}
    for kind in ("sop", "skill"):
        for path in sorted(_knowledge_dir(kind).glob("*.md.meta.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            payload = _json_load(path)
            if payload.get("status") == "promoted":
                continue
            pending_drafts_by_kind[kind] = pending_drafts_by_kind.get(kind, 0) + 1
            pending_drafts.append(
                {
                    "draft_id": payload.get("draft_id", path.stem),
                    "draft_kind": payload.get("draft_kind", kind),
                    "source_run_id": payload.get("source_run_id", ""),
                    "metadata_path": str(path),
                }
            )
    pending_drafts = pending_drafts[:draft_limit]

    recent_queue = []
    for path in sorted(queue_root.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True)[:queue_limit]:
        if not path.is_file():
            continue
        recent_queue.append(
            {
                "path": str(path),
                "kind": _queue_artifact_kind(path),
            }
        )

    current_selection_path = Path(layout["root"]) / "current-selection.json"
    current_selection = _json_load(current_selection_path) if current_selection_path.exists() else {}

    payload = {
        "format": "json",
        "recent_runs": recent_runs,
        "recent_accepted_runs": recent_accepted_runs,
        "recent_verification_only_runs": recent_verification_only_runs,
        "open_failures": open_failures,
        "open_failures_by_type": [
            {"failure_type": failure_type, "count": count}
            for failure_type, count in sorted(open_failures_by_type.items(), key=lambda item: (-item[1], item[0]))
        ],
        "pending_drafts": pending_drafts,
        "pending_drafts_by_kind": pending_drafts_by_kind,
        "recent_queue": recent_queue,
        "retention_due_soon": _retention_due_soon(draft_limit=draft_limit, queue_limit=queue_limit),
        "retention_policy_days": queue_retention_policy_days(),
        "current_selection": current_selection,
    }
    if format == "markdown":
        payload["format"] = "markdown"
        payload["content"] = _render_control_plane_markdown(payload)
    return payload


def _build_verification_only_report(
    *,
    run_id: str,
    objective_component: str,
    benchmark_command: str,
    metric_key: str,
    metric_value: float,
    summary: str,
    working_directory: str,
    branch_name: str,
    finalize_skipped_reason: str,
) -> str:
    return (
        "# Verification-Only Run Report\n\n"
        "## Run\n\n"
        f"- run id: `{run_id}`\n"
        f"- objective component: `{objective_component or 'unspecified'}`\n"
        f"- branch: `{branch_name or 'unspecified'}`\n\n"
        "## Benchmark\n\n"
        f"- command: `{benchmark_command}`\n"
        f"- metric: `{metric_key}`\n"
        f"- value: `{metric_value}`\n"
        f"- working directory: `{working_directory}`\n\n"
        "## Outcome\n\n"
        f"- summary: {summary}\n"
        f"- finalize skipped reason: {finalize_skipped_reason}\n"
        "- export: not executed\n"
        "- knowledge promotion: not executed\n"
    )


def record_verification_only_run(
    *,
    run_id: str,
    objective_component: str,
    benchmark_command: str,
    metric_key: str,
    metric_value: float,
    summary: str,
    working_directory: str,
    branch_name: str = "",
    finalize_skipped_reason: str = "",
) -> dict[str, Any]:
    run_path = run_dir(run_id)
    recorded_at = _now_timestamp()
    report_path = _verification_report_path(run_id)
    skip_reason = (
        finalize_skipped_reason.strip()
        or "verification-only run recorded without an accepted patch; finalize/export skipped"
    )
    report_content = _build_verification_only_report(
        run_id=run_id,
        objective_component=objective_component,
        benchmark_command=benchmark_command,
        metric_key=metric_key,
        metric_value=metric_value,
        summary=summary,
        working_directory=working_directory,
        branch_name=branch_name,
        finalize_skipped_reason=skip_reason,
    )
    report_path.write_text(report_content, encoding="utf-8")
    benchmark_result = {
        "iteration": 0,
        "decision": "verification_only",
        "metric_key": metric_key,
        "metric_value": metric_value,
        "summary": summary,
        "benchmark_command": benchmark_command,
    }
    payload = {
        "run_id": run_id,
        "run_kind": "verification_only",
        "verification_only": True,
        "objective_component": objective_component,
        "benchmark_command": benchmark_command,
        "metric_key": metric_key,
        "metric_value": metric_value,
        "summary": summary,
        "working_directory": working_directory,
        "branch_name": branch_name,
        "harness_metadata": {"objective_component": objective_component} if objective_component else {},
        "report_path": str(report_path),
        "finalize_skipped_reason": skip_reason,
        "benchmark_results": [benchmark_result],
        "recorded_at": recorded_at,
    }
    summary_path = run_path / "summary.json"
    if summary_path.exists():
        existing = _json_load(summary_path)
        existing["run_kind"] = "verification_only"
        existing["verification_only"] = True
        existing["objective_component"] = objective_component
        existing["summary"] = summary
        existing["benchmark_command"] = benchmark_command
        existing["metric_key"] = metric_key
        existing["metric_value"] = metric_value
        existing["final_metric"] = metric_value
        existing["working_directory"] = working_directory
        existing["run_branch"] = branch_name or existing.get("run_branch", "")
        existing["verification_recorded_at"] = recorded_at
        existing["report_path"] = str(report_path)
        existing["finalize_skipped_reason"] = skip_reason
        harness_metadata = existing.get("harness_metadata")
        if not isinstance(harness_metadata, dict):
            harness_metadata = {}
        if objective_component:
            harness_metadata["objective_component"] = objective_component
        if harness_metadata:
            existing["harness_metadata"] = harness_metadata
        benchmark_results = existing.get("benchmark_results")
        if not isinstance(benchmark_results, list):
            benchmark_results = []
        benchmark_results = [item for item in benchmark_results if item.get("decision") != "verification_only"]
        benchmark_results.append(benchmark_result)
        existing["benchmark_results"] = benchmark_results
        _json_dump(summary_path, existing)
        payload["summary_path"] = str(summary_path)
        payload["summary_payload"] = existing
    else:
        payload["summary_path"] = str(summary_path)
        _json_dump(summary_path, payload)
        payload["summary_payload"] = payload.copy()

    append_jsonl(
        run_path / "telemetry.jsonl",
        {
            "event_type": "verification_only",
            "timestamp": payload["recorded_at"],
            "run_id": run_id,
            "objective_component": objective_component,
            "benchmark_command": benchmark_command,
            "metric_key": metric_key,
            "metric_value": metric_value,
            "summary": summary,
            "branch_name": branch_name,
            "report_path": str(report_path),
            "finalize_skipped_reason": skip_reason,
        },
    )
    return payload


def prune_stale_control_plane_artifacts(
    *,
    max_age_days: int = 0,
    include_drafts: bool = True,
    include_queue: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    layout = ensure_control_plane_layout()
    now = time.time()
    removed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    retention_policy = {
        "drafts": DEFAULT_DRAFT_RETENTION_DAYS if max_age_days <= 0 else max_age_days,
        "queue": dict(QUEUE_RETENTION_POLICY_DAYS) if max_age_days <= 0 else {"default": max_age_days},
    }

    if include_drafts:
        for kind in ("sop", "skill"):
            for metadata_path in sorted(_knowledge_dir(kind).glob("*.md.meta.json")):
                draft_path = Path(str(metadata_path).removesuffix(".meta.json"))
                draft_exists = draft_path.exists()
                newest_mtime = max(
                    metadata_path.stat().st_mtime,
                    draft_path.stat().st_mtime if draft_exists else 0,
                )
                draft_retention_days = retention_policy["drafts"]
                if newest_mtime >= now - (draft_retention_days * 86400):
                    skipped.append(
                        {
                            "path": str(metadata_path),
                            "reason": f"within_retention:{draft_retention_days}",
                        }
                    )
                    continue
                if not dry_run:
                    if draft_exists:
                        draft_path.unlink()
                    metadata_path.unlink()
                removed.append({"path": str(metadata_path), "kind": "draft_metadata"})
                if draft_exists or dry_run:
                    removed.append({"path": str(draft_path), "kind": "draft_markdown"})

    if include_queue:
        queue_root = Path(layout["meta_loop"])
        for path in sorted(queue_root.glob("*")):
            if not path.is_file():
                continue
            queue_kind = _queue_artifact_kind(path)
            queue_retention_days = retention_policy["queue"].get(
                queue_kind,
                retention_policy["queue"].get("default", DEFAULT_DRAFT_RETENTION_DAYS),
            )
            if path.stat().st_mtime >= now - (queue_retention_days * 86400):
                skipped.append(
                    {
                        "path": str(path),
                        "reason": f"within_retention:{queue_retention_days}",
                    }
                )
                continue
            if not dry_run:
                path.unlink()
            removed.append({"path": str(path), "kind": "queue_entry", "queue_kind": queue_kind})

    report = {
        "action": "prune_stale_control_plane_artifacts",
        "max_age_days": max_age_days,
        "include_drafts": include_drafts,
        "include_queue": include_queue,
        "dry_run": dry_run,
        "side_effects_applied": not dry_run,
        "retention_policy_days": retention_policy,
        "removed": removed,
        "skipped": skipped,
    }
    report["report_path"] = ""
    if not dry_run:
        queue_root = Path(layout["meta_loop"])
        report_path = queue_root / f"{_now_timestamp()}-prune-report.json"
        _json_dump(report_path, report)
        report["report_path"] = str(report_path)
    return report


def _run_cmd(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _local_branch_exists(repo: Path, branch_name: str) -> bool:
    result = _run_cmd(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
        cwd=repo,
        check=False,
    )
    return result.returncode == 0


def _build_pr_body(
    *,
    run_id: str,
    objective_component: str,
    summary_payload: dict[str, Any],
    promoted_targets: list[str],
) -> str:
    selected_model_ids = summary_payload.get("selected_model_ids", {})
    resolved_models = summary_payload.get("resolved_models", {})
    promoted_block = "\n".join(f"- `{path}`" for path in promoted_targets) or "- _None_"
    selected_models_json = json.dumps(
        {
            "selected_model_ids": selected_model_ids,
            "resolved_models": resolved_models,
        },
        indent=2,
        ensure_ascii=False,
    )
    template_text = ""
    if META_LOOP_PR_TEMPLATE_PATH.exists():
        template_text = META_LOOP_PR_TEMPLATE_PATH.read_text(encoding="utf-8")
    else:
        template_text = (
            "## Merge Intent\n\n"
            "$merge_intent\n\n"
            "## What Changed\n\n"
            "$what_changed\n\n"
            "## Why\n\n"
            "$why\n\n"
            "## Impact\n\n"
            "$impact\n\n"
            "## Root Cause\n\n"
            "$root_cause\n\n"
            "## Validation\n\n"
            "$validation\n"
        )
    return Template(template_text).safe_substitute(
        merge_intent=(
            "Reference proof only. Not intended for merge.\n\n"
            "Primary structure PR: #6."
        ),
        what_changed=(
            f"- accepted run id: `{run_id}`\n"
            f"- objective component: `{objective_component or 'unspecified'}`\n"
            f"- metric key: `{summary_payload.get('metric_key', '')}`\n"
            f"- improvements kept: `{summary_payload.get('improvements_kept', 0)}`"
        ),
        why=summary_payload.get("summary", ""),
        impact=(
            "Promoted knowledge:\n"
            f"{promoted_block}\n\n"
            "Selected models:\n"
            f"```json\n{selected_models_json}\n```"
        ),
        root_cause=(
            "This PR was generated from an accepted meta-loop run and uses the standardized "
            "control-plane export flow."
        ),
        validation="- control-plane accepted-run export completed successfully",
    )


def export_meta_loop_change(
    run_id: str,
    *,
    objective_component: str = "",
    base_branch: str = "main",
    branch_name: str = "",
    commit_message: str = "",
    pr_title: str = "",
    pr_summary: str = "",
    promoted_targets: list[str] | None = None,
    dry_run: bool = False,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    summary_payload = load_run_summary(run_id)
    objective = objective_component or str(
        summary_payload.get("harness_metadata", {}).get("objective_component", "")
    ).strip()
    if not objective:
        objective = "harness"

    sanitized_branch = (
        _normalize_requested_branch_name(branch_name, run_id)
        if branch_name.strip()
        else _default_meta_loop_branch_name(objective, run_id)
    )

    commit_message = commit_message or f"meta-loop: accept {objective} run {run_id}"
    pr_title = pr_title or f"meta-loop: {objective} accepted change ({run_id})"

    _run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    source_head = _run_cmd(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    current_branch = _run_cmd(["git", "branch", "--show-current"], cwd=repo).stdout.strip()
    dirty = bool(_run_cmd(["git", "status", "--porcelain"], cwd=repo).stdout.strip())
    branch_preexisting = _local_branch_exists(repo, sanitized_branch)

    if current_branch == base_branch and not dirty:
        raise RuntimeError(
            "Refusing to export from a clean base branch. An accepted meta-loop change must exist before PR export."
        )

    if current_branch != sanitized_branch:
        if not dry_run:
            _run_cmd(["git", "switch", "-C", sanitized_branch, source_head], cwd=repo)

    if dirty and not dry_run:
        _run_cmd(["git", "add", "-A"], cwd=repo)
        staged_result = _run_cmd(["git", "diff", "--cached", "--quiet"], cwd=repo, check=False)
        if staged_result.returncode != 0:
            _run_cmd(["git", "commit", "-m", commit_message], cwd=repo)

    head_commit = _run_cmd(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip() if not dry_run else source_head
    _run_cmd(["git", "remote", "get-url", "origin"], cwd=repo)

    queue_root = Path(ensure_control_plane_layout()["meta_loop"])
    pr_body_path = queue_root / f"{_now_timestamp()}-{safe_run_id(run_id)}-draft-pr.md"
    body_content = _build_pr_body(
        run_id=run_id,
        objective_component=objective,
        summary_payload={
            **summary_payload,
            "summary": pr_summary or summary_payload.get("summary", ""),
        },
        promoted_targets=promoted_targets or [],
    )
    if not dry_run:
        pr_body_path.write_text(body_content, encoding="utf-8")

    pr_url = "dry-run"
    pr_body_path_value = ""
    queue_entry_path_value = ""
    if not dry_run:
        push_args = ["git", "push", "-u", "origin", sanitized_branch]
        if branch_preexisting:
            push_args.insert(2, "--force-with-lease")
        _run_cmd(push_args, cwd=repo)
        pr_result = _run_cmd(
            [
                "gh",
                "pr",
                "create",
                "--draft",
                "--base",
                base_branch,
                "--head",
                sanitized_branch,
                "--title",
                pr_title,
                "--body-file",
                str(pr_body_path),
            ],
            cwd=repo,
            check=False,
        )
        if pr_result.returncode == 0:
            pr_url = pr_result.stdout.strip().splitlines()[-1].strip()
        else:
            view_result = _run_cmd(
                ["gh", "pr", "view", sanitized_branch, "--json", "url", "-q", ".url"],
                cwd=repo,
                check=False,
            )
            if view_result.returncode == 0 and view_result.stdout.strip():
                pr_url = view_result.stdout.strip()
            else:
                raise RuntimeError(
                    "Failed to create draft PR.\n"
                    f"stdout:\n{pr_result.stdout}\n"
                    f"stderr:\n{pr_result.stderr}"
                )

    queue_entry_path = queue_root / f"{_now_timestamp()}-{safe_run_id(run_id)}-export.json"
    queue_entry = {
        "action": "export_meta_loop_change",
        "run_id": run_id,
        "dry_run": dry_run,
        "side_effects_applied": not dry_run,
        "objective_component": objective,
        "branch_name": sanitized_branch,
        "head_commit": head_commit,
        "base_branch": base_branch,
        "pr_title": pr_title,
        "pr_url": pr_url,
        "promoted_targets": promoted_targets or [],
        "summary_path": str(_summary_path(run_id)),
        "pr_body_path": "",
    }
    if not dry_run:
        _json_dump(queue_entry_path, queue_entry)
        pr_body_path_value = str(pr_body_path)
        queue_entry_path_value = str(queue_entry_path)
        queue_entry["pr_body_path"] = pr_body_path_value

    queue_entry["queue_entry_path"] = queue_entry_path_value
    return queue_entry


def finalize_accepted_meta_loop_run(
    run_id: str,
    *,
    objective_component: str = "",
    base_branch: str = "main",
    branch_name: str = "",
    commit_message: str = "",
    pr_title: str = "",
    pr_summary: str = "",
    operator_confirmed: bool = False,
    dry_run: bool = False,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    summary = load_run_summary(run_id)
    if not _is_accepted_summary(summary):
        raise RuntimeError(f"Run {run_id} does not contain an accepted change")

    draft_result = generate_knowledge_drafts_from_run(
        run_id,
        objective_component=objective_component,
        operator_confirmed=operator_confirmed,
        dry_run=dry_run,
    )
    promotion_result = promote_knowledge_drafts(
        run_id=run_id,
        operator_confirmed=operator_confirmed,
        dry_run=dry_run,
        draft_specs=draft_result["drafts_created"] if dry_run else None,
        repo_root=repo_root,
    )
    promoted_targets = [item["target_path"] for item in promotion_result.get("promoted", [])]
    failure_closure_result = _close_open_failures_for_run(
        run_id=run_id,
        dry_run=dry_run,
    )
    export_result = export_meta_loop_change(
        run_id,
        objective_component=objective_component,
        base_branch=base_branch,
        branch_name=branch_name,
        commit_message=commit_message,
        pr_title=pr_title,
        pr_summary=pr_summary,
        promoted_targets=promoted_targets,
        dry_run=dry_run,
        repo_root=repo_root,
    )

    queue_root = Path(ensure_control_plane_layout()["meta_loop"])
    finalize_path = queue_root / f"{_now_timestamp()}-{safe_run_id(run_id)}-finalize.json"
    if dry_run:
        summary_payload = load_run_summary(run_id)
    else:
        summary_payload = _annotate_run_summary_with_finalize(
            run_id=run_id,
            promotion_result=promotion_result,
            failure_closure_result=failure_closure_result,
            export_result=export_result,
            finalize_path=finalize_path,
        )
    result = {
        "run_id": run_id,
        "dry_run": dry_run,
        "side_effects_applied": not dry_run,
        "drafts_created": draft_result["drafts_created"],
        "promotion_report_path": promotion_result["report_path"],
        "promoted_targets": promoted_targets,
        "failure_closure": failure_closure_result,
        "export": export_result,
        "summary_path": str(_summary_path(run_id)),
        "summary_payload": summary_payload,
        "promotion": promotion_result,
    }
    result["finalize_path"] = ""
    if not dry_run:
        _json_dump(finalize_path, result)
        result["finalize_path"] = str(finalize_path)
    return result
