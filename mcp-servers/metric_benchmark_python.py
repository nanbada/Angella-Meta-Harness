#!/usr/bin/env python3
"""Python benchmark adapter with the shared benchmark schema."""

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

server = Server("metric-benchmark-python")


def _parse_python_metrics(stdout: str, stderr: str) -> dict:
    combined = stdout + stderr
    metrics = {
        "tokens_per_second": 0.0,
        "latency_ms": 0.0,
        "memory_mb": 0.0,
    }

    tps_patterns = [
        r"tokens?[/_\s](?:per[_\s])?s(?:ec)?[:\s]+([0-9]+\.?[0-9]*)",
        r"([0-9]+\.?[0-9]*)\s*(?:tok(?:en)?s?/s)",
        r"throughput[:\s]+([0-9]+\.?[0-9]*)",
        r"speed[:\s]+([0-9]+\.?[0-9]*)",
    ]
    for pattern in tps_patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            metrics["tokens_per_second"] = float(match.group(1))
            break

    lat_match = re.search(
        r"(?:latency|time|elapsed)[:\s]+([0-9]+\.?[0-9]*)\s*(?:ms|millisec)",
        combined,
        re.IGNORECASE,
    )
    if lat_match:
        metrics["latency_ms"] = float(lat_match.group(1))

    mem_match = re.search(
        r"(?:memory|mem|rss)[:\s]+([0-9]+\.?[0-9]*)\s*(?:MB|mb)",
        combined,
        re.IGNORECASE,
    )
    if mem_match:
        metrics["memory_mb"] = float(mem_match.group(1))

    return metrics


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="run_benchmark",
            description="Python 스크립트를 측정하고 공통 benchmark payload를 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "실행할 Python 명령어",
                    },
                    "metric_key": {
                        "type": "string",
                        "enum": ["tokens_per_second", "latency_ms"],
                        "default": "tokens_per_second",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "실행 디렉토리",
                        "default": ".",
                    },
                    "runs": {
                        "type": "integer",
                        "description": "반복 실행 횟수",
                        "default": 1,
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "각 실행당 최대 시간 (초)",
                        "default": 120,
                    },
                },
                "required": ["command"],
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
    if name in {"run_benchmark", "benchmark_python"}:
        if name == "benchmark_python":
            command = arguments["command"]
            metric_key = arguments.get("metric_key", "tokens_per_second")
            cwd = os.path.expanduser(arguments.get("working_directory", "."))
            runs = int(arguments.get("runs", 1))
            timeout = int(arguments.get("timeout_seconds", 120))
        else:
            command = arguments["command"]
            metric_key = arguments.get("metric_key", "tokens_per_second")
            cwd = os.path.expanduser(arguments.get("working_directory", "."))
            runs = int(arguments.get("runs", 1))
            timeout = int(arguments.get("timeout_seconds", 120))

        if metric_key not in {"tokens_per_second", "latency_ms"}:
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=0.0,
                    exit_code=2,
                    aux_metrics={"failure_reason": "unsupported_metric_for_python"},
                )
            )

        if not os.path.isdir(cwd):
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=0.0,
                    exit_code=2,
                    aux_metrics={
                        "failure_reason": "working_directory_not_found",
                        "working_directory": cwd,
                    },
                )
            )

        all_metrics = []
        all_durations = []
        last_stdout = ""
        last_stderr = ""
        last_exit_code = 0

        for run_index in range(runs):
            try:
                start = time.time()
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=timeout,
                    env={**os.environ},
                )
                duration = time.time() - start
                all_durations.append(duration)
                last_stdout = result.stdout
                last_stderr = result.stderr
                last_exit_code = result.returncode

                if result.returncode != 0:
                    return text_response(
                        build_benchmark_payload(
                            success=False,
                            metric_key=metric_key,
                            metric_value=0.0,
                            duration_seconds=duration,
                            exit_code=result.returncode,
                            stdout=result.stdout,
                            stderr=result.stderr,
                            aux_metrics={
                                "failure_reason": "command_failed",
                                "command": command,
                                "working_directory": cwd,
                                "failed_run_index": run_index + 1,
                            },
                        )
                    )

                all_metrics.append(_parse_python_metrics(result.stdout, result.stderr))
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
                            "working_directory": cwd,
                            "failed_run_index": run_index + 1,
                        },
                    )
                )

        avg_duration = sum(all_durations) / len(all_durations) if all_durations else 0.0
        avg_tokens = (
            sum(item["tokens_per_second"] for item in all_metrics) / len(all_metrics)
            if all_metrics
            else 0.0
        )
        avg_latency = (
            sum(item["latency_ms"] for item in all_metrics) / len(all_metrics)
            if all_metrics
            else 0.0
        )
        metric_value = avg_tokens if metric_key == "tokens_per_second" else avg_latency
        metric_found = metric_value > 0

        return text_response(
            build_benchmark_payload(
                success=metric_found,
                metric_key=metric_key,
                metric_value=metric_value,
                duration_seconds=avg_duration,
                exit_code=last_exit_code,
                stdout=last_stdout,
                stderr=last_stderr,
                aux_metrics={
                    "command": command,
                    "working_directory": cwd,
                    "runs_completed": len(all_metrics),
                    "tokens_per_second": round(avg_tokens, 4),
                    "latency_ms": round(avg_latency, 4),
                    "memory_mb": all_metrics[-1]["memory_mb"] if all_metrics else 0.0,
                    "failure_reason": "" if metric_found else "metric_parse_failed",
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
