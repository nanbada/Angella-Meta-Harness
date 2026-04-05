#!/usr/bin/env python3
"""Next.js benchmark adapter with the shared benchmark schema."""

import os
import re
import subprocess
import time

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from common import (
    SUPPORTED_METRICS,
    build_benchmark_payload,
    compare_metrics_payload,
    text_response,
)

server = Server("metric-benchmark-nextjs")


def _parse_next_build(stdout: str, stderr: str) -> dict:
    combined = stdout + stderr
    metrics = {
        "pages": [],
        "total_first_load_kb": 0.0,
        "largest_page_kb": 0.0,
        "page_count": 0,
    }

    route_pattern = r"[○●λƒ]\s+(/\S+)\s+([0-9.]+)\s*(kB|KB|B|MB)"
    for match in re.finditer(route_pattern, combined):
        route, size, unit = match.groups()
        size_kb = float(size)
        if unit == "B":
            size_kb /= 1024
        elif unit == "MB":
            size_kb *= 1024

        size_kb = round(size_kb, 2)
        metrics["pages"].append({"route": route, "size_kb": size_kb})
        metrics["largest_page_kb"] = max(metrics["largest_page_kb"], size_kb)

    fl_match = re.search(r"First Load JS.*?([0-9.]+)\s*kB", combined)
    if fl_match:
        metrics["total_first_load_kb"] = float(fl_match.group(1))

    metrics["page_count"] = len(metrics["pages"])
    return metrics


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="run_benchmark",
            description="Next.js 프로젝트를 측정하고 공통 benchmark payload를 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "빌드 명령어",
                        "default": "npm run build",
                    },
                    "metric_key": {
                        "type": "string",
                        "enum": ["build_time", "bundle_size"],
                        "default": "build_time",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Next.js 프로젝트 루트 경로",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "최대 실행 시간 (초)",
                        "default": 300,
                    },
                },
                "required": ["working_directory"],
            },
        ),
        types.Tool(
            name="compare_metrics",
            description="두 메트릭 값을 비교하여 개선 여부를 판정합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "baseline": {"type": "number"},
                    "current": {"type": "number"},
                    "metric_key": {
                        "type": "string",
                        "enum": list(SUPPORTED_METRICS),
                    },
                    "threshold_percent": {
                        "type": "number",
                        "default": 1.0,
                    },
                },
                "required": ["baseline", "current", "metric_key"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name in {"run_benchmark", "benchmark_nextjs"}:
        if name == "benchmark_nextjs":
            project_path = os.path.expanduser(arguments["project_path"])
            command = arguments.get("build_command", "npm run build")
            metric_key = arguments.get("metric_key", "build_time")
            timeout = int(arguments.get("timeout_seconds", 300))
        else:
            project_path = os.path.expanduser(arguments["working_directory"])
            command = arguments.get("command", "npm run build")
            metric_key = arguments.get("metric_key", "build_time")
            timeout = int(arguments.get("timeout_seconds", 300))

        if metric_key not in {"build_time", "bundle_size"}:
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=0.0,
                    exit_code=2,
                    aux_metrics={"failure_reason": "unsupported_metric_for_nextjs"},
                )
            )

        if not os.path.isdir(project_path):
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=0.0,
                    exit_code=2,
                    aux_metrics={
                        "failure_reason": "working_directory_not_found",
                        "working_directory": project_path,
                    },
                )
            )

        try:
            start = time.time()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=timeout,
                env={**os.environ},
            )
            duration = time.time() - start

            next_metrics = _parse_next_build(result.stdout, result.stderr)
            metric_value = duration if metric_key == "build_time" else next_metrics["total_first_load_kb"]
            metric_found = metric_key == "build_time" or next_metrics["total_first_load_kb"] > 0
            success = result.returncode == 0 and metric_found

            failure_reason = ""
            if result.returncode != 0:
                failure_reason = "command_failed"
            elif not metric_found:
                failure_reason = "metric_parse_failed"

            return text_response(
                build_benchmark_payload(
                    success=success,
                    metric_key=metric_key,
                    metric_value=metric_value,
                    duration_seconds=duration,
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    aux_metrics={
                        "command": command,
                        "working_directory": project_path,
                        "page_count": next_metrics["page_count"],
                        "pages": next_metrics["pages"][:10],
                        "largest_page_kb": next_metrics["largest_page_kb"],
                        "total_first_load_kb": next_metrics["total_first_load_kb"],
                        "failure_reason": failure_reason,
                    },
                )
            )
        except subprocess.TimeoutExpired:
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=float(timeout),
                    exit_code=124,
                    aux_metrics={
                        "failure_reason": "timeout",
                        "command": command,
                        "working_directory": project_path,
                    },
                )
            )
        except Exception as e:
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=0.0,
                    exit_code=1,
                    aux_metrics={
                        "failure_reason": "exception",
                        "error": str(e),
                        "command": command,
                        "working_directory": project_path,
                    },
                )
            )

    if name == "compare_metrics":
        return text_response(
            compare_metrics_payload(
                float(arguments["baseline"]),
                float(arguments["current"]),
                arguments["metric_key"],
                float(arguments.get("threshold_percent", 1.0)),
            )
        )

    return text_response({"success": False, "error": f"Unknown tool: {name}"})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
