#!/usr/bin/env python3
"""Validate tracked harness schema, policy, and naming conventions."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

from meta_loop_ops import _required_schema_sections  # noqa: E402


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []

    schema_path = ROOT_DIR / "knowledge" / "schema.md"
    policy_path = ROOT_DIR / "config" / "knowledge-policy.yaml"
    parity_path = ROOT_DIR / "PARITY.md"
    scenario_path = ROOT_DIR / "scripts" / "harness_parity_scenarios.json"

    schema_text = schema_path.read_text(encoding="utf-8")
    for section in _required_schema_sections():
        if section not in schema_text:
            errors.append(f"Missing required schema section: {section}")

    policy = _load_json(policy_path).get("knowledge_policy", {})
    for key in ("indexed_paths", "canonical_entrypoints", "search_provider", "snippet_chars"):
        if key not in policy:
            errors.append(f"Missing knowledge policy key: {key}")

    parity_text = parity_path.read_text(encoding="utf-8")
    scenarios = _load_json(scenario_path).get("lanes", [])
    for lane in scenarios:
        header = f"## Lane {lane['id']} — {lane['title']}"
        if header not in parity_text:
            errors.append(f"Missing parity lane header: {header}")
    for folder in (ROOT_DIR / "knowledge" / "components", ROOT_DIR / "knowledge" / "sources", ROOT_DIR / "knowledge" / "queries"):
        if not folder.exists():
            continue
        for path in folder.glob("*.md"):
            if path.name == "index.md":
                continue
            if not re.match(r"^[a-z0-9][a-z0-9-]*\.md$", path.name):
                errors.append(f"Invalid tracked page naming convention: {path.relative_to(ROOT_DIR)}")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("harness schema validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
