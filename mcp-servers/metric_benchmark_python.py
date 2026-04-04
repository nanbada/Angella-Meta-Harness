#!/usr/bin/env python3
"""
Python Metric Benchmark MCP Server
====================================
Python inference 속도 (tokens/s, latency) 측정.
MLX 기반 inference 스크립트에 최적화.
"""

import subprocess
import time
import re
import json
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("metric-benchmark-python")


def _parse_python_metrics(stdout: str, stderr: str) -> dict:
    """Python inference 로그에서 성능 메트릭 추출"""
    combined = stdout + stderr
    metrics = {
        "tokens_per_second": 0.0,
        "latency_ms": 0.0,
        "throughput": 0.0,
        "memory_mb": 0.0,
    }

    # tokens/s 패턴들
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

    # Latency
    lat_match = re.search(r"(?:latency|time|elapsed)[:\s]+([0-9]+\.?[0-9]*)\s*(?:ms|millisec)", combined, re.IGNORECASE)
    if lat_match:
        metrics["latency_ms"] = float(lat_match.group(1))

    # Memory
    mem_match = re.search(r"(?:memory|mem|rss)[:\s]+([0-9]+\.?[0-9]*)\s*(?:MB|mb)", combined, re.IGNORECASE)
    if mem_match:
        metrics["memory_mb"] = float(mem_match.group(1))

    return metrics


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="benchmark_python",
            description="Python 스크립트의 inference 속도 (tokens/s), latency, 메모리를 측정합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "실행할 Python 명령어 (예: 'python inference.py --model qwen2.5')",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "실행 디렉토리",
                        "default": ".",
                    },
                    "runs": {
                        "type": "integer",
                        "description": "반복 실행 횟수 (평균값 계산)",
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
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "benchmark_python":
        command = arguments["command"]
        cwd = os.path.expanduser(arguments.get("working_directory", "."))
        runs = arguments.get("runs", 1)
        timeout = arguments.get("timeout_seconds", 120)

        all_metrics = []
        all_durations = []

        for i in range(runs):
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

                if result.returncode != 0:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({
                            "error": f"Run {i+1} failed (exit code {result.returncode})",
                            "stderr": result.stderr[-500:],
                            "success": False,
                        })
                    )]

                metrics = _parse_python_metrics(result.stdout, result.stderr)
                all_metrics.append(metrics)

            except subprocess.TimeoutExpired:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Timeout on run {i+1} ({timeout}s)", "success": False})
                )]

        # 평균 계산
        avg_tps = sum(m["tokens_per_second"] for m in all_metrics) / len(all_metrics) if all_metrics else 0
        avg_lat = sum(m["latency_ms"] for m in all_metrics) / len(all_metrics) if all_metrics else 0
        avg_dur = sum(all_durations) / len(all_durations) if all_durations else 0

        output = {
            "metric_key": "tokens_per_second",
            "metric_value": round(avg_tps, 2),
            "tokens_per_second": round(avg_tps, 2),
            "latency_ms": round(avg_lat, 2),
            "avg_duration_seconds": round(avg_dur, 3),
            "memory_mb": all_metrics[-1]["memory_mb"] if all_metrics else 0,
            "runs_completed": len(all_metrics),
            "success": True,
        }

        return [types.TextContent(type="text", text=json.dumps(output, indent=2, ensure_ascii=False))]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
