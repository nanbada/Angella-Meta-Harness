#!/usr/bin/env python3
"""
Swift / SwiftUI Metric Benchmark MCP Server
=============================================
Swift 빌드 시간 + 앱 launch time 측정 (macOS / Xcode).
"""

import subprocess
import time
import re
import json
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

server = Server("metric-benchmark-swift")


def _parse_xcode_log(stdout: str, stderr: str) -> dict:
    """Xcode 빌드 로그에서 메트릭 추출"""
    combined = stdout + stderr
    metrics = {
        "compile_time_seconds": 0.0,
        "link_time_seconds": 0.0,
        "warning_count": 0,
        "error_count": 0,
    }

    # CompileSwiftSources timing
    compile_match = re.search(r"CompileSwift.*?(\d+\.\d+)\s*seconds", combined)
    if compile_match:
        metrics["compile_time_seconds"] = float(compile_match.group(1))

    # Warnings & Errors
    metrics["warning_count"] = len(re.findall(r"warning:", combined))
    metrics["error_count"] = len(re.findall(r"error:", combined))

    return metrics


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="benchmark_swift",
            description="Swift/SwiftUI 프로젝트의 빌드 시간을 측정합니다 (xcodebuild 또는 swift build).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "프로젝트 루트 경로",
                    },
                    "build_command": {
                        "type": "string",
                        "description": "빌드 명령어",
                        "default": "swift build -c release",
                    },
                    "scheme": {
                        "type": "string",
                        "description": "Xcode scheme 이름 (xcodebuild 사용 시)",
                        "default": "",
                    },
                    "clean_build": {
                        "type": "boolean",
                        "description": "클린 빌드 여부 (DerivedData 삭제)",
                        "default": False,
                    },
                },
                "required": ["project_path"],
            },
        ),
        types.Tool(
            name="measure_launch_time",
            description="빌드된 앱/바이너리의 launch time을 측정합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "binary_path": {
                        "type": "string",
                        "description": "실행할 바이너리 경로 (예: .build/release/MyApp)",
                    },
                    "args": {
                        "type": "string",
                        "description": "바이너리에 전달할 인자",
                        "default": "",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "최대 실행 시간 (초)",
                        "default": 30,
                    },
                },
                "required": ["binary_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "benchmark_swift":
        project_path = os.path.expanduser(arguments["project_path"])
        build_cmd = arguments.get("build_command", "swift build -c release")
        scheme = arguments.get("scheme", "")
        clean_build = arguments.get("clean_build", False)

        try:
            # Clean build: DerivedData 삭제
            if clean_build:
                derived = os.path.expanduser("~/Library/Developer/Xcode/DerivedData")
                subprocess.run(f"rm -rf {derived}/*", shell=True, timeout=30)

            # xcodebuild 사용 시 scheme 추가
            if scheme and "xcodebuild" in build_cmd:
                build_cmd = f"xcodebuild -scheme {scheme} -destination 'platform=macOS' build"

            start = time.time()
            result = subprocess.run(
                build_cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=600,  # Swift 빌드는 오래 걸릴 수 있음
                env={**os.environ},
            )
            build_time = round(time.time() - start, 3)

            xcode_metrics = _parse_xcode_log(result.stdout, result.stderr)

            output = {
                "metric_key": "build_time",
                "metric_value": build_time,
                "build_time_seconds": build_time,
                "compile_time_seconds": xcode_metrics["compile_time_seconds"],
                "warnings": xcode_metrics["warning_count"],
                "errors": xcode_metrics["error_count"],
                "success": result.returncode == 0,
                "clean_build": clean_build,
                "log": result.stdout[-800:],
            }

            return [types.TextContent(type="text", text=json.dumps(output, indent=2, ensure_ascii=False))]

        except subprocess.TimeoutExpired:
            return [types.TextContent(type="text", text=json.dumps({"error": "Build timeout (600s)", "success": False}))]
        except Exception as e:
            return [types.TextContent(type="text", text=json.dumps({"error": str(e), "success": False}))]

    elif name == "measure_launch_time":
        binary_path = os.path.expanduser(arguments["binary_path"])
        args = arguments.get("args", "")
        timeout = arguments.get("timeout_seconds", 30)

        try:
            cmd = f"{binary_path} {args}".strip()
            start = time.time()
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            launch_time = round((time.time() - start) * 1000, 2)  # ms

            output = {
                "metric_key": "latency_ms",
                "metric_value": launch_time,
                "launch_time_ms": launch_time,
                "success": result.returncode == 0,
                "stdout": result.stdout[:500],
            }

            return [types.TextContent(type="text", text=json.dumps(output, indent=2, ensure_ascii=False))]

        except subprocess.TimeoutExpired:
            return [types.TextContent(type="text", text=json.dumps({"error": f"Launch timeout ({timeout}s)", "success": False}))]
        except Exception as e:
            return [types.TextContent(type="text", text=json.dumps({"error": str(e), "success": False}))]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
