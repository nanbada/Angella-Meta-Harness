#!/usr/bin/env python3
"""MCP tools for control-plane promotion and meta-loop export automation."""

from __future__ import annotations

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from common import text_response
from meta_loop_ops import (
    export_meta_loop_change,
    finalize_accepted_meta_loop_run,
    generate_knowledge_drafts_from_run,
    harness_component_context,
    inspect_control_plane,
    prune_stale_control_plane_artifacts,
    record_verification_only_run,
    promote_knowledge_drafts,
)


server = Server("control-plane-admin")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="draft_knowledge_from_run",
            description="Accepted run summary를 기반으로 control-plane knowledge draft를 생성합니다. dry_run이면 preview만 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "objective_component": {"type": "string", "default": ""},
                    "operator_confirmed": {"type": "boolean", "default": False},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["run_id"],
            },
        ),
        types.Tool(
            name="promote_knowledge_drafts",
            description="Control-plane draft를 promotion rule에 따라 tracked knowledge/sops 또는 knowledge/skills 로 승격합니다. dry_run이면 preview만 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "default": ""},
                    "draft_kind": {"type": "string", "enum": ["sop", "skill"], "default": ""},
                    "operator_confirmed": {"type": "boolean", "default": False},
                    "dry_run": {"type": "boolean", "default": False},
                },
            },
        ),
        types.Tool(
            name="export_meta_loop_change",
            description="Accepted meta-loop change를 codex 브랜치로 내보내고 draft PR을 생성합니다. dry_run이면 branch/PR을 만들지 않습니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "objective_component": {"type": "string", "default": ""},
                    "base_branch": {"type": "string", "default": "main"},
                    "branch_name": {"type": "string", "default": ""},
                    "commit_message": {"type": "string", "default": ""},
                    "pr_title": {"type": "string", "default": ""},
                    "pr_summary": {"type": "string", "default": ""},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["run_id"],
            },
        ),
        types.Tool(
            name="finalize_accepted_meta_loop_run",
            description="Accepted run의 draft 생성, promotion, codex 브랜치 export, draft PR 생성을 한 번에 수행합니다. dry_run이면 preview만 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "objective_component": {"type": "string", "default": ""},
                    "base_branch": {"type": "string", "default": "main"},
                    "branch_name": {"type": "string", "default": ""},
                    "commit_message": {"type": "string", "default": ""},
                    "pr_title": {"type": "string", "default": ""},
                    "pr_summary": {"type": "string", "default": ""},
                    "operator_confirmed": {"type": "boolean", "default": False},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["run_id"],
            },
        ),
        types.Tool(
            name="prune_stale_control_plane_artifacts",
            description="오래된 control-plane draft 및 meta-loop queue artifact를 정리합니다. max_age_days=0이면 내장 retention policy를 사용합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_age_days": {"type": "integer", "default": 0},
                    "include_drafts": {"type": "boolean", "default": True},
                    "include_queue": {"type": "boolean", "default": True},
                    "dry_run": {"type": "boolean", "default": False},
                },
            },
        ),
        types.Tool(
            name="inspect_control_plane",
            description="최근 runs, open failures, pending drafts, queue 상태를 요약합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_limit": {"type": "integer", "default": 5},
                    "failure_limit": {"type": "integer", "default": 10},
                    "draft_limit": {"type": "integer", "default": 10},
                    "queue_limit": {"type": "integer", "default": 10},
                    "format": {"type": "string", "enum": ["json", "markdown"], "default": "json"},
                },
            },
        ),
        types.Tool(
            name="describe_harness_component",
            description="objective_component별 benchmark command, acceptance checks, success signal, 우선 파일 경로를 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "objective_component": {"type": "string"}
                },
                "required": ["objective_component"],
            },
        ),
        types.Tool(
            name="record_verification_only_run",
            description="verification-only benchmark 결과를 control-plane summary/telemetry에 기록하고 종료합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "objective_component": {"type": "string"},
                    "benchmark_command": {"type": "string"},
                    "metric_key": {"type": "string"},
                    "metric_value": {"type": "number"},
                    "summary": {"type": "string"},
                    "working_directory": {"type": "string"},
                    "branch_name": {"type": "string", "default": ""},
                    "finalize_skipped_reason": {"type": "string", "default": ""},
                },
                "required": [
                    "run_id",
                    "objective_component",
                    "benchmark_command",
                    "metric_key",
                    "metric_value",
                    "summary",
                    "working_directory",
                ],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "draft_knowledge_from_run":
        return text_response(
            generate_knowledge_drafts_from_run(
                arguments["run_id"],
                objective_component=arguments.get("objective_component", ""),
                operator_confirmed=arguments.get("operator_confirmed", False),
                dry_run=arguments.get("dry_run", False),
            )
        )

    if name == "promote_knowledge_drafts":
        return text_response(
            promote_knowledge_drafts(
                run_id=arguments.get("run_id") or None,
                draft_kind=arguments.get("draft_kind") or None,
                operator_confirmed=arguments.get("operator_confirmed", False),
                dry_run=arguments.get("dry_run", False),
            )
        )

    if name == "export_meta_loop_change":
        return text_response(
            export_meta_loop_change(
                arguments["run_id"],
                objective_component=arguments.get("objective_component", ""),
                base_branch=arguments.get("base_branch", "main"),
                branch_name=arguments.get("branch_name", ""),
                commit_message=arguments.get("commit_message", ""),
                pr_title=arguments.get("pr_title", ""),
                pr_summary=arguments.get("pr_summary", ""),
                dry_run=arguments.get("dry_run", False),
            )
        )

    if name == "finalize_accepted_meta_loop_run":
        return text_response(
            finalize_accepted_meta_loop_run(
                arguments["run_id"],
                objective_component=arguments.get("objective_component", ""),
                base_branch=arguments.get("base_branch", "main"),
                branch_name=arguments.get("branch_name", ""),
                commit_message=arguments.get("commit_message", ""),
                pr_title=arguments.get("pr_title", ""),
                pr_summary=arguments.get("pr_summary", ""),
                operator_confirmed=arguments.get("operator_confirmed", False),
                dry_run=arguments.get("dry_run", False),
            )
        )

    if name == "prune_stale_control_plane_artifacts":
        return text_response(
            prune_stale_control_plane_artifacts(
                max_age_days=arguments.get("max_age_days", 0),
                include_drafts=arguments.get("include_drafts", True),
                include_queue=arguments.get("include_queue", True),
                dry_run=arguments.get("dry_run", False),
            )
        )

    if name == "inspect_control_plane":
        return text_response(
            inspect_control_plane(
                run_limit=arguments.get("run_limit", 5),
                failure_limit=arguments.get("failure_limit", 10),
                draft_limit=arguments.get("draft_limit", 10),
                queue_limit=arguments.get("queue_limit", 10),
                format=arguments.get("format", "json"),
            )
        )

    if name == "describe_harness_component":
        return text_response(harness_component_context(arguments["objective_component"]))

    if name == "record_verification_only_run":
        return text_response(
            record_verification_only_run(
                run_id=arguments["run_id"],
                objective_component=arguments["objective_component"],
                benchmark_command=arguments["benchmark_command"],
                metric_key=arguments["metric_key"],
                metric_value=arguments["metric_value"],
                summary=arguments["summary"],
                working_directory=arguments["working_directory"],
                branch_name=arguments.get("branch_name", ""),
                finalize_skipped_reason=arguments.get("finalize_skipped_reason", ""),
            )
        )

    return text_response({"success": False, "error": f"Unknown tool: {name}"})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
