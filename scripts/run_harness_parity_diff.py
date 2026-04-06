#!/usr/bin/env python3
"""Validate PARITY.md against the canonical lane scenario map and parity state."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "mcp-servers"))

from meta_loop_ops import search_harness_knowledge  # noqa: E402


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _control_plane_root() -> Path:
    configured = os.environ.get("ANGELLA_CONTROL_PLANE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return ROOT_DIR / ".cache" / "angella" / "control-plane"


def _lane_section(parity_text: str, lane_id: int, title: str) -> str:
    pattern = re.compile(
        rf"^## Lane {lane_id} — {re.escape(title)}\n(?P<body>.*?)(?=^## Lane |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(parity_text)
    return match.group(0) if match else ""


def _recovery_hint(repo_root: Path, lane: dict, errors: list[str]) -> str:
    query = f"{lane['title']} {' '.join(errors[:2])}".strip()
    search = search_harness_knowledge(query, limit=3, repo_root=repo_root)
    if search.get("results"):
        pages = ", ".join(item["relpath"] for item in search["results"][:3])
        return f"Review related knowledge first: {pages}"
    return "Review PARITY.md, the scenario map, and the referenced evidence paths."


def _close_parity_failure_if_present(control_plane_root: Path, lane_id: int) -> None:
    open_path = control_plane_root / "failures" / "open" / f"parity-lane-{lane_id}.json"
    if not open_path.exists():
        return
    payload = _load_json(open_path)
    payload["status"] = "closed"
    payload["closed_at"] = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    closed_path = control_plane_root / "failures" / "closed" / open_path.name
    _json_dump(closed_path, payload)
    open_path.unlink()


def _write_parity_failure(control_plane_root: Path, lane_id: int, lane: dict, errors: list[str], recovery_hint: str) -> None:
    payload = {
        "component": "parity",
        "failure_type": "parity_lane_mismatch",
        "lane_id": lane_id,
        "title": lane["title"],
        "status": "open",
        "expected": lane["status"],
        "observed": errors,
        "recovery_hint": recovery_hint,
        "source_run_id": "parity-audit",
    }
    target = control_plane_root / "failures" / "open" / f"parity-lane-{lane_id}.json"
    _json_dump(target, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parity-file", default=str(ROOT_DIR / "PARITY.md"))
    parser.add_argument("--scenario-file", default=str(ROOT_DIR / "scripts" / "harness_parity_scenarios.json"))
    parser.add_argument("--state-file", default="")
    args = parser.parse_args()

    parity_file = Path(args.parity_file).resolve()
    scenario_file = Path(args.scenario_file).resolve()
    repo_root = parity_file.parent
    control_plane_root = _control_plane_root()
    state_file = Path(args.state_file).resolve() if args.state_file else control_plane_root / "parity-state.json"

    parity_text = parity_file.read_text(encoding="utf-8")
    scenarios = _load_json(scenario_file).get("lanes", [])
    existing_state = _load_json(state_file) if state_file.exists() else {"lanes": []}
    existing_by_id = {int(item.get("lane_id", -1)): item for item in existing_state.get("lanes", []) if isinstance(item, dict)}
    existing_lane_ids = {int(item.get("lane_id", -1)) for item in existing_state.get("lanes", []) if isinstance(item, dict)}

    control_plane_root.joinpath("failures", "open").mkdir(parents=True, exist_ok=True)
    control_plane_root.joinpath("failures", "closed").mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    lane_states: list[dict[str, object]] = []
    if "scripts/run_harness_parity_diff.py" not in parity_text:
        errors.append("PARITY.md is missing the canonical diff-runner reference.")
    scenario_lane_ids = {int(lane["id"]) for lane in scenarios}
    if existing_lane_ids and existing_lane_ids != scenario_lane_ids:
        errors.append("parity-state.json lane IDs do not match the scenario map.")

    for lane in scenarios:
        lane_id = int(lane["id"])
        title = str(lane["title"])
        lane_errors: list[str] = []
        section = _lane_section(parity_text, lane_id, title)
        if not section:
            lane_errors.append(f"Missing lane section: {lane_id} / {title}")
        else:
            status_line = f"- Status: {lane['status']}"
            if status_line not in section:
                lane_errors.append(f"Lane {lane_id} status mismatch: expected `{status_line}`")
            for evidence in lane.get("evidence", []):
                if evidence not in section:
                    lane_errors.append(f"Lane {lane_id} missing evidence reference: {evidence}")
                if not (repo_root / evidence).exists():
                    lane_errors.append(f"Lane {lane_id} evidence path does not exist: {evidence}")

        previous = existing_by_id.get(lane_id, {})
        if previous and str(previous.get("title", "")) != title:
            lane_errors.append(f"Lane {lane_id} title mismatch with parity-state.json")

        hint = _recovery_hint(repo_root, lane, lane_errors) if lane_errors else ""
        lane_state = {
            "lane_id": lane_id,
            "title": title,
            "status": "failed" if lane_errors else str(lane["status"]),
            "last_checked_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "evidence_paths": lane.get("evidence", []),
            "failure_reason": "; ".join(lane_errors),
            "recovery_hint": hint,
        }
        lane_states.append(lane_state)
        if lane_errors:
            errors.extend(lane_errors)
            _write_parity_failure(control_plane_root, lane_id, lane, lane_errors, hint)
        else:
            _close_parity_failure_if_present(control_plane_root, lane_id)

    state_payload = {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "parity_file": str(parity_file),
        "scenario_file": str(scenario_file),
        "lane_count": len(lane_states),
        "lanes": lane_states,
    }
    _json_dump(state_file, state_payload)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(f"parity diff passed: {len(scenarios)} lanes verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
