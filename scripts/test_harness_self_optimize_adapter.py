#!/usr/bin/env python3
"""Smoke checks for benchmark adapters and harness-self-optimize recipe wiring."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

import metric_benchmark  # noqa: E402
import metric_benchmark_python  # noqa: E402


def _payload(contents) -> dict:
    return json.loads(contents[0].text)


async def main() -> int:
    generic = _payload(
        await metric_benchmark.call_tool(
            "run_benchmark",
            {
                "command": "python3 -c \"print('build time: 0.05 s')\"",
                "metric_key": "build_time",
                "working_directory": str(ROOT_DIR),
                "timeout_seconds": 30,
            },
        )
    )
    assert generic["success"] is True
    assert generic["metric_key"] == "build_time"
    assert generic["metric_value"] > 0

    python_payload = _payload(
        await metric_benchmark_python.call_tool(
            "run_benchmark",
            {
                "command": "python3 -c \"print('tokens/s: 42')\"",
                "metric_key": "tokens_per_second",
                "working_directory": str(ROOT_DIR),
                "runs": 1,
                "timeout_seconds": 30,
            },
        )
    )
    assert python_payload["success"] is True
    assert python_payload["metric_key"] == "tokens_per_second"
    assert python_payload["metric_value"] == 42.0

    recipe_text = (ROOT_DIR / "recipes" / "harness-self-optimize.yaml").read_text(encoding="utf-8")
    assert "name: metric-benchmark" in recipe_text
    assert "name: control-plane-admin" in recipe_text
    assert "finalize_accepted_meta_loop_run" in recipe_text
    assert "inspect_control_plane" in recipe_text or "recent telemetry/summary" in recipe_text

    print("harness self-optimize adapter tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
