#!/usr/bin/env python3
"""Regression checks for file-backed Scion coordination."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT_DIR / "mcp-servers" / "scion_coordination_ops.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("scion_coordination_ops", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _text(response: dict) -> str:
    return response["content"][0]["text"]


def main() -> int:
    module = _load_module()

    with tempfile.TemporaryDirectory() as tmp_root:
        shared_dir = Path(tmp_root) / "shared"
        original_env = {
            "SCION_SHARED_DIR": os.environ.get("SCION_SHARED_DIR"),
            "SCION_AGENT_ID": os.environ.get("SCION_AGENT_ID"),
            "SCION_TTL_SECONDS": os.environ.get("SCION_TTL_SECONDS"),
        }

        try:
            os.environ["SCION_SHARED_DIR"] = str(shared_dir)
            os.environ["SCION_AGENT_ID"] = "angella-alpha"
            os.environ["SCION_TTL_SECONDS"] = "120"

            claim = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_claim_files",
                    "arguments": {
                        "files": ["src/frontend", "./docs/PARITY.md"],
                        "intent": "Refactor frontend and parity docs",
                    },
                }
            )
            assert "Claimed 2 file(s)" in _text(claim)

            broadcast = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_broadcast",
                    "arguments": {
                        "message": "Starting Phase 7 coordination work",
                        "status": "active",
                    },
                }
            )
            assert "Broadcast recorded" in _text(broadcast)

            alpha_state = json.loads((shared_dir / "agents" / "angella-alpha.json").read_text(encoding="utf-8"))
            assert alpha_state["status"] == "active"
            assert alpha_state["claimed_files"] == ["docs/PARITY.md", "src/frontend"]

            inspect = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_inspect_state",
                    "arguments": {"event_limit": 5},
                }
            )
            inspect_text = _text(inspect)
            assert "Active agents:" in inspect_text
            assert "angella-alpha status=active" in inspect_text
            assert "Recent events:" in inspect_text

            os.environ["SCION_AGENT_ID"] = "angella-beta"
            query = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_query_peers",
                    "arguments": {
                        "query": "Can I modify the frontend?",
                        "candidate_files": ["src/frontend", "README.md"],
                    },
                }
            )
            text = _text(query)
            assert "Conflicts detected with active peers" in text
            assert "angella-alpha -> src/frontend" in text

            strict_conflict = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_claim_files",
                    "arguments": {
                        "files": ["src/frontend"],
                        "strict": True,
                    },
                }
            )
            assert "error" in strict_conflict
            assert "Conflicting Scion claims detected" in strict_conflict["error"]

            overlap_warning = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_claim_files",
                    "arguments": {
                        "files": ["src/frontend"],
                        "strict": False,
                    },
                }
            )
            assert "Warning: overlapping claims" in _text(overlap_warning)

            heartbeat = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_heartbeat",
                    "arguments": {
                        "status": "waiting",
                        "message": "waiting for alpha to finish",
                    },
                }
            )
            assert "Heartbeat recorded" in _text(heartbeat)

            beta_state = json.loads((shared_dir / "agents" / "angella-beta.json").read_text(encoding="utf-8"))
            assert beta_state["status"] == "waiting"
            assert beta_state["claimed_files"] == ["src/frontend"]

            os.environ["SCION_AGENT_ID"] = "angella-alpha"
            release = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_release_claims",
                    "arguments": {
                        "files": ["src/frontend"],
                        "note": "frontend work completed",
                    },
                }
            )
            assert "Released 1 claim(s)" in _text(release)
            assert "docs/PARITY.md" not in _text(release)

            alpha_state_after_release = json.loads((shared_dir / "agents" / "angella-alpha.json").read_text(encoding="utf-8"))
            assert alpha_state_after_release["claimed_files"] == ["docs/PARITY.md"]

            stale_peer = {
                "agent_id": "angella-stale",
                "status": "active",
                "intent": "old work",
                "message": "stale",
                "claimed_files": ["scripts/setup.sh"],
                "metadata": {},
                "updated_at": "2000-01-01T00:00:00+00:00",
                "updated_at_epoch": 0.0,
                "expires_at_epoch": 1.0,
            }
            (shared_dir / "agents").mkdir(parents=True, exist_ok=True)
            (shared_dir / "agents" / "angella-stale.json").write_text(
                json.dumps(stale_peer, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            old_event_path = shared_dir / "events" / "1-angella-stale-broadcast.json"
            old_event_path.parent.mkdir(parents=True, exist_ok=True)
            old_event_path.write_text(
                json.dumps({"agent_id": "angella-stale", "kind": "broadcast", "timestamp": "2000-01-01T00:00:00+00:00", "payload": {}}, indent=2),
                encoding="utf-8",
            )

            prune = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_prune_stale",
                    "arguments": {"event_retention_seconds": 60},
                }
            )
            assert "Pruned 1 stale agent state file(s)" in _text(prune)
            assert not (shared_dir / "agents" / "angella-stale.json").exists()
            assert not old_event_path.exists()

            os.environ["SCION_AGENT_ID"] = "angella-beta"
            no_conflict = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_query_peers",
                    "arguments": {
                        "query": "Any active setup work?",
                        "candidate_files": ["scripts/setup.sh"],
                    },
                }
            )
            assert "No direct conflicts detected" in _text(no_conflict)
            assert "angella-stale" not in _text(no_conflict)
        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    print("scion coordination tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
