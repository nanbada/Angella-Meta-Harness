#!/usr/bin/env python3
"""
Next.js Metric Benchmark MCP Server
====================================
Next.js 프로젝트 빌드 시간 + 번들 사이즈 + route별 사이즈 측정.
"""

import subprocess
import time
import re
import json
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("metric-benchmark-nextjs")


def _parse_next_build(stdout: str, stderr: str) -> dict:
    """Next.js 빌드 로그에서 메트릭 추출"""
    combined = stdout + stderr
    metrics = {
        "pages": [],
        "total_first_load_kb": 0.0,
        "largest_page_kb": 0.0,
    }

    # Route sizes: "○ /api/hello  2.3 kB"
    route_pattern = r"[○●λƒ]\s+(/\S+)\s+([0-9.]+)\s*(kB|KB|B|MB)"
    for match in re.finditer(route_pattern, combined):
        route, size, unit = match.groups()
        size_kb = float(size)
        if unit in ("B",):
            size_kb /= 1024
        elif unit in ("MB",):
            size_kb *= 1024
        metrics["pages"].append({"route": route, "size_kb": round(size_kb, 2)})
        if size_kb > metrics["largest_page_kb"]:
            metrics["largest_page_kb"] = size_kb

    # First Load JS shared: "First Load JS shared by all  87.3 kB"
    fl_match = re.search(r"First Load JS.*?([0-9.]+)\s*kB", combined)
    if fl_match:
        metrics["total_first_load_kb"] = float(fl_match.group(1))

    return metrics


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="benchmark_nextjs",
            description="Next.js 프로젝트의 빌드 시간, 번들 사이즈, route별 사이즈를 측정합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Next.js 프로젝트 루트 경로",
                    },
                    "build_command": {
                        "type": "string",
                        "description": "빌드 명령어",
                        "default": "npm run build",
                    },
                },
                "required": ["project_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "benchmark_nextjs":
        project_path = os.path.expanduser(arguments["project_path"])
        build_cmd = arguments.get("build_command", "npm run build")

        try:
            start = time.time()
            result = subprocess.run(
                build_cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=300,
                env={**os.environ},
            )
            build_time = round(time.time() - start, 3)

            next_metrics = _parse_next_build(result.stdout, result.stderr)

            output = {
                "metric_key": "build_time",
                "metric_value": build_time,
                "build_time_seconds": build_time,
                "total_first_load_kb": next_metrics["total_first_load_kb"],
                "largest_page_kb": next_metrics["largest_page_kb"],
                "page_count": len(next_metrics["pages"]),
                "pages": next_metrics["pages"][:10],  # Top 10
                "success": result.returncode == 0,
                "log": result.stdout[-1000:],
            }

            return [types.TextContent(type="text", text=json.dumps(output, indent=2, ensure_ascii=False))]

        except subprocess.TimeoutExpired:
            return [types.TextContent(type="text", text=json.dumps({"error": "Build timeout (300s)", "success": False}))]
        except Exception as e:
            return [types.TextContent(type="text", text=json.dumps({"error": str(e), "success": False}))]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
