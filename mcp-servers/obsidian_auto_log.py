#!/usr/bin/env python3
"""
Run-scoped logging MCP for Angella transparency.

환경변수:
  OBSIDIAN_VAULT_PATH — 로그를 저장할 루트 경로
"""

import datetime
import json
import os
import re

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
    log_dir = os.path.join(_resolve_vault_path(), "Goose Logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def _safe_run_id(run_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", run_id).strip("-") or "angella-run"


def _format_intent_contract(intent_contract: dict | None) -> str:
    if not intent_contract:
        return "_Not recorded_\n"

    first_hypotheses = intent_contract.get("first_hypotheses", [])
    if isinstance(first_hypotheses, list):
        hypotheses_text = "\n".join(f"- {item}" for item in first_hypotheses) or "- _None_"
    else:
        hypotheses_text = str(first_hypotheses)

    return (
        f"- `intent_summary`: {intent_contract.get('intent_summary', '')}\n"
        f"- `metric_reason`: {intent_contract.get('metric_reason', '')}\n"
        f"- `non_goals`: {intent_contract.get('non_goals', '')}\n"
        f"- `success_threshold`: {intent_contract.get('success_threshold', '')}\n"
        f"- `first_hypotheses`:\n{hypotheses_text}\n"
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
                        "description": "Intent Contract 구조체",
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
        aux_metrics = arguments.get("aux_metrics", {})

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = f"{_safe_run_id(run_id)}.md"
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
                f"{_format_intent_contract(intent_contract)}\n"
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

        content += _format_json_block("Benchmark Aux Metrics", aux_metrics)

        if git_diff:
            content += f"### Git Diff\n```diff\n{git_diff[:4000]}\n```\n\n"

        with open(filepath, "a", encoding="utf-8") as handle:
            handle.write(content)

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
        aux_metrics = arguments.get("aux_metrics", {})

        lower_is_better = metric_key in ("build_time", "latency_ms", "bundle_size")
        if initial_metric > 0:
            if lower_is_better:
                change_pct = round(((initial_metric - final_metric) / initial_metric) * 100, 2)
            else:
                change_pct = round(((final_metric - initial_metric) / initial_metric) * 100, 2)
        else:
            change_pct = 0.0

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = f"{_safe_run_id(run_id)}-FINAL.md"
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
            f"{_format_intent_contract(intent_contract)}\n"
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

        content += _format_json_block("Aux Metrics", aux_metrics)

        if full_git_diff:
            content += f"## Full Git Diff\n```diff\n{full_git_diff[:6000]}\n```\n"

        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write(content)

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
