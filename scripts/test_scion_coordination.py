#!/usr/bin/env python3
"""Regression checks for file-backed Scion coordination."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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

            worktree = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_register_worktree",
                    "arguments": {
                        "worktree_path": str(Path(tmp_root) / "wt-alpha"),
                        "branch": "codex/scion-alpha",
                        "base_branch": "main",
                        "clean": True,
                    },
                }
            )
            assert "Registered worktree" in _text(worktree)

            claim = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_claim_files",
                    "arguments": {
                        "files": ["src/frontend", "./docs/PARITY.md"],
                        "intent": "Refactor frontend and parity docs",
                        "mode": "exclusive",
                    },
                }
            )
            assert "Claimed 2 file(s)" in _text(claim)
            assert "Claim mode: exclusive" in _text(claim)

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
            assert alpha_state["worktree"]["branch"] == "codex/scion-alpha"
            assert (shared_dir / "claims" / "docs" / "PARITY.md.json").is_file()
            assert (shared_dir / "claims" / "src" / "frontend.json").is_file()

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
            assert "worktree=branch=codex/scion-alpha" in inspect_text
            assert "Authoritative claims:" in inspect_text
            assert "Recent events:" in inspect_text

            os.environ["SCION_AGENT_ID"] = "angella-beta"
            query = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_query_peers",
                    "arguments": {
                        "query": "Can I modify the frontend?",
                        "candidate_files": ["src/frontend/App.tsx", "README.md"],
                    },
                }
            )
            text = _text(query)
            assert "Conflicts detected with active peers" in text
            assert "angella-alpha -> src/frontend/App.tsx (peer claim: src/frontend)" in text

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

            beta_worktree = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_register_worktree",
                    "arguments": {
                        "worktree_path": str(Path(tmp_root) / "wt-beta"),
                        "branch": "codex/scion-beta",
                        "base_branch": "main",
                        "clean": True,
                    },
                }
            )
            assert "Registered worktree" in _text(beta_worktree)

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

            takeover = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_claim_files",
                    "arguments": {
                        "files": ["docs/PARITY.md"],
                        "mode": "takeover",
                        "takeover_from": "angella-alpha",
                        "intent": "Take over parity documentation",
                    },
                }
            )
            takeover_text = _text(takeover)
            assert "Claim mode: takeover" in takeover_text
            assert "Took over exact claims from: angella-alpha" in takeover_text

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
            assert beta_state["claimed_files"] == ["docs/PARITY.md", "src/frontend"]
            assert beta_state["worktree"]["branch"] == "codex/scion-beta"

            alpha_state_after_takeover = json.loads((shared_dir / "agents" / "angella-alpha.json").read_text(encoding="utf-8"))
            assert alpha_state_after_takeover["claimed_files"] == ["src/frontend"]
            parity_claim = json.loads((shared_dir / "claims" / "docs" / "PARITY.md.json").read_text(encoding="utf-8"))
            assert parity_claim["agent_id"] == "angella-beta"

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
            assert alpha_state_after_release["claimed_files"] == []
            assert not (shared_dir / "claims" / "src" / "frontend.json").exists()

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
            (shared_dir / "claims").mkdir(parents=True, exist_ok=True)
            (shared_dir / "claims" / "scripts").mkdir(parents=True, exist_ok=True)
            (shared_dir / "claims" / "scripts" / "setup.sh.json").write_text(
                json.dumps(
                    {
                        "agent_id": "angella-stale",
                        "claimed_path": "scripts/setup.sh",
                        "claim_mode": "exclusive",
                        "intent": "old work",
                        "message": "stale claim",
                        "metadata": {},
                        "worktree": {},
                        "claimed_at": "2000-01-01T00:00:00+00:00",
                        "claimed_at_epoch": 0.0,
                        "expires_at_epoch": 1.0,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
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
            assert "Pruned 1 stale agent state file(s) 1 stale claim file(s)" in _text(prune)
            assert not (shared_dir / "agents" / "angella-stale.json").exists()
            assert not (shared_dir / "claims" / "scripts" / "setup.sh.json").exists()
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

            repo_root = Path(tmp_root) / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", "-b", "main", str(repo_root)], check=True, capture_output=True, text=True)
            (repo_root / "README.md").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo_root), "add", "README.md"], check=True, capture_output=True, text=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "-c",
                    "user.name=Scion Test",
                    "-c",
                    "user.email=scion@example.com",
                    "commit",
                    "-m",
                    "init",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            os.environ["SCION_AGENT_ID"] = "angella-gamma"
            gamma_worktree_path = Path(tmp_root) / "wt-gamma"
            prepared = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_prepare_worktree",
                    "arguments": {
                        "repo_root": str(repo_root),
                        "worktree_path": str(gamma_worktree_path),
                        "branch": "codex/scion-gamma",
                        "base_branch": "main",
                    },
                }
            )
            prepared_text = _text(prepared)
            assert "Prepared worktree for angella-gamma" in prepared_text
            assert gamma_worktree_path.is_dir()
            current_branch = subprocess.run(
                ["git", "-C", str(gamma_worktree_path), "branch", "--show-current"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            assert current_branch == "codex/scion-gamma"
            assert (shared_dir / "worktrees" / "codex" / "scion-gamma.json").is_file()

            inspect_after_prepare = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_inspect_state",
                    "arguments": {"event_limit": 10},
                }
            )
            inspect_after_prepare_text = _text(inspect_after_prepare)
            assert "Reserved worktrees:" in inspect_after_prepare_text
            assert "branch=codex/scion-gamma" in inspect_after_prepare_text

            os.environ["SCION_AGENT_ID"] = "angella-delta"
            conflicting_worktree = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_prepare_worktree",
                    "arguments": {
                        "repo_root": str(repo_root),
                        "worktree_path": str(Path(tmp_root) / "wt-delta"),
                        "branch": "codex/scion-gamma",
                        "base_branch": "main",
                    },
                }
            )
            assert "error" in conflicting_worktree
            assert "Conflicting Scion worktree reservations detected" in conflicting_worktree["error"]

            os.environ["SCION_AGENT_ID"] = "angella-gamma"
            removed = module.handle_request(
                {
                    "type": "call_tool",
                    "name": "scion_remove_worktree",
                    "arguments": {
                        "repo_root": str(repo_root),
                        "branch": "codex/scion-gamma",
                        "worktree_path": str(gamma_worktree_path),
                    },
                }
            )
            assert "Removed worktree for angella-gamma" in _text(removed)
            assert not gamma_worktree_path.exists()
            assert not (shared_dir / "worktrees" / "codex" / "scion-gamma.json").exists()
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
