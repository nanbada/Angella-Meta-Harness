#!/usr/bin/env python3
"""Generic benchmark MCP with a shared benchmark payload schema."""

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

server = Server("metric-benchmark")


def _parse_metric(output: str, metric_key: str) -> tuple[float, bool, str]:
    patterns = {
        "tokens_per_second": [
            r"tokens?[/_\s](?:per[_\s])?s(?:ec(?:ond)?)?[:\s]+([0-9]+\.?[0-9]*)",
            r"([0-9]+\.?[0-9]*)\s*tokens?/s",
        ],
        "build_time": [
            r"(?:build|compile)\s*(?:time)?[:\s]+([0-9]+\.?[0-9]*)\s*s",
            r"(?:completed|finished)\s+in\s+([0-9]+\.?[0-9]*)\s*s",
        ],
        "latency_ms": [
            r"latency[:\s]+([0-9]+\.?[0-9]*)\s*ms",
            r"(?:avg|average|p50|median)\s*[:\s]+([0-9]+\.?[0-9]*)\s*ms",
        ],
        "bundle_size": [
            r"(?:bundle|total)\s*(?:size)?[:\s]+([0-9]+\.?[0-9]*)\s*(?:kb|KB)",
            r"([0-9]+\.?[0-9]*)\s*(?:kB|KB)\b",
        ],
    }

    for pattern in patterns.get(metric_key, []):
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return float(match.group(1)), True, "parsed_from_output"

    return 0.0, False, "parse_failed"


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="run_benchmark",
            description="벤치마크 명령을 실행하고 공통 benchmark payload를 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "실행할 벤치마크 명령어 (예: 'npm run build', 'python inference.py')",
                    },
                    "metric_key": {
                        "type": "string",
                        "description": "추출할 메트릭 키",
                        "enum": list(SUPPORTED_METRICS),
                        "default": "build_time",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "명령 실행 디렉토리 (기본값: 현재 디렉토리)",
                        "default": ".",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "최대 실행 시간 (초)",
                        "default": 300,
                    },
                },
                "required": ["command"],
            },
        ),
        types.Tool(
            name="compare_metrics",
            description="두 메트릭 값을 비교하여 개선 여부를 판정합니다 (ratchet judge).",
            inputSchema={
                "type": "object",
                "properties": {
                    "baseline": {
                        "type": "number",
                        "description": "이전 (baseline) 메트릭 값",
                    },
                    "current": {
                        "type": "number",
                        "description": "현재 메트릭 값",
                    },
                    "metric_key": {
                        "type": "string",
                        "description": "메트릭 키 (lower_is_better 판단용)",
                        "enum": list(SUPPORTED_METRICS),
                    },
                    "threshold_percent": {
                        "type": "number",
                        "description": "개선 판정 최소 비율 (%)",
                        "default": 1.0,
                    },
                },
                "required": ["baseline", "current", "metric_key"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "run_benchmark":
        command = arguments["command"].strip()
        metric_key = arguments.get("metric_key", "build_time")
        cwd = arguments.get("working_directory", ".")
        timeout = arguments.get("timeout_seconds", 300)

        if not command:
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=0.0,
                    exit_code=2,
                    aux_metrics={"failure_reason": "empty_command"},
                )
            )

        expanded_cwd = os.path.expanduser(cwd)
        if not os.path.isdir(expanded_cwd):
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=0.0,
                    exit_code=2,
                    aux_metrics={
                        "failure_reason": "working_directory_not_found",
                        "working_directory": expanded_cwd,
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
                cwd=expanded_cwd,
                timeout=timeout,
                env={**os.environ},
            )
            duration = time.time() - start

            metric_value, metric_found, metric_source = _parse_metric(
                result.stdout + result.stderr, metric_key
            )

            if metric_key == "build_time" and not metric_found:
                metric_value = duration
                metric_found = True
                metric_source = "duration_fallback"

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
                        "working_directory": expanded_cwd,
                        "metric_found": metric_found,
                        "metric_source": metric_source,
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
                        "working_directory": expanded_cwd,
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
                        "working_directory": expanded_cwd,
                    },
                )
            )

    elif name == "compare_metrics":
        baseline = float(arguments["baseline"])
        current = float(arguments["current"])
        metric_key = arguments["metric_key"]
        threshold = float(arguments.get("threshold_percent", 1.0))
        return text_response(
            compare_metrics_payload(baseline, current, metric_key, threshold)
        )

    return text_response({"success": False, "error": f"Unknown tool: {name}"})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
