#!/usr/bin/env python3
"""Automation helpers for accepted harness meta-loop runs."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from string import Template
from typing import Any

from control_plane import append_jsonl, ensure_control_plane_layout, run_dir, safe_run_id
from output_compactor import compact_output, telemetry_block


ANGELLA_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_ROOT = ANGELLA_ROOT / "logs" / "Goose Logs"
META_LOOP_PR_TEMPLATE_PATH = ANGELLA_ROOT / "templates" / "meta-loop-pr.md.tmpl"
KNOWLEDGE_POLICY_PATH = ANGELLA_ROOT / "config" / "knowledge-policy.yaml"
PARITY_PATH = ANGELLA_ROOT / "PARITY.md"
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
DEFAULT_COMPONENT_ORDER = (
    "setup-check",
    "setup-yes-warm",
    "setup-yes-cold",
    "profile-resolution",
    "recipe-runtime",
)


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
        payload["_summary_mtime"] = path.stat().st_mtime
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


def _knowledge_policy(repo_root: str | Path | None = None) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    defaults = {
        "indexed_paths": [
            "knowledge",
            "docs/current-harness-status.md",
            "docs/setup-installer-architecture.md",
            "docs/hybrid-harness.md",
            "docs/promotion-content-quality.md",
            "PARITY.md",
        ],
        "canonical_entrypoints": [
            "knowledge/index.md",
            "knowledge/log.md",
        ],
        "search_provider": "builtin",
        "default_max_results": 5,
        "snippet_chars": 240,
        "compaction_budget_chars": 600,
        "log_tail_entries": 5,
    }
    path = repo / "config" / "knowledge-policy.yaml"
    if not path.exists():
        return defaults
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defaults
    if isinstance(payload.get("knowledge_policy"), dict):
        payload = payload["knowledge_policy"]
    if not isinstance(payload, dict):
        return defaults
    merged = dict(defaults)
    for key, value in payload.items():
        if value not in (None, ""):
            merged[key] = value
    return merged


def _wiki_index_db_path() -> Path:
    return Path(ensure_control_plane_layout()["root"]) / "wiki-index.sqlite"


def _knowledge_sync_state_path() -> Path:
    return Path(ensure_control_plane_layout()["root"]) / "knowledge-sync.json"


def _tracked_component_dir(repo: Path) -> Path:
    return repo / "knowledge" / "components"


def _tracked_query_dir(repo: Path) -> Path:
    return repo / "knowledge" / "queries"


def _tracked_source_dir(repo: Path) -> Path:
    return repo / "knowledge" / "sources"


def _tracked_index_path(repo: Path) -> Path:
    return repo / "knowledge" / "index.md"


def _tracked_log_path(repo: Path) -> Path:
    return repo / "knowledge" / "log.md"


def _tracked_source_index_path(repo: Path) -> Path:
    return _tracked_source_dir(repo) / "index.md"


def _component_sort_key(component: str) -> tuple[int, str]:
    if component in DEFAULT_COMPONENT_ORDER:
        return (DEFAULT_COMPONENT_ORDER.index(component), component)
    return (len(DEFAULT_COMPONENT_ORDER), component)


def _component_ids_from_summaries(summaries: list[dict[str, Any]]) -> list[str]:
    seen = set(DEFAULT_COMPONENT_ORDER)
    for summary in summaries:
        objective = ""
        harness = summary.get("harness_metadata", {})
        if isinstance(harness, dict):
            objective = str(harness.get("objective_component", "")).strip()
        objective = objective or str(summary.get("objective_component", "")).strip()
        if objective:
            seen.add(objective)
    return sorted(seen, key=_component_sort_key)


def _relative_link(from_path: Path, target_path: Path) -> str:
    return os.path.relpath(target_path, start=from_path.parent).replace(os.sep, "/")


def _markdown_link(from_path: Path, target_path: Path, label: str | None = None) -> str:
    return f"[{label or target_path.name}]({_relative_link(from_path, target_path)})"


def _write_text_if_changed(path: Path, content: str, *, dry_run: bool) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return True


def _markdown_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()


def _markdown_summary(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped
    return ""


def _source_id_for_relpath(relpath: str) -> str:
    return f"source-{_slug(relpath.replace('/', '-'))}"


def _source_page_path(repo: Path, relpath: str) -> Path:
    return _tracked_source_dir(repo) / f"{_source_id_for_relpath(relpath)}.md"


def _query_page_path(repo: Path, slug: str) -> Path:
    return _tracked_query_dir(repo) / f"{slug}.md"


def _policy_entry_paths(repo: Path) -> list[Path]:
    policy = _knowledge_policy(repo)
    entries: list[Path] = []
    for relpath in policy.get("canonical_entrypoints", []):
        path = repo / relpath
        if path.exists():
            entries.append(path)
    parity = repo / "PARITY.md"
    if parity.exists():
        entries.append(parity)
    source_index = _tracked_source_index_path(repo)
    if source_index.exists():
        entries.append(source_index)
    return entries


def _source_specs(repo: Path, summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in _iter_policy_documents(_knowledge_policy(repo), repo):
        relpath = os.path.relpath(path, repo).replace(os.sep, "/")
        if relpath.startswith("knowledge/sources/"):
            continue
        source_type = "tracked_doc"
        if relpath.startswith("knowledge/queries/"):
            source_type = "query_page"
        elif relpath.startswith("knowledge/"):
            source_type = "tracked_knowledge"
        if relpath not in seen:
            seen.add(relpath)
            specs.append(
                {
                    "relpath": relpath,
                    "source_type": source_type,
                    "title": _markdown_title(path),
                    "summary": _markdown_summary(path),
                }
            )

    for summary in summaries:
        summary_path = summary.get("_summary_path")
        if not summary_path:
            continue
        run_id = str(summary.get("run_id", "")).strip()
        relpath = os.path.relpath(summary_path, repo).replace(os.sep, "/") if str(summary_path).startswith(str(repo)) else f".cache-source/{run_id}/summary.json"
        if relpath in seen:
            continue
        seen.add(relpath)
        specs.append(
            {
                "relpath": relpath,
                "source_type": "control_plane_summary",
                "title": f"Source Summary: {run_id}",
                "summary": _compact_text(str(summary.get("summary", ""))),
            }
        )
        report_path = str(summary.get("report_path", "")).strip()
        if report_path:
            report_relpath = os.path.relpath(report_path, repo).replace(os.sep, "/") if report_path.startswith(str(repo)) else f".cache-source/{run_id}/report.md"
            if report_relpath not in seen:
                seen.add(report_relpath)
                specs.append(
                    {
                        "relpath": report_relpath,
                        "source_type": "control_plane_report",
                        "title": f"Source Report: {run_id}",
                        "summary": f"Verification report for `{run_id}`.",
                    }
                )
    return specs


def _source_page_content(repo: Path, spec: dict[str, Any]) -> str:
    relpath = str(spec["relpath"])
    source_path = _source_page_path(repo, relpath)
    return (
        f"# Source: {spec['title']}\n\n"
        f"- source type: `{spec['source_type']}`\n"
        f"- source path: `{relpath}`\n"
        f"- source id: `{_source_id_for_relpath(relpath)}`\n\n"
        "## Summary\n\n"
        f"- {spec['summary'] or '_No summary_'}\n\n"
        "## Backlinks\n\n"
        f"- {_markdown_link(source_path, _tracked_index_path(repo), 'knowledge/index.md')}\n"
        f"- {_markdown_link(source_path, _tracked_log_path(repo), 'knowledge/log.md')}\n"
    )


def _iter_policy_documents(policy: dict[str, Any], repo: Path) -> list[Path]:
    documents: list[Path] = []
    seen: set[Path] = set()
    for raw_path in policy.get("indexed_paths", []):
        candidate = (repo / str(raw_path)).resolve()
        if not candidate.exists():
            continue
        if candidate.is_dir():
            for path in sorted(candidate.rglob("*.md")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                documents.append(resolved)
            continue
        if candidate.suffix == ".md" and candidate not in seen:
            seen.add(candidate)
            documents.append(candidate)
    return documents


def _backfill_promoted_knowledge(*, repo_root: str | Path | None = None, dry_run: bool = False) -> list[str]:
    repo = _repo_root(repo_root)
    backfilled: list[str] = []
    for kind in ("sop", "skill"):
        for metadata_path in sorted(_knowledge_dir(kind).glob("*.md.meta.json")):
            try:
                metadata = _json_load(metadata_path)
            except Exception:
                continue
            if metadata.get("status") != "promoted":
                continue
            draft_path = Path(str(metadata_path).removesuffix(".meta.json"))
            if not draft_path.exists():
                continue
            target_relpath = str(metadata.get("target_relpath", "")).strip()
            if not target_relpath:
                continue
            target_path = repo / target_relpath
            if target_path.exists():
                continue
            backfilled.append(target_relpath)
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")
    return backfilled


def _skill_paths_for_worker(repo: Path, worker_model_id: str) -> list[Path]:
    paths: list[Path] = []
    exact = repo / "knowledge" / "skills" / f"worker-{_slug(worker_model_id)}.md"
    if exact.exists():
        paths.append(exact)
    generic_candidates = []
    worker_lower = worker_model_id.lower()
    if "gemma4" in worker_lower:
        generic_candidates.append(repo / "knowledge" / "skills" / "worker-gemma4-local.md")
    if "apfel" in worker_lower:
        generic_candidates.append(repo / "knowledge" / "skills" / "worker-apfel-lowlatency.md")
    for candidate in generic_candidates:
        if candidate.exists() and candidate not in paths:
            paths.append(candidate)
    return paths


def _open_failures_by_component() -> dict[str, list[dict[str, Any]]]:
    failures: dict[str, list[dict[str, Any]]] = {}
    layout = ensure_control_plane_layout()
    for path in sorted(Path(layout["failures_open"]).glob("*.json")):
        try:
            payload = _json_load(path)
        except Exception:
            continue
        component = str(payload.get("component", "")).strip() or "unspecified"
        failures.setdefault(component, []).append(
            {
                "path": str(path),
                "failure_type": str(payload.get("failure_type", "")).strip(),
                "source_run_id": str(payload.get("source_run_id", "")).strip(),
            }
        )
    return failures


def _component_page_content(
    *,
    repo: Path,
    component: str,
    summaries: list[dict[str, Any]],
    policy: dict[str, Any],
) -> str:
    context = harness_component_context(component)
    accepted_runs: list[dict[str, Any]] = []
    verification_runs: list[dict[str, Any]] = []
    failure_types: set[str] = set()
    skill_paths: list[Path] = []
    source_paths: list[Path] = []
    for summary in sorted(summaries, key=lambda item: item.get("_summary_mtime", 0), reverse=True):
        entry = _run_entry(Path(summary.get("_summary_path", "")), summary)
        if entry["run_kind"] == "verification_only":
            verification_runs.append(entry)
        elif _is_accepted_summary(summary):
            accepted_runs.append(entry)
        for failure_type in summary.get("failure_causes", []):
            if str(failure_type).strip():
                failure_types.add(str(failure_type).strip())
        worker_id = _selected_worker_id(summary)
        if worker_id:
            for path in _skill_paths_for_worker(repo, worker_id):
                if path not in skill_paths:
                    skill_paths.append(path)
        summary_relpath = os.path.relpath(str(summary.get("_summary_path", "")), repo).replace(os.sep, "/") if str(summary.get("_summary_path", "")).startswith(str(repo)) else f".cache-source/{entry['run_id']}/summary.json"
        source_paths.append(_source_page_path(repo, summary_relpath))
        report_path = str(entry.get("report_path", "")).strip()
        if report_path:
            report_relpath = os.path.relpath(report_path, repo).replace(os.sep, "/") if report_path.startswith(str(repo)) else f".cache-source/{entry['run_id']}/report.md"
            source_paths.append(_source_page_path(repo, report_relpath))

    open_failures = _open_failures_by_component().get(component, [])
    for item in open_failures:
        if item.get("failure_type"):
            failure_types.add(item["failure_type"])

    sop_paths = []
    for failure_type in sorted(failure_types):
        candidate = repo / "knowledge" / "sops" / f"failure-{_slug(failure_type)}.md"
        if candidate.exists():
            sop_paths.append(candidate)

    target_path = _tracked_component_dir(repo) / f"{component}.md"
    accepted_lines = []
    for item in accepted_runs[:5]:
        compacted = compact_output("summary", str(item.get("summary", "")), budget_chars=policy["snippet_chars"])
        suffix = f" pr={item.get('pr_url')}" if item.get("pr_url") else ""
        accepted_lines.append(
            f"`{item['run_id']}` metric=`{item.get('metric_key', '')}` summary={compacted['text']}{suffix}"
        )
    verification_lines = []
    for item in verification_runs[:5]:
        compacted = compact_output("summary", str(item.get("summary", "")), budget_chars=policy["snippet_chars"])
        verification_lines.append(
            f"`{item['run_id']}` metric=`{item.get('metric_key', '')}` summary={compacted['text']}"
        )
    open_failure_lines = [
        f"`{item['failure_type']}` source_run=`{item.get('source_run_id', '') or 'unknown'}`"
        for item in open_failures
        if item.get("failure_type")
    ]
    sop_lines = [
        f"{_markdown_link(target_path, path)}"
        for path in sop_paths
    ]
    skill_lines = [
        f"{_markdown_link(target_path, path)}"
        for path in skill_paths
    ]
    source_lines = [
        f"{_markdown_link(target_path, path)}"
        for path in source_paths
        if path.exists()
    ]
    return (
        f"# Component: {component}\n\n"
        "Generated from control-plane evidence and tracked harness knowledge.\n\n"
        "## Contract\n\n"
        f"- benchmark command: `{context.get('benchmark_command', '')}`\n"
        f"- success signal: {context.get('success_signal', '')}\n"
        f"- metric key: `{context.get('metric_key', '')}`\n"
        "\n## Related Knowledge\n\n"
        "### SOPs\n\n"
        f"{_bullet_block(sop_lines)}\n\n"
        "### Skills\n\n"
        f"{_bullet_block(skill_lines)}\n\n"
        "### Sources\n\n"
        f"{_bullet_block(source_lines)}\n\n"
        "## Recent Accepted Runs\n\n"
        f"{_bullet_block(accepted_lines)}\n\n"
        "## Recent Verification-Only Runs\n\n"
        f"{_bullet_block(verification_lines)}\n\n"
        "## Current Open Failures\n\n"
        f"{_bullet_block(open_failure_lines)}\n"
    )


def _index_content(
    *,
    repo: Path,
    component_ids: list[str],
    policy: dict[str, Any],
) -> str:
    index_path = _tracked_index_path(repo)
    component_lines = []
    for component in component_ids:
        component_path = _tracked_component_dir(repo) / f"{component}.md"
        if not component_path.exists():
            continue
        component_lines.append(f"{_markdown_link(index_path, component_path, component)}")

    sop_lines = []
    for path in sorted((repo / "knowledge" / "sops").glob("*.md")):
        sop_lines.append(f"{_markdown_link(index_path, path, _markdown_title(path))}")

    skill_lines = []
    for path in sorted((repo / "knowledge" / "skills").glob("*.md")):
        skill_lines.append(f"{_markdown_link(index_path, path, _markdown_title(path))}")

    query_lines = []
    for path in sorted(_tracked_query_dir(repo).glob("*.md")):
        query_lines.append(f"{_markdown_link(index_path, path, _markdown_title(path))}")

    source_lines = []
    for path in sorted(_tracked_source_dir(repo).glob("*.md")):
        source_lines.append(f"{_markdown_link(index_path, path, _markdown_title(path))}")

    reference_lines = []
    for path in _iter_policy_documents(policy, repo):
        relpath = os.path.relpath(path, repo).replace(os.sep, "/")
        if relpath.startswith("knowledge/"):
            continue
        reference_lines.append(f"{_markdown_link(index_path, path, relpath)}")

    entrypoint_lines = []
    for relpath in policy.get("canonical_entrypoints", []):
        target = repo / relpath
        if target.exists():
            entrypoint_lines.append(f"{_markdown_link(index_path, target, relpath)}")
    parity_target = repo / "PARITY.md"
    if parity_target.exists():
        entrypoint_lines.append(f"{_markdown_link(index_path, parity_target, 'PARITY.md')}")
    return (
        "# Angella Harness Wiki Index\n\n"
        "This file is the canonical entry point for tracked harness knowledge.\n\n"
        "## Entry Points\n\n"
        f"{_bullet_block(entrypoint_lines)}\n\n"
        "## Components\n\n"
        f"{_bullet_block(component_lines)}\n\n"
        "## Failure Patterns\n\n"
        f"{_bullet_block(sop_lines)}\n\n"
        "## Worker Patterns\n\n"
        f"{_bullet_block(skill_lines)}\n\n"
        "## Queries\n\n"
        f"{_bullet_block(query_lines)}\n\n"
        "## Sources\n\n"
        f"{_bullet_block(source_lines)}\n\n"
        "## Reference Docs\n\n"
        f"{_bullet_block(reference_lines)}\n"
    )


def _ensure_log_header(log_path: Path, *, dry_run: bool) -> str:
    if log_path.exists():
        return log_path.read_text(encoding="utf-8")
    header = (
        "# Angella Harness Wiki Log\n\n"
        "Append-only event log for accepted runs, verification-only runs, parity updates, and sync lint passes.\n"
    )
    if not dry_run:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(header, encoding="utf-8")
    return header


def _source_index_content(repo: Path) -> str:
    index_path = _tracked_source_index_path(repo)
    lines = [
        _markdown_link(index_path, path, _markdown_title(path))
        for path in sorted(_tracked_source_dir(repo).glob("*.md"))
        if path.name != "index.md"
    ]
    return (
        "# Harness Source Index\n\n"
        "Tracked raw-source mirror pages used by the harness wiki.\n\n"
        "## Sources\n\n"
        f"{_bullet_block(lines)}\n"
    )


def _append_log_entries(
    *,
    repo: Path,
    policy: dict[str, Any],
    source_summaries: list[dict[str, Any]],
    updated_paths: list[str],
    dry_run: bool,
    run_id: str,
    source_kind: str,
    indexed_document_count: int,
) -> list[str]:
    log_path = _tracked_log_path(repo)
    existing = _ensure_log_header(log_path, dry_run=dry_run)
    markers = set(re.findall(r"<!-- angella-log:([^>]+) -->", existing))
    entries: list[str] = []
    added_markers: list[str] = []

    for summary in sorted(source_summaries, key=lambda item: item.get("_summary_mtime", 0)):
        entry = _run_entry(Path(summary.get("_summary_path", "")), summary)
        kind = "verification" if entry["run_kind"] == "verification_only" else "accepted"
        marker = f"{kind}:{entry['run_id']}"
        if marker in markers:
            continue
        added_markers.append(marker)
        summary_text = compact_output("summary", str(entry.get("summary", "")), budget_chars=policy["snippet_chars"])
        heading_date = _dt.datetime.fromtimestamp(summary.get("_summary_mtime", time.time())).strftime("%Y-%m-%d")
        component_path = _tracked_component_dir(repo) / f"{entry.get('objective_component') or 'recipe-runtime'}.md"
        component_link = (
            _markdown_link(log_path, component_path, component_path.stem)
            if component_path.exists()
            else f"`{entry.get('objective_component') or 'unspecified'}`"
        )
        entries.append(
            f"\n## [{heading_date}] {kind} | {entry.get('objective_component') or 'unspecified'} | {entry['run_id']}\n"
            f"<!-- angella-log:{marker} -->\n"
            f"- component: {component_link}\n"
            f"- metric: `{entry.get('metric_key', '')}`\n"
            f"- summary: {summary_text['text']}\n"
        )

    parity_file = repo / "PARITY.md"
    if parity_file.exists():
        fingerprint = _content_fingerprint(parity_file.read_text(encoding="utf-8"))
        marker = f"parity:{fingerprint}"
        if marker not in markers:
            added_markers.append(marker)
            entries.append(
                f"\n## [{_dt.datetime.now().strftime('%Y-%m-%d')}] parity | PARITY.md\n"
                f"<!-- angella-log:{marker} -->\n"
                f"- canonical file: {_markdown_link(log_path, parity_file, 'PARITY.md')}\n"
                "- role: product-truth behavioral checklist\n"
            )

    if updated_paths:
        fingerprint = _content_fingerprint("\n".join(sorted(updated_paths + [run_id, source_kind])))
        marker = f"lint:{fingerprint}"
        if marker not in markers:
            added_markers.append(marker)
            updated_lines = "\n".join(f"- `{path}`" for path in updated_paths)
            entries.append(
                f"\n## [{_dt.datetime.now().strftime('%Y-%m-%d')}] lint | harness knowledge sync\n"
                f"<!-- angella-log:{marker} -->\n"
                f"- indexed documents: `{indexed_document_count}`\n"
                f"{updated_lines}\n"
            )

    if entries and not dry_run:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write("".join(entries))
    return added_markers


def _rebuild_wiki_index(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    policy = _knowledge_policy(repo)
    db_path = _wiki_index_db_path()
    documents = _iter_policy_documents(policy, repo)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DROP TABLE IF EXISTS docs")
        conn.execute("DROP TABLE IF EXISTS docs_fts")
        conn.execute(
            "CREATE TABLE docs (relpath TEXT PRIMARY KEY, abs_path TEXT, title TEXT, category TEXT, content TEXT)"
        )
        engine = "fts5"
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE docs_fts USING fts5(relpath UNINDEXED, title, category, content)"
            )
        except sqlite3.OperationalError:
            engine = "like"

        for path in documents:
            relpath = os.path.relpath(path, repo).replace(os.sep, "/")
            content = path.read_text(encoding="utf-8")
            title = _markdown_title(path)
            category = relpath.split("/", 1)[0]
            conn.execute(
                "INSERT INTO docs(relpath, abs_path, title, category, content) VALUES (?, ?, ?, ?, ?)",
                (relpath, str(path), title, category, content),
            )
            if engine == "fts5":
                conn.execute(
                    "INSERT INTO docs_fts(relpath, title, category, content) VALUES (?, ?, ?, ?)",
                    (relpath, title, category, content),
                )
        conn.commit()
    return {
        "db_path": str(db_path),
        "document_count": len(documents),
        "engine": engine,
    }


def _snippet_for_query(content: str, query: str, *, budget_chars: int) -> dict[str, Any]:
    lowered = content.lower()
    position = 0
    for token in [part for part in re.split(r"\s+", query.lower().strip()) if part]:
        candidate = lowered.find(token)
        if candidate >= 0:
            position = candidate
            break
    start = max(0, position - (budget_chars // 2))
    end = min(len(content), start + budget_chars)
    return compact_output("search_snippet", content[start:end], budget_chars=budget_chars)


def _fts_match_query(query: str) -> str:
    tokens = [token for token in re.findall(r"[A-Za-z0-9_.:/-]+", query) if token]
    if not tokens:
        return query
    return " OR ".join(f'"{token}"' for token in tokens)


def _coerce_qmd_results(payload: Any, *, limit: int) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            payload = payload["results"]
        elif isinstance(payload.get("items"), list):
            payload = payload["items"]
        else:
            payload = [payload]
    if not isinstance(payload, list):
        return []
    results: list[dict[str, Any]] = []
    for item in payload[:limit]:
        if not isinstance(item, dict):
            continue
        relpath = str(item.get("relpath") or item.get("path") or item.get("file") or "").strip()
        if not relpath:
            continue
        results.append(
            {
                "relpath": relpath,
                "title": str(item.get("title") or Path(relpath).name).strip(),
                "category": str(item.get("category") or relpath.split("/", 1)[0]).strip(),
                "score": item.get("score", 0.0),
                "snippet": str(item.get("snippet") or item.get("excerpt") or "").strip(),
            }
        )
    return results


def _qmd_search(query: str, *, limit: int, repo: Path, budget_chars: int) -> dict[str, Any]:
    qmd_binary = shutil.which("qmd")
    if not qmd_binary:
        return {"available": False, "reason": "qmd_not_installed", "results": []}
    command_variants = [
        [qmd_binary, "search", query, "--json", "-n", str(limit)],
        [qmd_binary, "search", query, "--json", "--limit", str(limit)],
    ]
    for command in command_variants:
        result = subprocess.run(
            command,
            cwd=str(repo),
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            continue
        try:
            payload = json.loads(result.stdout)
        except Exception:
            continue
        results = []
        for item in _coerce_qmd_results(payload, limit=limit):
            compacted = compact_output("search_snippet", item.get("snippet", ""), budget_chars=budget_chars)
            results.append(
                {
                    **item,
                    "snippet": compacted["text"],
                    "compaction": telemetry_block(compacted),
                }
            )
        return {"available": True, "reason": "", "results": results}
    return {"available": False, "reason": "qmd_invocation_failed", "results": []}


def search_harness_knowledge(
    query: str,
    *,
    limit: int = 5,
    provider: str = "builtin",
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    policy = _knowledge_policy(repo)
    selected_provider = provider or str(policy.get("search_provider", "builtin"))
    budget_chars = int(policy.get("snippet_chars", 240))
    if selected_provider == "qmd":
        qmd_result = _qmd_search(query, limit=limit, repo=repo, budget_chars=budget_chars)
        if qmd_result["available"]:
            index_info = _rebuild_wiki_index(repo_root=repo)
            return {
                "success": True,
                "requested_provider": "qmd",
                "provider": "qmd",
                "engine": "external_qmd",
                "query": query,
                "limit": limit,
                "index_db_path": index_info["db_path"],
                "document_count": index_info["document_count"],
                "results": qmd_result["results"],
                "fallback_reason": "",
            }
        selected_provider = "builtin"
        fallback_reason = qmd_result["reason"]
    elif selected_provider != "builtin":
        return {
            "success": False,
            "provider": selected_provider,
            "error": "Unsupported search provider.",
        }
    else:
        fallback_reason = ""

    index_info = _rebuild_wiki_index(repo_root=repo)
    results: list[dict[str, Any]] = []
    with sqlite3.connect(index_info["db_path"]) as conn:
        if index_info["engine"] == "fts5":
            statement = (
                "SELECT docs.relpath, docs.title, docs.category, docs.content, bm25(docs_fts) AS rank "
                "FROM docs_fts JOIN docs USING(relpath) "
                "WHERE docs_fts MATCH ? ORDER BY rank LIMIT ?"
            )
            try:
                rows = conn.execute(statement, (_fts_match_query(query), limit)).fetchall()
            except sqlite3.OperationalError:
                rows = []
        else:
            rows = []

        if not rows:
            tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9_.:/-]+", query) if token]
            if not tokens:
                tokens = [query.lower()]
            clauses = " OR ".join("(lower(title) LIKE ? OR lower(content) LIKE ?)" for _ in tokens)
            params: list[Any] = []
            for token in tokens:
                pattern = f"%{token}%"
                params.extend([pattern, pattern])
            params.append(limit)
            rows = conn.execute(
                f"SELECT relpath, title, category, content, 0.0 AS rank FROM docs "
                f"WHERE {clauses} ORDER BY relpath LIMIT ?",
                params,
            ).fetchall()

    for relpath, title, category, content, rank in rows[:limit]:
        compacted = _snippet_for_query(str(content), query, budget_chars=budget_chars)
        results.append(
            {
                "relpath": relpath,
                "title": title,
                "category": category,
                "score": rank,
                "snippet": compacted["text"],
                "compaction": telemetry_block(compacted),
            }
        )

    return {
        "success": True,
        "requested_provider": provider or str(policy.get("search_provider", "builtin")),
        "provider": selected_provider,
        "engine": index_info["engine"],
        "query": query,
        "limit": limit,
        "index_db_path": index_info["db_path"],
        "document_count": index_info["document_count"],
        "results": results,
        "fallback_reason": fallback_reason,
    }


def inspect_harness_knowledge(
    *,
    format: str = "json",
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    policy = _knowledge_policy(repo)
    state_path = _knowledge_sync_state_path()
    state = _json_load(state_path) if state_path.exists() else {}
    index_info = _rebuild_wiki_index(repo_root=repo)
    log_path = _tracked_log_path(repo)
    log_entries = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## ["):
                log_entries.append(line)
    component_paths = sorted(_tracked_component_dir(repo).glob("*.md"))
    query_paths = sorted(_tracked_query_dir(repo).glob("*.md"))
    source_paths = [path for path in sorted(_tracked_source_dir(repo).glob("*.md")) if path.name != "index.md"]
    payload = {
        "format": "json",
        "search_provider": str(policy.get("search_provider", "builtin")),
        "canonical_entrypoints": list(policy.get("canonical_entrypoints", [])),
        "schema_path": str(repo / "knowledge" / "schema.md"),
        "index_path": str(_tracked_index_path(repo)),
        "log_path": str(log_path),
        "component_paths": [str(path) for path in component_paths],
        "query_paths": [str(path) for path in query_paths],
        "source_paths": [str(path) for path in source_paths],
        "component_count": len(component_paths),
        "query_count": len(query_paths),
        "source_count": len(source_paths),
        "index_db_path": index_info["db_path"],
        "indexed_document_count": index_info["document_count"],
        "recent_log_entries": log_entries[-int(policy.get("log_tail_entries", 5)):],
        "last_sync": state,
    }
    if format == "markdown":
        payload["format"] = "markdown"
        payload["content"] = (
            "# Harness Knowledge Overview\n\n"
            f"- search provider: `{payload['search_provider']}`\n"
            f"- indexed documents: `{payload['indexed_document_count']}`\n"
            f"- component pages: `{payload['component_count']}`\n"
            f"- query pages: `{payload['query_count']}`\n"
            f"- source pages: `{payload['source_count']}`\n"
            f"- index db: `{payload['index_db_path']}`\n\n"
            "## Entry Points\n\n"
            f"- `knowledge/schema.md`\n- `knowledge/index.md`\n- `knowledge/log.md`\n- `knowledge/sources/index.md`\n\n"
            "## Components\n\n"
            f"{_bullet_block([f'`{Path(path).name}`' for path in payload['component_paths']])}\n\n"
            "## Queries\n\n"
            f"{_bullet_block([f'`{Path(path).name}`' for path in payload['query_paths']])}\n\n"
            "## Sources\n\n"
            f"{_bullet_block([f'`{Path(path).name}`' for path in payload['source_paths']])}\n\n"
            "## Recent Log Entries\n\n"
            f"{_bullet_block([f'`{entry}`' for entry in payload['recent_log_entries']])}\n"
        )
    return payload


def sync_harness_knowledge(
    run_id: str = "",
    *,
    source_kind: str = "recent",
    dry_run: bool = False,
    include_backfill: bool = True,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    policy = _knowledge_policy(repo)
    repo_summaries = _all_run_summaries()
    component_ids = _component_ids_from_summaries(repo_summaries)
    updated_paths: list[str] = []
    backfilled_paths = (
        _backfill_promoted_knowledge(repo_root=repo, dry_run=dry_run)
        if include_backfill
        else []
    )
    updated_paths.extend(backfilled_paths)

    for spec in _source_specs(repo, repo_summaries):
        source_path = _source_page_path(repo, spec["relpath"])
        if _write_text_if_changed(source_path, _source_page_content(repo, spec), dry_run=dry_run):
            updated_paths.append(os.path.relpath(source_path, repo).replace(os.sep, "/"))
    source_index_path = _tracked_source_index_path(repo)
    if _write_text_if_changed(source_index_path, _source_index_content(repo), dry_run=dry_run):
        updated_paths.append(os.path.relpath(source_index_path, repo).replace(os.sep, "/"))

    components_dir = _tracked_component_dir(repo)
    for component in component_ids:
        component_summaries = []
        for summary in repo_summaries:
            objective = ""
            harness = summary.get("harness_metadata", {})
            if isinstance(harness, dict):
                objective = str(harness.get("objective_component", "")).strip()
            objective = objective or str(summary.get("objective_component", "")).strip()
            if objective == component:
                component_summaries.append(summary)
        content = _component_page_content(
            repo=repo,
            component=component,
            summaries=component_summaries,
            policy=policy,
        )
        component_path = components_dir / f"{component}.md"
        if _write_text_if_changed(component_path, content, dry_run=dry_run):
            updated_paths.append(os.path.relpath(component_path, repo).replace(os.sep, "/"))

    index_content = _index_content(repo=repo, component_ids=component_ids, policy=policy)
    index_path = _tracked_index_path(repo)
    if _write_text_if_changed(index_path, index_content, dry_run=dry_run):
        updated_paths.append(os.path.relpath(index_path, repo).replace(os.sep, "/"))

    source_summaries = repo_summaries
    if run_id:
        source_summaries = [summary for summary in repo_summaries if summary.get("run_id") == run_id]
    index_info = _rebuild_wiki_index(repo_root=repo)
    added_log_markers = _append_log_entries(
        repo=repo,
        policy=policy,
        source_summaries=source_summaries,
        updated_paths=updated_paths,
        dry_run=dry_run,
        run_id=run_id,
        source_kind=source_kind,
        indexed_document_count=index_info["document_count"],
    )
    if added_log_markers:
        updated_paths.append("knowledge/log.md")
        index_info = _rebuild_wiki_index(repo_root=repo)

    state = {
        "run_id": run_id,
        "source_kind": source_kind,
        "synced_at": _now_timestamp(),
        "include_backfill": include_backfill,
        "updated_paths": sorted(set(updated_paths)),
        "backfilled_paths": sorted(set(backfilled_paths)),
        "component_count": len(component_ids),
        "search_provider": str(policy.get("search_provider", "builtin")),
        "index_db_path": index_info["db_path"],
        "indexed_document_count": index_info["document_count"],
        "log_entries_added": added_log_markers,
    }
    if not dry_run:
        _json_dump(_knowledge_sync_state_path(), state)
    return {
        "run_id": run_id,
        "source_kind": source_kind,
        "dry_run": dry_run,
        "side_effects_applied": not dry_run,
        **state,
    }


def _required_schema_sections() -> list[str]:
    return [
        "## Layers",
        "## Entry Points",
        "## Component Pages",
        "## Linking Rules",
        "## Log Rules",
        "## Addendum Rules",
        "## Search Rules",
        "## Non-Goals",
    ]


def _validate_harness_schema_and_policy(repo: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    schema_path = repo / "knowledge" / "schema.md"
    if not schema_path.exists():
        issues.append({"kind": "missing_schema", "path": str(schema_path), "message": "knowledge/schema.md is missing."})
    else:
        schema_text = schema_path.read_text(encoding="utf-8")
        for section in _required_schema_sections():
            if section not in schema_text:
                issues.append(
                    {
                        "kind": "schema_section_missing",
                        "path": str(schema_path),
                        "message": f"Missing required schema section: {section}",
                    }
                )

    policy_path = repo / "config" / "knowledge-policy.yaml"
    policy = _knowledge_policy(repo)
    for key in ("indexed_paths", "canonical_entrypoints", "search_provider", "snippet_chars"):
        if key not in policy:
            issues.append(
                {
                    "kind": "policy_key_missing",
                    "path": str(policy_path),
                    "message": f"Missing required policy key: {key}",
                }
            )
    return issues


def _extract_markdown_links(path: Path) -> list[tuple[str, str]]:
    links = []
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        links.append((match.group(1), match.group(2)))
    return links


def _record_lint_log(repo: Path, issues: list[dict[str, Any]], *, dry_run: bool) -> None:
    log_path = _tracked_log_path(repo)
    existing = _ensure_log_header(log_path, dry_run=dry_run)
    fingerprint = _content_fingerprint(json.dumps(issues, ensure_ascii=False))
    marker = f"lint-audit:{fingerprint}"
    if marker in existing:
        return
    body = (
        f"\n## [{_dt.datetime.now().strftime('%Y-%m-%d')}] lint-audit | harness knowledge\n"
        f"<!-- angella-log:{marker} -->\n"
        f"- issue count: `{len(issues)}`\n"
    )
    if issues:
        body += "\n".join(f"- {issue['kind']}: {issue['message']}" for issue in issues[:10]) + "\n"
    else:
        body += "- no issues detected\n"
    if not dry_run:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(body)


def lint_harness_knowledge(
    *,
    repo_root: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    issues: list[dict[str, Any]] = []
    issues.extend(_validate_harness_schema_and_policy(repo))

    index_path = _tracked_index_path(repo)
    log_path = _tracked_log_path(repo)
    index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    tracked_pages = []
    for folder in (
        _tracked_component_dir(repo),
        repo / "knowledge" / "skills",
        repo / "knowledge" / "sops",
        _tracked_query_dir(repo),
        _tracked_source_dir(repo),
    ):
        if folder.exists():
            tracked_pages.extend(sorted(path for path in folder.glob("*.md")))

    for path in tracked_pages:
        if path.name == "index.md" and path.parent == _tracked_source_dir(repo):
            continue
        relpath = os.path.relpath(path, repo).replace(os.sep, "/")
        index_rel = os.path.relpath(path, index_path.parent).replace(os.sep, "/") if index_path.exists() else relpath
        log_rel = os.path.relpath(path, log_path.parent).replace(os.sep, "/") if log_path.exists() else relpath
        if path.parent == _tracked_component_dir(repo):
            if relpath not in index_text and index_rel not in index_text:
                issues.append({"kind": "missing_index_registration", "path": str(path), "message": f"{relpath} is not referenced from knowledge/index.md"})
        if path.parent in {_tracked_query_dir(repo), _tracked_source_dir(repo)}:
            if relpath not in log_text and log_rel not in log_text and relpath not in index_text and index_rel not in index_text:
                issues.append({"kind": "orphan_page", "path": str(path), "message": f"{relpath} is not referenced from knowledge/index.md or knowledge/log.md"})
        for _, target in _extract_markdown_links(path):
            if target.startswith("http://") or target.startswith("https://") or target.startswith("#"):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                issues.append({"kind": "broken_relative_link", "path": str(path), "message": f"Broken relative link: {target}"})

    summaries = _all_run_summaries()
    for component in _component_ids_from_summaries(summaries):
        component_path = _tracked_component_dir(repo) / f"{component}.md"
        if not component_path.exists():
            issues.append({"kind": "missing_component_page", "path": str(component_path), "message": f"Missing component page for {component}"})
            continue
        latest_summary = ""
        latest_time = -1.0
        for summary in summaries:
            harness = summary.get("harness_metadata", {})
            objective = ""
            if isinstance(harness, dict):
                objective = str(harness.get("objective_component", "")).strip()
            objective = objective or str(summary.get("objective_component", "")).strip()
            if objective != component:
                continue
            if float(summary.get("_summary_mtime", 0)) > latest_time:
                latest_time = float(summary.get("_summary_mtime", 0))
                latest_summary = compact_output("summary", str(summary.get("summary", "")), budget_chars=240)["text"]
        if latest_summary and latest_summary not in component_path.read_text(encoding="utf-8"):
            issues.append(
                {
                    "kind": "stale_component_page",
                    "path": str(component_path),
                    "message": f"Latest summary for {component} is not reflected in the component page.",
                }
            )

    parity_runner = repo / "scripts" / "run_harness_parity_diff.py"
    if parity_runner.exists():
        parity_result = subprocess.run(
            [str(parity_runner)],
            cwd=str(repo),
            text=True,
            capture_output=True,
            check=False,
        )
        if parity_result.returncode != 0:
            issues.append(
                {
                    "kind": "parity_mismatch",
                    "path": str(repo / "PARITY.md"),
                    "message": parity_result.stderr.strip() or "PARITY.md does not match the scenario map/state.",
                }
            )

    _record_lint_log(repo, issues, dry_run=dry_run)
    return {
        "success": len(issues) == 0,
        "dry_run": dry_run,
        "issue_count": len(issues),
        "issues": issues,
    }


def save_harness_query_page(
    *,
    query: str,
    answer_summary: str,
    cited_paths: list[str] | None = None,
    generated_artifacts: list[str] | None = None,
    save_reason: str = "",
    title: str = "",
    dry_run: bool = False,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    repo = _repo_root(repo_root)
    cited_paths = [str(path) for path in (cited_paths or []) if str(path).strip()]
    generated_artifacts = [str(path) for path in (generated_artifacts or []) if str(path).strip()]
    slug = f"{_dt.datetime.now().strftime('%Y%m%d')}-{_slug(title or query)[:48]}"
    page_path = _query_page_path(repo, slug)
    cited_block = _bullet_block([f"`{path}`" for path in cited_paths])
    artifact_block = _bullet_block([f"`{path}`" for path in generated_artifacts])
    content = (
        f"# Query: {title or _compact_text(query, 72)}\n\n"
        f"- saved at: `{_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"- save reason: {save_reason or '_Not specified_'}\n\n"
        "## Query\n\n"
        f"```text\n{query}\n```\n\n"
        "## Answer Summary\n\n"
        f"- {answer_summary}\n\n"
        "## Cited Paths\n\n"
        f"{cited_block}\n\n"
        "## Generated Artifacts\n\n"
        f"{artifact_block}\n"
    )
    if not dry_run:
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(content, encoding="utf-8")
    sync_result = sync_harness_knowledge(
        source_kind="query",
        dry_run=dry_run,
        include_backfill=False,
        repo_root=repo,
    )
    return {
        "success": True,
        "dry_run": dry_run,
        "page_path": str(page_path),
        "sync": sync_result,
    }


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


def _annotate_summary_with_knowledge_sync(
    *,
    run_id: str,
    knowledge_sync: dict[str, Any],
    compaction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = _summary_path(run_id)
    summary_payload = load_run_summary(run_id)
    summary_payload["knowledge_sync"] = knowledge_sync
    if compaction:
        existing_compaction = summary_payload.get("compaction", {})
        if not isinstance(existing_compaction, dict):
            existing_compaction = {}
        existing_compaction.update(compaction)
        summary_payload["compaction"] = existing_compaction
    _json_dump(path, summary_payload)
    append_jsonl(
        path.parent / "telemetry.jsonl",
        {
            "event_type": "knowledge_sync",
            "timestamp": _now_timestamp(),
            "run_id": run_id,
            "knowledge_sync": knowledge_sync,
            "compaction": compaction or {},
        },
    )
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
    repo_root: str | Path | None = None,
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

    knowledge_sync = sync_harness_knowledge(
        run_id=run_id,
        source_kind="run",
        dry_run=False,
        include_backfill=False,
        repo_root=repo_root,
    )
    summary_compaction = telemetry_block(compact_output("summary", summary, budget_chars=240))
    report_content += (
        "\n## Harness Wiki Sync\n\n"
        f"- updated files: `{len(knowledge_sync.get('updated_paths', []))}`\n"
        f"{_bullet_block([f'`{path}`' for path in knowledge_sync.get('updated_paths', [])])}\n\n"
        "## Compaction Telemetry\n\n"
        f"- summary raw chars: `{summary_compaction['raw_chars']}`\n"
        f"- summary compact chars: `{summary_compaction['compact_chars']}`\n"
        f"- summary compaction ratio: `{summary_compaction['compaction_ratio']}`\n"
        f"- estimated tokens saved: `{summary_compaction['estimated_tokens_saved']}`\n"
    )
    report_path.write_text(report_content, encoding="utf-8")
    report_compaction = telemetry_block(compact_output("report", report_content, budget_chars=600))
    payload["knowledge_sync"] = knowledge_sync
    payload["compaction"] = {
        "summary": summary_compaction,
        "report": report_compaction,
    }
    payload["summary_payload"] = _annotate_summary_with_knowledge_sync(
        run_id=run_id,
        knowledge_sync=knowledge_sync,
        compaction=payload["compaction"],
    )

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
            "knowledge_sync": knowledge_sync,
            "compaction": payload["compaction"],
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
    knowledge_sync = sync_harness_knowledge(
        run_id=run_id,
        source_kind="run",
        dry_run=dry_run,
        include_backfill=True,
        repo_root=repo_root,
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
    summary_compaction = {
        "summary": telemetry_block(compact_output("summary", str(summary_payload.get("summary", "")), budget_chars=240))
    }
    if dry_run:
        summary_payload = {
            **summary_payload,
            "knowledge_sync": knowledge_sync,
            "compaction": {
                **(summary_payload.get("compaction", {}) if isinstance(summary_payload.get("compaction", {}), dict) else {}),
                **summary_compaction,
            },
        }
    else:
        summary_payload = _annotate_summary_with_knowledge_sync(
            run_id=run_id,
            knowledge_sync=knowledge_sync,
            compaction=summary_compaction,
        )
    result = {
        "run_id": run_id,
        "dry_run": dry_run,
        "side_effects_applied": not dry_run,
        "drafts_created": draft_result["drafts_created"],
        "promotion_report_path": promotion_result["report_path"],
        "promoted_targets": promoted_targets,
        "failure_closure": failure_closure_result,
        "knowledge_sync": knowledge_sync,
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
