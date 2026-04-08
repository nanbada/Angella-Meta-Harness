#!/usr/bin/env python3
"""Safe MLX runtime probe for Angella bootstrap environments."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BOOTSTRAP_PYTHON = ROOT_DIR / ".cache" / "angella" / "bootstrap-venv" / "bin" / "python"
DEFAULT_TIMEOUT_SECONDS = 20
PROBE_CODE = r"""
import importlib
import json

payload = {}
for module_name in ("mlx", "mlx_lm"):
    module = importlib.import_module(module_name)
    payload[module_name] = getattr(module, "__version__", "unknown")

print(json.dumps(payload, ensure_ascii=False))
"""


def _tail(text: str, *, max_lines: int = 20, max_chars: int = 2000) -> str:
    if not text:
        return ""
    lines = text.strip().splitlines()[-max_lines:]
    trimmed = "\n".join(lines)
    if len(trimmed) <= max_chars:
        return trimmed
    return trimmed[-max_chars:]


def classify_probe_failure(returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
    stdout_full = stdout or ""
    stderr_full = stderr or ""
    stdout_tail = _tail(stdout)
    stderr_tail = _tail(stderr)

    category = "import_failed"
    hint = "Inspect stderr from the probe subprocess."

    if "NSRangeException" in stderr_full and "Metal" in stderr_full:
        category = "metal_device_init_crash"
        hint = (
            "MLX crashed during Metal device initialization. In Codex this often indicates sandbox or "
            "Metal device visibility limits rather than a broken installation."
        )
    elif "No module named" in stderr_full:
        category = "missing_module"
        hint = "The target Python environment does not have mlx/mlx_lm installed."
    elif returncode < 0:
        category = "terminated_by_signal"
        hint = "The probe subprocess terminated via signal before imports completed."
    elif returncode == 124:
        category = "probe_timeout"
        hint = "The probe subprocess timed out."

    return {
        "success": False,
        "category": category,
        "returncode": returncode,
        "hint": hint,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


def run_probe(python_executable: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS, probe_code: str = PROBE_CODE) -> dict[str, Any]:
    python_path = Path(python_executable)
    if python_path.is_absolute() and not python_path.exists():
        return {
            "success": False,
            "category": "python_missing",
            "returncode": 127,
            "hint": f"Python executable not found: {python_executable}",
            "stdout_tail": "",
            "stderr_tail": "",
        }

    try:
        result = subprocess.run(
            [python_executable, "-c", probe_code],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return {
            "success": False,
            "category": "python_missing",
            "returncode": 127,
            "hint": f"Python executable not found: {python_executable}",
            "stdout_tail": "",
            "stderr_tail": "",
        }
    except subprocess.TimeoutExpired as exc:
        return classify_probe_failure(124, exc.stdout or "", exc.stderr or "")

    if result.returncode != 0:
        return classify_probe_failure(result.returncode, result.stdout, result.stderr)

    stdout_tail = _tail(result.stdout)
    try:
        versions = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return {
            "success": False,
            "category": "invalid_probe_output",
            "returncode": result.returncode,
            "hint": "Probe subprocess exited successfully but did not emit valid JSON.",
            "stdout_tail": stdout_tail,
            "stderr_tail": _tail(result.stderr),
        }

    return {
        "success": True,
        "category": "ok",
        "returncode": result.returncode,
        "python": python_executable,
        "versions": versions,
        "stdout_tail": stdout_tail,
        "stderr_tail": _tail(result.stderr),
    }


def format_probe_report(payload: dict[str, Any]) -> str:
    if payload.get("success"):
        versions = payload.get("versions", {})
        return (
            f"MLX runtime probe succeeded for {payload.get('python', '')}\n"
            f"mlx={versions.get('mlx', 'unknown')}\n"
            f"mlx_lm={versions.get('mlx_lm', 'unknown')}"
        ).strip()

    lines = [
        f"MLX runtime probe failed for {payload.get('python', '')}".rstrip(),
        f"category={payload.get('category', 'unknown')}",
        f"returncode={payload.get('returncode', 'unknown')}",
        f"hint={payload.get('hint', '')}",
    ]
    stdout_tail = payload.get("stdout_tail", "")
    stderr_tail = payload.get("stderr_tail", "")
    if stdout_tail:
        lines.append("stdout:")
        lines.append(stdout_tail)
    if stderr_tail:
        lines.append("stderr:")
        lines.append(stderr_tail)
    return "\n".join(lines).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=str(DEFAULT_BOOTSTRAP_PYTHON))
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_probe(args.python, timeout_seconds=args.timeout_seconds)
    payload.setdefault("python", args.python)

    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(format_probe_report(payload))

    return 0 if payload.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
