#!/usr/bin/env python3
"""Swift benchmark adapter with the shared benchmark schema."""

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

server = Server("metric-benchmark-swift")


def _parse_xcode_log(stdout: str, stderr: str) -> dict:
    combined = stdout + stderr
    metrics = {
        "compile_time_seconds": 0.0,
        "warning_count": len(re.findall(r"warning:", combined)),
        "error_count": len(re.findall(r"error:", combined)),
        "launch_time_ms": 0.0,
    }

    compile_match = re.search(r"CompileSwift.*?(\d+\.\d+)\s*seconds", combined)
    if compile_match:
        metrics["compile_time_seconds"] = float(compile_match.group(1))

    latency_match = re.search(
        r"(?:launch time|startup time|latency)[:\s]+([0-9]+\.?[0-9]*)\s*ms",
        combined,
        re.IGNORECASE,
    )
    if latency_match:
        metrics["launch_time_ms"] = float(latency_match.group(1))

    return metrics


def _run_clean_step(project_path: str, scheme: str, build_command: str) -> tuple[bool, str]:
    if "xcodebuild" in build_command:
        clean_command = "xcodebuild clean"
        if scheme:
            clean_command = f"xcodebuild -scheme {scheme} clean"
    elif build_command.strip().startswith("swift "):
        clean_command = "swift package clean"
    else:
        return False, "clean_build_requested_without_safe_clean_command"

    clean_result = subprocess.run(
        clean_command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=project_path,
        timeout=120,
        env={**os.environ},
    )
    return clean_result.returncode == 0, clean_result.stderr[-400:] or clean_result.stdout[-400:]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="run_benchmark",
            description="Swift 프로젝트를 측정하고 공통 benchmark payload를 반환합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "빌드 또는 측정 명령어",
                        "default": "swift build -c release",
                    },
                    "metric_key": {
                        "type": "string",
                        "enum": ["build_time", "latency_ms"],
                        "default": "build_time",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "프로젝트 루트 경로",
                    },
                    "scheme": {
                        "type": "string",
                        "description": "xcodebuild 사용 시 scheme",
                        "default": "",
                    },
                    "clean_build": {
                        "type": "boolean",
                        "description": "안전한 clean command 실행 여부",
                        "default": False,
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "최대 실행 시간 (초)",
                        "default": 600,
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
    if name in {"run_benchmark", "benchmark_swift", "measure_launch_time"}:
        if name == "measure_launch_time":
            project_path = os.path.expanduser(os.path.dirname(arguments["binary_path"]) or ".")
            command = f'"{os.path.expanduser(arguments["binary_path"])}" {arguments.get("args", "")}'.strip()
            metric_key = "latency_ms"
            scheme = ""
            clean_build = False
            timeout = int(arguments.get("timeout_seconds", 30))
        elif name == "benchmark_swift":
            project_path = os.path.expanduser(arguments["project_path"])
            command = arguments.get("build_command", "swift build -c release")
            metric_key = arguments.get("metric_key", "build_time")
            scheme = arguments.get("scheme", "")
            clean_build = bool(arguments.get("clean_build", False))
            timeout = int(arguments.get("timeout_seconds", 600))
        else:
            project_path = os.path.expanduser(arguments["working_directory"])
            command = arguments.get("command", "swift build -c release")
            metric_key = arguments.get("metric_key", "build_time")
            scheme = arguments.get("scheme", "")
            clean_build = bool(arguments.get("clean_build", False))
            timeout = int(arguments.get("timeout_seconds", 600))

        if metric_key not in {"build_time", "latency_ms"}:
            return text_response(
                build_benchmark_payload(
                    success=False,
                    metric_key=metric_key,
                    metric_value=0.0,
                    duration_seconds=0.0,
                    exit_code=2,
                    aux_metrics={"failure_reason": "unsupported_metric_for_swift"},
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
            if clean_build:
                clean_ok, clean_detail = _run_clean_step(project_path, scheme, command)
                if not clean_ok:
                    return text_response(
                        build_benchmark_payload(
                            success=False,
                            metric_key=metric_key,
                            metric_value=0.0,
                            duration_seconds=0.0,
                            exit_code=2,
                            aux_metrics={
                                "failure_reason": clean_detail,
                                "command": command,
                                "working_directory": project_path,
                            },
                        )
                    )

            if scheme and "xcodebuild" in command and "-scheme" not in command:
                command = f"xcodebuild -scheme {scheme} -destination 'platform=macOS' build"

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

            parsed = _parse_xcode_log(result.stdout, result.stderr)
            metric_value = duration if metric_key == "build_time" else parsed["launch_time_ms"]
            metric_found = metric_key == "build_time" or parsed["launch_time_ms"] > 0
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
                        "clean_build": clean_build,
                        "compile_time_seconds": parsed["compile_time_seconds"],
                        "warning_count": parsed["warning_count"],
                        "error_count": parsed["error_count"],
                        "launch_time_ms": parsed["launch_time_ms"],
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
