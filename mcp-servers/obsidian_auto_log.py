#!/usr/bin/env python3
"""
Run-scoped logging MCP for Angella transparency.

환경변수:
  OBSIDIAN_VAULT_PATH — 로그를 저장할 루트 경로
"""

import datetime
import json
import os

from control_plane import (
    normalize_intent_contract,
    record_loop_iteration,
    safe_run_id,
    write_final_summary,
)
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("obsidian-auto-log")
ANGELLA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_VAULT_PATH = os.path.join(ANGELLA_ROOT, "logs")


def _resolve_vault_path() -> str:
    configured = os.environ.get("OBSIDIAN_VAULT_PATH") or DEFAULT_VAULT_PATH
    return os.path.abspath(os.path.expanduser(configured))


def _get_log_dir() -> str:
    log_dir = os.path.join(_resolve_vault_path(), "Meta-Harness Logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _format_list(items: list[str]) -> str:
    if not items:
        return "- _None_"
    return "\n".join(f"- {item}" for item in items)


def _format_intent_contract(intent_contract: dict | None) -> str:
    normalized = normalize_intent_contract(intent_contract or {})
    validation = normalized.get("validation", {})
    missing = validation.get("missing_required_fields", [])

    return (
        f"- `ideal_state_8_12_words`: {normalized.get('ideal_state_8_12_words', '') or '_Missing_'}\n"
        f"- `metric_key`: {normalized.get('metric_key', '') or '_Missing_'}\n"
        f"- `intent_summary`: {normalized.get('intent_summary', '') or '_Not recorded_'}\n"
        f"- `metric_reason`: {normalized.get('metric_reason', '') or '_Not recorded_'}\n"
        f"- `success_threshold`: {normalized.get('success_threshold', '') or '_Missing_'}\n"
        f"- `binary_acceptance_checks`:\n{_format_list(normalized.get('binary_acceptance_checks', []))}\n"
        f"- `non_goals`:\n{_format_list(normalized.get('non_goals', []))}\n"
        f"- `operator_constraints`:\n{_format_list(normalized.get('operator_constraints', []))}\n"
        f"- `first_hypotheses`:\n{_format_list(normalized.get('first_hypotheses', []))}\n"
        f"- `validation`: word_count={validation.get('ideal_state_word_count', 0)}, "
        f"target_ok={validation.get('ideal_state_target_ok', False)}, "
        f"missing={missing or '[]'}\n"
    )


def _format_json_block(title: str, payload: dict | list | None) -> str:
    if not payload:
        return ""
    return f"### {title}\n```json\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n```\n\n"


def _decision_label(decision: str) -> str:
    mapping = {
        "baseline": "BASELINE",
        "keep": "KEEP",
        "revert": "REVERT",
        "failure": "FAILURE",
    }
    return mapping.get(decision, decision.upper())


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="save_loop_log",
            description="Run-scoped loop iteration 결과를 Markdown으로 저장합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "project_name": {"type": "string"},
                    "iteration": {"type": "integer"},
                    "decision": {
                        "type": "string",
                        "description": "baseline, keep, revert, failure 중 하나",
                    },
                    "metric_key": {"type": "string"},
                    "metric_value": {"type": "number"},
                    "baseline_value": {"type": "number", "default": 0},
                    "improvement_percent": {"type": "number", "default": 0},
                    "start_commit": {"type": "string"},
                    "candidate_commit": {"type": "string", "default": ""},
                    "benchmark_command": {"type": "string"},
                    "working_directory": {"type": "string"},
                    "summary": {"type": "string"},
                    "failure_reason": {"type": "string", "default": ""},
                    "git_diff": {"type": "string", "default": ""},
                    "proposals": {"type": "string", "default": ""},
                    "intent_contract": {
                        "type": "object",
                        "description": "Intent Contract. Required keys: ideal_state_8_12_words, metric_key, success_threshold, binary_acceptance_checks, non_goals, operator_constraints.",
                        "default": {},
                    },
                    "harness_metadata": {
                        "type": "object",
                        "description": "선택된 profile/model ids, resolved provider/model names, env capability snapshot metadata.",
                        "default": {},
                    },
                    "aux_metrics": {
                        "type": "object",
                        "description": "benchmark MCP가 반환한 보조 메트릭",
                        "default": {},
                    },
                },
                "required": [
                    "run_id",
                    "project_name",
                    "iteration",
                    "decision",
                    "metric_key",
                    "metric_value",
                    "start_commit",
                    "benchmark_command",
                    "working_directory",
                    "summary",
                ],
            },
        ),
        types.Tool(
            name="save_final_report",
            description="Run 종료 후 최종 보고서를 저장합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "project_name": {"type": "string"},
                    "total_iterations": {"type": "integer"},
                    "initial_metric": {"type": "number"},
                    "final_metric": {"type": "number"},
                    "metric_key": {"type": "string"},
                    "improvements_kept": {"type": "integer", "default": 0},
                    "summary": {"type": "string"},
                    "full_git_diff": {"type": "string", "default": ""},
                    "start_commit": {"type": "string"},
                    "final_commit": {"type": "string", "default": ""},
                    "run_branch": {"type": "string", "default": ""},
                    "benchmark_command": {"type": "string"},
                    "working_directory": {"type": "string"},
                    "failure_reasons": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "intent_contract": {
                        "type": "object",
                        "description": "Intent Contract. Required keys: ideal_state_8_12_words, metric_key, success_threshold, binary_acceptance_checks, non_goals, operator_constraints.",
                        "default": {},
                    },
                    "harness_metadata": {
                        "type": "object",
                        "description": "선택된 profile/model ids, resolved provider/model names, env capability snapshot metadata.",
                        "default": {},
                    },
                    "aux_metrics": {
                        "type": "object",
                        "default": {},
                    },
                },
                "required": [
                    "run_id",
                    "project_name",
                    "total_iterations",
                    "initial_metric",
                    "final_metric",
                    "metric_key",
                    "summary",
                    "start_commit",
                    "benchmark_command",
                    "working_directory",
                ],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "save_loop_log":
        run_id = arguments["run_id"]
        project_name = arguments["project_name"]
        iteration = arguments["iteration"]
        decision = arguments["decision"]
        metric_key = arguments["metric_key"]
        metric_value = arguments["metric_value"]
        baseline_value = arguments.get("baseline_value", 0)
        improvement_percent = arguments.get("improvement_percent", 0)
        start_commit = arguments["start_commit"]
        candidate_commit = arguments.get("candidate_commit", "")
        benchmark_command = arguments["benchmark_command"]
        working_directory = arguments["working_directory"]
        summary = arguments["summary"]
        failure_reason = arguments.get("failure_reason", "")
        git_diff = arguments.get("git_diff", "")
        proposals = arguments.get("proposals", "")
        intent_contract = arguments.get("intent_contract", {})
        harness_metadata = arguments.get("harness_metadata", {})
        aux_metrics = arguments.get("aux_metrics", {})
        normalized_intent = normalize_intent_contract(intent_contract, metric_key=metric_key)

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = f"{safe_run_id(run_id)}.md"
        filepath = os.path.join(_get_log_dir(), filename)

        if not os.path.exists(filepath):
            header = (
                f"# Angella Run Log — {project_name}\n\n"
                f"- `run_id`: {run_id}\n"
                f"- `start_commit`: {start_commit}\n"
                f"- `working_directory`: {working_directory}\n"
                f"- `benchmark_command`: `{benchmark_command}`\n"
                f"- `log_root`: `{_resolve_vault_path()}`\n\n"
                "## Intent Contract\n"
                f"{_format_intent_contract(normalized_intent)}\n"
            )
            with open(filepath, "w", encoding="utf-8") as handle:
                handle.write(header)

        content = (
            f"\n---\n\n"
            f"## Iteration {iteration} — {now}\n\n"
            f"| Key | Value |\n"
            f"|-----|-------|\n"
            f"| `decision` | {_decision_label(decision)} |\n"
            f"| `metric_key` | `{metric_key}` |\n"
            f"| `baseline_value` | `{baseline_value}` |\n"
            f"| `metric_value` | `{metric_value}` |\n"
            f"| `improvement_percent` | `{improvement_percent}` |\n"
            f"| `start_commit` | `{start_commit}` |\n"
            f"| `candidate_commit` | `{candidate_commit or '-'}` |\n"
            f"| `failure_reason` | `{failure_reason or '-'}` |\n\n"
            f"### Summary\n{summary}\n\n"
        )

        if proposals:
            content += f"### Proposals\n{proposals}\n\n"

        content += _format_json_block("Harness Metadata", harness_metadata)
        content += _format_json_block("Benchmark Aux Metrics", aux_metrics)

        if git_diff:
            content += f"### Git Diff\n```diff\n{git_diff[:4000]}\n```\n\n"

        with open(filepath, "a", encoding="utf-8") as handle:
            handle.write(content)

        artifacts = record_loop_iteration(
            run_id=run_id,
            project_name=project_name,
            iteration=iteration,
            decision=decision,
            metric_key=metric_key,
            metric_value=metric_value,
            baseline_value=baseline_value,
            improvement_percent=improvement_percent,
            start_commit=start_commit,
            candidate_commit=candidate_commit,
            benchmark_command=benchmark_command,
            working_directory=working_directory,
            summary=summary,
            failure_reason=failure_reason,
            proposals=proposals,
            intent_contract=normalized_intent,
            harness_metadata=harness_metadata,
            aux_metrics=aux_metrics,
        )

        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "saved",
                        "filepath": os.path.abspath(filepath),
                        "run_id": run_id,
                        "iteration": iteration,
                        "decision": decision,
                        "run_dir": artifacts["run_dir"],
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    if name == "save_final_report":
        run_id = arguments["run_id"]
        project_name = arguments["project_name"]
        total_iterations = arguments["total_iterations"]
        initial_metric = arguments["initial_metric"]
        final_metric = arguments["final_metric"]
        metric_key = arguments["metric_key"]
        improvements_kept = arguments.get("improvements_kept", 0)
        summary = arguments["summary"]
        full_git_diff = arguments.get("full_git_diff", "")
        start_commit = arguments["start_commit"]
        final_commit = arguments.get("final_commit", "")
        run_branch = arguments.get("run_branch", "")
        benchmark_command = arguments["benchmark_command"]
        working_directory = arguments["working_directory"]
        failure_reasons = arguments.get("failure_reasons", [])
        intent_contract = arguments.get("intent_contract", {})
        harness_metadata = arguments.get("harness_metadata", {})
        aux_metrics = arguments.get("aux_metrics", {})
        normalized_intent = normalize_intent_contract(intent_contract, metric_key=metric_key)

        lower_is_better = metric_key in ("build_time", "latency_ms", "bundle_size")
        if initial_metric > 0:
            if lower_is_better:
                change_pct = round(((initial_metric - final_metric) / initial_metric) * 100, 2)
            else:
                change_pct = round(((final_metric - initial_metric) / initial_metric) * 100, 2)
        else:
            change_pct = 0.0

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = f"{safe_run_id(run_id)}-FINAL.md"
        filepath = os.path.join(_get_log_dir(), filename)

        content = (
            f"# Angella Final Report — {project_name}\n\n"
            f"- `run_id`: {run_id}\n"
            f"- `completed_at`: {now}\n"
            f"- `run_branch`: {run_branch or '-'}\n"
            f"- `start_commit`: {start_commit}\n"
            f"- `final_commit`: {final_commit or '-'}\n"
            f"- `working_directory`: {working_directory}\n"
            f"- `benchmark_command`: `{benchmark_command}`\n\n"
            "## Intent Contract\n"
            f"{_format_intent_contract(normalized_intent)}\n"
            "## Result\n\n"
            "| Metric | Initial | Final | Change |\n"
            "|--------|---------|-------|--------|\n"
            f"| `{metric_key}` | {initial_metric} | {final_metric} | {change_pct}% |\n\n"
            f"- `total_iterations`: {total_iterations}\n"
            f"- `improvements_kept`: {improvements_kept}\n\n"
            f"## Summary\n{summary}\n\n"
        )

        if failure_reasons:
            content += "## Failure Reasons\n"
            content += "\n".join(f"- {reason}" for reason in failure_reasons)
            content += "\n\n"

        content += _format_json_block("Harness Metadata", harness_metadata)
        content += _format_json_block("Aux Metrics", aux_metrics)

        if full_git_diff:
            content += f"## Full Git Diff\n```diff\n{full_git_diff[:6000]}\n```\n"

        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write(content)

        summary_artifacts = write_final_summary(
            run_id=run_id,
            project_name=project_name,
            total_iterations=total_iterations,
            initial_metric=initial_metric,
            final_metric=final_metric,
            metric_key=metric_key,
            improvements_kept=improvements_kept,
            summary=summary,
            start_commit=start_commit,
            final_commit=final_commit,
            run_branch=run_branch,
            benchmark_command=benchmark_command,
            working_directory=working_directory,
            failure_reasons=failure_reasons,
            intent_contract=normalized_intent,
            harness_metadata=harness_metadata,
            aux_metrics=aux_metrics,
        )

        return [
            types.TextContent(
                type="text",
                text=json.dumps(
                    {
                        "status": "final_report_saved",
                        "filepath": os.path.abspath(filepath),
                        "run_id": run_id,
                        "total_iterations": total_iterations,
                        "improvement_percent": change_pct,
                        "summary_path": summary_artifacts["summary_path"],
                    },
                    ensure_ascii=False,
                ),
            )
        ]

    return [types.TextContent(type="text", text=json.dumps({"success": False, "error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
