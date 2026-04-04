#!/usr/bin/env python3
"""
Generic Metric Benchmark MCP Server
====================================
MLX 최적화된 범용 벤치마크 실행 + objective metric 추출.
Goose의 Autoresearch ratchet loop에서 호출됩니다.

Usage (stdio MCP):
  python metric_benchmark.py
"""

import subprocess
import time
import re
import json
import os
import sys
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("metric-benchmark")


def _parse_metric(stdout: str, metric_key: str) -> float:
    """stdout에서 metric_key에 해당하는 숫자 값 추출"""
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
        match = re.search(pattern, stdout, re.IGNORECASE)
        if match:
            return float(match.group(1))

    # Fallback: 마지막으로 나타나는 숫자
    numbers = re.findall(r"([0-9]+\.?[0-9]+)", stdout)
    if numbers:
        return float(numbers[-1])

    return 0.0


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="run_benchmark",
            description="벤치마크 명령을 실행하고 objective metric을 추출합니다. MLX 최적화 환경에서 동작합니다.",
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
                        "enum": [
                            "tokens_per_second",
                            "build_time",
                            "latency_ms",
                            "bundle_size",
                        ],
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
                        "enum": [
                            "tokens_per_second",
                            "build_time",
                            "latency_ms",
                            "bundle_size",
                        ],
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
        command = arguments["command"]
        metric_key = arguments.get("metric_key", "build_time")
        cwd = arguments.get("working_directory", ".")
        timeout = arguments.get("timeout_seconds", 300)

        try:
            start = time.time()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=os.path.expanduser(cwd),
                timeout=timeout,
                env={**os.environ},
            )
            duration = time.time() - start

            metric_value = _parse_metric(
                result.stdout + result.stderr, metric_key
            )

            # build_time의 경우 duration을 기본값으로 사용
            if metric_key == "build_time" and metric_value == 0.0:
                metric_value = round(duration, 3)

            output = {
                "metric_key": metric_key,
                "metric_value": metric_value,
                "duration_seconds": round(duration, 3),
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout_tail": result.stdout[-1500:] if result.stdout else "",
                "stderr_tail": result.stderr[-500:] if result.stderr else "",
            }

            return [types.TextContent(type="text", text=json.dumps(output, indent=2, ensure_ascii=False))]

        except subprocess.TimeoutExpired:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": f"Timeout after {timeout}s", "success": False}
                    ),
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "success": False}),
                )
            ]

    elif name == "compare_metrics":
        baseline = arguments["baseline"]
        current = arguments["current"]
        metric_key = arguments["metric_key"]
        threshold = arguments.get("threshold_percent", 1.0)

        # lower_is_better: build_time, latency_ms, bundle_size
        # higher_is_better: tokens_per_second
        lower_is_better = metric_key in ("build_time", "latency_ms", "bundle_size")

        if baseline == 0:
            improvement_pct = 100.0 if current != 0 else 0.0
        else:
            if lower_is_better:
                improvement_pct = ((baseline - current) / baseline) * 100
            else:
                improvement_pct = ((current - baseline) / baseline) * 100

        is_improved = improvement_pct >= threshold

        output = {
            "metric_key": metric_key,
            "baseline": baseline,
            "current": current,
            "improvement_percent": round(improvement_pct, 2),
            "is_improved": is_improved,
            "verdict": "✅ KEEP (ratchet forward)" if is_improved else "❌ REVERT (no improvement)",
            "direction": "lower_is_better" if lower_is_better else "higher_is_better",
        }

        return [types.TextContent(type="text", text=json.dumps(output, indent=2, ensure_ascii=False))]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
