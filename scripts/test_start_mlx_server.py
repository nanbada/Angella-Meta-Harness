#!/usr/bin/env python3
"""Regression checks for the MLX server launcher helper."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import start_mlx_server  # noqa: E402


def main() -> int:
    parsed = start_mlx_server.parse_base_url("http://127.0.0.1:11435/v1")
    assert parsed["host"] == "127.0.0.1"
    assert parsed["port"] == 11435
    assert parsed["path"] == "/v1"

    parsed_empty = start_mlx_server.parse_base_url("http://localhost:8080")
    assert parsed_empty["host"] == "localhost"
    assert parsed_empty["port"] == 8080
    assert parsed_empty["path"] == "/"

    try:
        start_mlx_server.parse_base_url("https://127.0.0.1:11435/v1")
    except ValueError as exc:
        assert "Unsupported MLX base URL scheme" in str(exc)
    else:
        raise AssertionError("expected invalid scheme failure")

    try:
        start_mlx_server.parse_base_url("http://127.0.0.1:11435/foo")
    except ValueError as exc:
        assert "Unsupported MLX base URL path" in str(exc)
    else:
        raise AssertionError("expected invalid path failure")

    server_binary = ROOT_DIR / ".cache" / "angella" / "bootstrap-venv" / "bin" / "mlx_lm.server"
    command, endpoint = start_mlx_server.build_server_command(
        server_binary=server_binary,
        model="mlx-community/gemma-4-31b-it-4bit",
        base_url="http://127.0.0.1:11435/v1",
        extra_args=["--log-level", "DEBUG"],
    )
    assert command[:7] == [
        str(server_binary),
        "--model",
        "mlx-community/gemma-4-31b-it-4bit",
        "--host",
        "127.0.0.1",
        "--port",
        "11435",
    ]
    assert command[-2:] == ["--log-level", "DEBUG"]
    rendered = start_mlx_server.format_plan(command, endpoint, "mlx-community/gemma-4-31b-it-4bit")
    assert "command=" in rendered
    assert "host=127.0.0.1" in rendered

    print("mlx server launcher tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
