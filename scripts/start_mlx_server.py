#!/usr/bin/env python3
"""Launch mlx_lm.server using Angella's canonical MLX environment."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BOOTSTRAP_SERVER = ROOT_DIR / ".cache" / "angella" / "bootstrap-venv" / "bin" / "mlx_lm.server"
DEFAULT_BASE_URL = "http://127.0.0.1:11435/v1"
DEFAULT_MODEL = "mlx-community/gemma-4-31b-it-4bit"


def parse_base_url(base_url: str) -> dict[str, object]:
    parsed = urlparse(base_url)
    if parsed.scheme != "http":
        raise ValueError(f"Unsupported MLX base URL scheme: {parsed.scheme or '(missing)'}")
    if not parsed.hostname:
        raise ValueError("MLX base URL must include a host.")
    if parsed.username or parsed.password:
        raise ValueError("MLX base URL must not include embedded credentials.")
    path = parsed.path or ""
    if path not in {"", "/", "/v1"}:
        raise ValueError(f"Unsupported MLX base URL path: {path}. Expected /v1 or empty path.")

    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port or 80,
        "path": path or "/",
    }


def resolve_server_binary(explicit: str | None) -> Path:
    candidate = Path(explicit).expanduser().resolve() if explicit else DEFAULT_BOOTSTRAP_SERVER.resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"mlx_lm.server binary not found: {candidate}")
    return candidate


def build_server_command(
    *,
    server_binary: Path,
    model: str,
    base_url: str,
    extra_args: list[str],
) -> tuple[list[str], dict[str, object]]:
    endpoint = parse_base_url(base_url)
    command = [
        str(server_binary),
        "--model",
        model,
        "--host",
        str(endpoint["host"]),
        "--port",
        str(endpoint["port"]),
        *extra_args,
    ]
    return command, endpoint


def format_plan(command: list[str], endpoint: dict[str, object], model: str) -> str:
    return "\n".join(
        [
            "MLX server launch plan",
            f"model={model}",
            f"host={endpoint['host']}",
            f"port={endpoint['port']}",
            f"base_path={endpoint['path']}",
            f"command={shlex.join(command)}",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("ANGELLA_MLX_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("ANGELLA_MLX_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--server-binary", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("extra_args", nargs=argparse.REMAINDER)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    extra_args = list(args.extra_args)
    if extra_args and extra_args[0] == "--":
        extra_args = extra_args[1:]

    try:
        server_binary = resolve_server_binary(args.server_binary)
        command, endpoint = build_server_command(
            server_binary=server_binary,
            model=args.model,
            base_url=args.base_url,
            extra_args=extra_args,
        )
    except (FileNotFoundError, ValueError) as exc:
        if args.format == "json":
            print(json.dumps({"success": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        else:
            print(str(exc))
        return 1

    payload = {
        "success": True,
        "model": args.model,
        "base_url": args.base_url,
        "host": endpoint["host"],
        "port": endpoint["port"],
        "base_path": endpoint["path"],
        "server_binary": str(server_binary),
        "command": command,
        "dry_run": args.dry_run,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(format_plan(command, endpoint, args.model))

    if args.dry_run:
        return 0

    result = subprocess.run(command, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
