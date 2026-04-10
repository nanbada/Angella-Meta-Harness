#!/usr/bin/env python3
"""Automation helpers for accepted harness meta-loop runs."""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from control_plane import append_jsonl, ensure_control_plane_layout, run_dir, safe_run_id


ANGELLA_ROOT = Path(__file__).resolve().parent.parent
TELEMETRY_DIR = ANGELLA_ROOT / "telemetry"
LOGS_DIR = TELEMETRY_DIR / "logs"
ERRORS_DIR = TELEMETRY_DIR / "errors"
DEFAULT_LOG_ROOT = LOGS_DIR / "harness_activity"


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


def _merge_existing_target_content(
    *,
    target_content: str,
    draft_content: str,
    source_run_id: str,
) -> tuple[str, str]:
    marker = _draft_addendum_marker(source_run_id)
    if marker in target_content:
        return target_content, "already_merged"

    draft_body = _strip_h1(draft_content)
    if not draft_body:
        draft_body = draft_content.strip()

    merged = (
        target_content.rstrip()
        + "\n\n---\n\n"
        + marker
        + "\n\n"
        + draft_body
        + "\n"
    )
    return merged, "merged_addendum"


def _log_final_report_path(run_id: str) -> Path:
    return DEFAULT_LOG_ROOT / f"{safe_run_id(run_id)}-FINAL.md"


def _build_sop_body(
    *,
    run_id: str,
    failure_type: str,
    summary: dict[str, Any],
    objective_component: str,
    failure_count: int,
) -> str:
    metric_key = summary.get("metric_key", "")
    summary_text = summary.get("summary", "")
    return (
        f"# Failure Pattern: {failure_type}\n\n"
        f"Generated from accepted run `{run_id}`.\n\n"
        "## Context\n\n"
        f"- objective component: `{objective_component or 'unspecified'}`\n"
        f"- recurring failure type: `{failure_type}`\n"
        f"- observed failure count: `{failure_count}`\n"
        f"- metric key: `{metric_key}`\n\n"
        "## Reusable pattern\n\n"
        f"{summary_text or 'Review the accepted change and benchmark evidence for reusable repair steps.'}\n\n"
        "## Promotion notes\n\n"
        "- Review the linked failure artifacts before broad reuse.\n"
        "- Update this SOP if a later accepted run tightens the fix boundaries.\n"
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
    summary_text = summary.get("summary", "")
    return (
        f"# Worker Pattern: {worker_model_id}\n\n"
        f"Generated from accepted run `{run_id}`.\n\n"
        "## Recommended when\n\n"
        f"- objective component is `{objective_component or 'unspecified'}`\n"
        f"- worker id is `{worker_model_id}`\n"
        f"- accepted run evidence count is `{accepted_run_count}`\n\n"
        "## Resolved model\n\n"
        f"- provider: `{provider or 'unknown'}`\n"
        f"- model: `{model or 'unknown'}`\n\n"
        "## Reusable pattern\n\n"
        f"{summary_text or 'Review the accepted run to capture worker-specific execution guidance.'}\n\n"
        "## Promotion notes\n\n"
        "- Prefer promotion only when the accepted fix repeats across runs or the operator confirms reuse.\n"
        "- Keep the skill scoped to the worker-specific behavior that actually repeated.\n"
    )


def _write_draft(
    *,
    kind: str,
    slug: str,
    body: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    markdown_path, metadata_path = _draft_paths(kind, slug)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(body, encoding="utf-8")
    _json_dump(metadata_path, metadata)
    return {
        "draft_path": str(markdown_path),
        "metadata_path": str(metadata_path),
        "draft_kind": kind,
        "draft_id": metadata["draft_id"],
        "target_relpath": metadata["target_relpath"],
    }


def generate_knowledge_drafts_from_run(
    run_id: str,
    *,
    objective_component: str = "",
    operator_confirmed: bool = False,
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
        created_drafts.append(_write_draft(kind="sop", slug=slug, body=body, metadata=metadata))

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
        created_drafts.append(_write_draft(kind="skill", slug=slug, body=body, metadata=metadata))

    return {
        "run_id": run_id,
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
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    failure_counts = collect_failure_counts()
    accepted_run_counts = collect_accepted_run_counts()
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

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
        content = draft_path.read_text(encoding="utf-8")
        merged = False
        merge_result = "direct_write"
        if target_path.exists() and target_path.read_text(encoding="utf-8") != content:
            merge_strategy = metadata.get("merge_strategy", "")
            if merge_strategy == "append_run_addendum":
                content, merge_result = _merge_existing_target_content(
                    target_content=target_path.read_text(encoding="utf-8"),
                    draft_content=content,
                    source_run_id=str(metadata.get("source_run_id", "")),
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
        "promoted": promoted,
        "skipped": skipped,
    }
    if not dry_run:
        _json_dump(report_path, report)

    report["report_path"] = str(report_path)
    return report


def _annotate_run_summary_with_finalize(
    *,
    run_id: str,
    promotion_result: dict[str, Any],
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


def prune_stale_control_plane_artifacts(
    *,
    max_age_days: int = 7,
    include_drafts: bool = True,
    include_queue: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    layout = ensure_control_plane_layout()
    cutoff = time.time() - (max_age_days * 86400)
    removed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if include_drafts:
        for kind in ("sop", "skill"):
            for metadata_path in sorted(_knowledge_dir(kind).glob("*.md.meta.json")):
                draft_path = Path(str(metadata_path).removesuffix(".meta.json"))
                draft_exists = draft_path.exists()
                newest_mtime = max(
                    metadata_path.stat().st_mtime,
                    draft_path.stat().st_mtime if draft_exists else 0,
                )
                if newest_mtime >= cutoff:
                    skipped.append({"path": str(metadata_path), "reason": "recent"})
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
            if path.stat().st_mtime >= cutoff:
                skipped.append({"path": str(path), "reason": "recent"})
                continue
            if not dry_run:
                path.unlink()
            removed.append({"path": str(path), "kind": "queue_entry"})

    report = {
        "action": "prune_stale_control_plane_artifacts",
        "max_age_days": max_age_days,
        "include_drafts": include_drafts,
        "include_queue": include_queue,
        "dry_run": dry_run,
        "removed": removed,
        "skipped": skipped,
    }
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
    return (
        f"# Harness Meta-Loop Export\n\n"
        f"- `run_id`: `{run_id}`\n"
        f"- `objective_component`: `{objective_component or 'unspecified'}`\n"
        f"- `metric_key`: `{summary_payload.get('metric_key', '')}`\n"
        f"- `improvements_kept`: `{summary_payload.get('improvements_kept', 0)}`\n\n"
        "## Accepted Summary\n\n"
        f"{summary_payload.get('summary', '')}\n\n"
        "## Selected Models\n\n"
        "```json\n"
        f"{json.dumps({'selected_model_ids': selected_model_ids, 'resolved_models': resolved_models}, indent=2, ensure_ascii=False)}\n"
        "```\n\n"
        "## Promoted Knowledge\n\n"
        f"{promoted_block}\n"
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

    sanitized_branch = branch_name.strip() if branch_name else ""
    if not sanitized_branch:
        sanitized_branch = f"codex/meta-loop-{_slug(objective)}-{safe_run_id(run_id)}"
    elif not sanitized_branch.startswith("codex/"):
        sanitized_branch = f"codex/{_slug(sanitized_branch)}"

    commit_message = commit_message or f"meta-loop: accept {objective} run {run_id}"
    pr_title = pr_title or f"meta-loop: {objective} accepted change ({run_id})"

    _run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    current_branch = _run_cmd(["git", "branch", "--show-current"], cwd=repo).stdout.strip()
    dirty = bool(_run_cmd(["git", "status", "--porcelain"], cwd=repo).stdout.strip())

    if current_branch == base_branch and not dirty:
        raise RuntimeError(
            "Refusing to export from a clean base branch. An accepted meta-loop change must exist before PR export."
        )

    if current_branch != sanitized_branch:
        if _local_branch_exists(repo, sanitized_branch):
            _run_cmd(["git", "switch", sanitized_branch], cwd=repo)
        else:
            _run_cmd(["git", "switch", "-c", sanitized_branch], cwd=repo)

    if dirty:
        _run_cmd(["git", "add", "-A"], cwd=repo)
        staged_result = _run_cmd(["git", "diff", "--cached", "--quiet"], cwd=repo, check=False)
        if staged_result.returncode != 0 and not dry_run:
            _run_cmd(["git", "commit", "-m", commit_message], cwd=repo)

    head_commit = _run_cmd(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
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
    if not dry_run:
        _run_cmd(["git", "push", "-u", "origin", sanitized_branch], cwd=repo)
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
        "objective_component": objective,
        "branch_name": sanitized_branch,
        "head_commit": head_commit,
        "base_branch": base_branch,
        "pr_title": pr_title,
        "pr_url": pr_url,
        "promoted_targets": promoted_targets or [],
        "summary_path": str(_summary_path(run_id)),
        "pr_body_path": str(pr_body_path),
    }
    if not dry_run:
        _json_dump(queue_entry_path, queue_entry)

    queue_entry["queue_entry_path"] = str(queue_entry_path)
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
    promote: bool = False,
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
    )

    promotion_result: dict[str, Any] = {"promoted": [], "skipped": [], "report_path": ""}
    if promote:
        promotion_result = promote_knowledge_drafts(
            run_id=run_id,
            operator_confirmed=operator_confirmed,
            dry_run=dry_run,
            repo_root=repo_root,
        )

    promoted_targets = [item["target_path"] for item in promotion_result.get("promoted", [])]
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
            export_result=export_result,
            finalize_path=finalize_path,
        )
    result = {
        "run_id": run_id,
        "drafts_created": draft_result["drafts_created"],
        "promotion_report_path": promotion_result["report_path"],
        "promoted_targets": promoted_targets,
        "export": export_result,
        "summary_path": str(_summary_path(run_id)),
        "summary_payload": summary_payload,
    }
    if not dry_run:
        _json_dump(finalize_path, result)
    result["finalize_path"] = str(finalize_path)
    return result
