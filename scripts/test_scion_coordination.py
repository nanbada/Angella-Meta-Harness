#!/usr/bin/env python3
"""Regression checks for file-backed and sqlite-backed Scion coordination."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
from pathlib import Path
import sqlite3

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

def _inject_stale_data(shared_dir: Path, backend: str):
    if backend == "file":
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
        (shared_dir / "agents" / "angella-stale.json").write_text(json.dumps(stale_peer, indent=2, ensure_ascii=False), encoding="utf-8")
        (shared_dir / "claims").mkdir(parents=True, exist_ok=True)
        (shared_dir / "claims" / "scripts").mkdir(parents=True, exist_ok=True)
        (shared_dir / "claims" / "scripts" / "setup.sh.json").write_text(
            json.dumps({
                "agent_id": "angella-stale",
                "claimed_path": "scripts/setup.sh",
                "mode": "exclusive",
                "intent": "old work",
                "message": "stale claim",
                "metadata": {},
                "worktree": {},
                "claimed_at": "2000-01-01T00:00:00+00:00",
                "claimed_at_epoch": 0.0,
                "expires_at_epoch": 1.0,
            }, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        old_event_path = shared_dir / "events" / "1-angella-stale-broadcast.json"
        old_event_path.parent.mkdir(parents=True, exist_ok=True)
        old_event_path.write_text(
            json.dumps({"agent_id": "angella-stale", "kind": "broadcast", "timestamp": "2000-01-01T00:00:00+00:00", "payload": {}}, indent=2), encoding="utf-8"
        )
    elif backend == "sqlite":
        conn = sqlite3.connect(shared_dir / "scion.db")
        conn.execute("INSERT INTO agents (agent_id, status, intent, message, claimed_files, updated_at, expires_at_epoch) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     ("angella-stale", "active", "old work", "stale", '["scripts/setup.sh"]', "2000-01-01T00:00:00+00:00", 1.0))
        conn.execute("INSERT INTO claims (claimed_path, agent_id, mode, exclusions, expires_at_epoch, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                     ("scripts/setup.sh", "angella-stale", "exclusive", "[]", 1.0, "{}"))
        conn.execute("INSERT INTO events (agent_id, kind, message, timestamp, payload) VALUES (?, ?, ?, ?, ?)",
                     ("angella-stale", "broadcast", "stale claim", "2000-01-01T00:00:00+00:00", "{}"))
        # Hack timestamp for events query
        conn.execute("UPDATE events SET timestamp = '2000-01-01T00:00:00+00:00' WHERE agent_id = 'angella-stale'")
        conn.commit()
        conn.close()

def _verify_stale_pruned(shared_dir: Path, backend: str):
    if backend == "file":
        assert not (shared_dir / "agents" / "angella-stale.json").exists()
        assert not (shared_dir / "claims" / "scripts" / "setup.sh.json").exists()
        assert not (shared_dir / "events" / "1-angella-stale-broadcast.json").exists()
    elif backend == "sqlite":
        conn = sqlite3.connect(shared_dir / "scion.db")
        agents = conn.execute("SELECT * FROM agents WHERE agent_id = 'angella-stale'").fetchall()
        assert len(agents) == 0
        claims = conn.execute("SELECT * FROM claims WHERE claimed_path = 'scripts/setup.sh'").fetchall()
        assert len(claims) == 0
        events = conn.execute("SELECT * FROM events WHERE agent_id = 'angella-stale'").fetchall()
        assert len(events) == 0
        conn.close()

def _get_agent_state(shared_dir: Path, backend: str, agent_id: str) -> dict:
    if backend == "file":
        path = shared_dir / "agents" / f"{agent_id}.json"
        if not path.exists(): return {}
        return json.loads(path.read_text(encoding="utf-8"))
    elif backend == "sqlite":
        conn = sqlite3.connect(shared_dir / "scion.db")
        row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        conn.close()
        if not row: return {}
        return {
            "status": row[1], "intent": row[2], "message": row[3],
            "claimed_files": json.loads(row[5] or "[]"),
            "worktree": json.loads(row[6] or "{}")
        }
    return {}

def _get_claim(shared_dir: Path, backend: str, path: str) -> dict:
    if backend == "file":
        p = shared_dir / "claims" / f"{path}.json"
        if not p.exists(): return {}
        return json.loads(p.read_text(encoding="utf-8"))
    elif backend == "sqlite":
        conn = sqlite3.connect(shared_dir / "scion.db")
        row = conn.execute("SELECT * FROM claims WHERE claimed_path = ?", (path,)).fetchone()
        conn.close()
        if not row: return {}
        return {
            "agent_id": row[1],
            "exclusions": json.loads(row[3] or "[]")
        }
    return {}

def _has_worktree(shared_dir: Path, backend: str, branch: str) -> bool:
    if backend == "file":
        return (shared_dir / "worktrees" / f"{branch}.json").exists()
    elif backend == "sqlite":
        conn = sqlite3.connect(shared_dir / "scion.db")
        row = conn.execute("SELECT * FROM worktrees WHERE branch = ?", (branch,)).fetchone()
        conn.close()
        return row is not None
    return False

def run_test_suite_for_backend(module, backend: str, tmp_root: str):
    shared_dir = Path(tmp_root) / "shared"
    os.environ["SCION_SHARED_DIR"] = str(shared_dir)
    os.environ["SCION_AGENT_ID"] = "angella-alpha"
    os.environ["SCION_TTL_SECONDS"] = "120"
    os.environ["SCION_BACKEND"] = backend

    worktree = module.handle_request({
        "type": "call_tool",
        "name": "scion_register_worktree",
        "arguments": {
            "worktree_path": str(Path(tmp_root) / "wt-alpha"),
            "branch": "codex/scion-alpha",
            "base_branch": "main",
            "clean": True,
        },
    })
    assert "Registered worktree" in _text(worktree)

    claim = module.handle_request({
        "type": "call_tool",
        "name": "scion_claim_files",
        "arguments": {
            "files": ["src/frontend", "./docs/PARITY.md"],
            "intent": "Refactor frontend and parity docs",
            "mode": "exclusive",
        },
    })
    assert "Claimed 2 file(s)" in _text(claim)
    assert "Claim mode: exclusive" in _text(claim)

    broadcast = module.handle_request({
        "type": "call_tool",
        "name": "scion_broadcast",
        "arguments": {"message": "Starting Phase 7 coordination work", "status": "active"},
    })
    assert "Broadcast recorded" in _text(broadcast)

    alpha_state = _get_agent_state(shared_dir, backend, "angella-alpha")
    assert alpha_state["status"] == "active"
    assert "docs/PARITY.md" in alpha_state["claimed_files"]
    assert "src/frontend" in alpha_state["claimed_files"]
    assert alpha_state["worktree"]["branch"] == "codex/scion-alpha"
    
    assert _get_claim(shared_dir, backend, "docs/PARITY.md")["agent_id"] == "angella-alpha"
    assert _get_claim(shared_dir, backend, "src/frontend")["agent_id"] == "angella-alpha"

    inspect = module.handle_request({
        "type": "call_tool", "name": "scion_inspect_state", "arguments": {"event_limit": 5},
    })
    inspect_text = _text(inspect)
    assert "Active agents:" in inspect_text
    assert "angella-alpha status=active" in inspect_text
    assert "worktree=branch=codex/scion-alpha" in inspect_text
    assert "Authoritative claims:" in inspect_text
    assert "Recent events:" in inspect_text

    os.environ["SCION_AGENT_ID"] = "angella-beta"
    query = module.handle_request({
        "type": "call_tool", "name": "scion_query_peers",
        "arguments": {"query": "Can I modify the frontend?", "candidate_files": ["src/frontend/App.tsx", "README.md"]},
    })
    text = _text(query)
    assert "Conflicts detected with active peers" in text
    assert "angella-alpha -> src/frontend/App.tsx" in text

    strict_conflict = module.handle_request({
        "type": "call_tool", "name": "scion_claim_files",
        "arguments": {"files": ["src/frontend"], "mode": "exclusive"},
    })
    assert "error" in strict_conflict

    beta_worktree = module.handle_request({
        "type": "call_tool", "name": "scion_register_worktree",
        "arguments": {"worktree_path": str(Path(tmp_root) / "wt-beta"), "branch": "codex/scion-beta", "base_branch": "main", "clean": True},
    })
    assert "Registered worktree" in _text(beta_worktree)

    overlap_warning = module.handle_request({
        "type": "call_tool", "name": "scion_claim_files",
        "arguments": {"files": ["src/frontend"], "mode": "advisory"},
    })
    assert "Warning: overlapping claims" in _text(overlap_warning)

    takeover = module.handle_request({
        "type": "call_tool", "name": "scion_claim_files",
        "arguments": {"files": ["docs/PARITY.md"], "mode": "takeover", "takeover_from": "angella-alpha", "intent": "Take over parity documentation"},
    })
    takeover_text = _text(takeover)
    assert "Claim mode: takeover" in takeover_text
    assert "Took over" in takeover_text

    heartbeat = module.handle_request({
        "type": "call_tool", "name": "scion_heartbeat",
        "arguments": {"status": "waiting", "message": "waiting for alpha to finish"},
    })
    assert "Heartbeat" in _text(heartbeat)

    beta_state = _get_agent_state(shared_dir, backend, "angella-beta")
    assert beta_state["status"] == "waiting"
    assert "docs/PARITY.md" in beta_state["claimed_files"]
    assert beta_state["worktree"]["branch"] == "codex/scion-beta"

    alpha_state_after_takeover = _get_agent_state(shared_dir, backend, "angella-alpha")
    assert "src/frontend" in alpha_state_after_takeover["claimed_files"]
    assert _get_claim(shared_dir, backend, "docs/PARITY.md")["agent_id"] == "angella-beta"

    os.environ["SCION_AGENT_ID"] = "angella-alpha"
    release = module.handle_request({
        "type": "call_tool", "name": "scion_release_claims",
        "arguments": {"files": ["src/frontend"], "note": "frontend work completed"},
    })
    assert "Released " in _text(release)

    alpha_state_after_release = _get_agent_state(shared_dir, backend, "angella-alpha")
    assert "src/frontend" not in alpha_state_after_release.get("claimed_files", [])
    assert not _get_claim(shared_dir, backend, "src/frontend")

    _inject_stale_data(shared_dir, backend)
    prune = module.handle_request({
        "type": "call_tool", "name": "scion_prune_stale",
        "arguments": {"event_retention_seconds": 60},
    })
    assert "Pruned " in _text(prune)
    _verify_stale_pruned(shared_dir, backend)

    os.environ["SCION_AGENT_ID"] = "angella-beta"
    no_conflict = module.handle_request({
        "type": "call_tool", "name": "scion_query_peers",
        "arguments": {"query": "Any active setup work?", "candidate_files": ["scripts/setup.sh"]},
    })
    assert "No direct conflicts detected" in _text(no_conflict)

    os.environ["SCION_AGENT_ID"] = "angella-nested-owner"
    nested_parent_claim = module.handle_request({
        "type": "call_tool", "name": "scion_claim_files",
        "arguments": {"files": ["src/api"], "intent": "Own broad API area", "mode": "exclusive"},
    })
    assert "Claim mode: exclusive" in _text(nested_parent_claim)

    os.environ["SCION_AGENT_ID"] = "angella-nested-child"
    nested_takeover = module.handle_request({
        "type": "call_tool", "name": "scion_claim_files",
        "arguments": {"files": ["src/api/server.py"], "mode": "takeover", "takeover_from": "angella-nested-owner", "intent": "Take over the API entrypoint only"},
    })
    assert "Claim mode: takeover" in _text(nested_takeover)

    parent_claim = _get_claim(shared_dir, backend, "src/api")
    assert "src/api/server.py" in parent_claim.get("exclusions", [])

    os.environ["SCION_AGENT_ID"] = "angella-nested-observer"
    nested_query = module.handle_request({
        "type": "call_tool", "name": "scion_query_peers",
        "arguments": {"query": "Can I edit the API entrypoint?", "candidate_files": ["src/api/server.py"]},
    })
    nested_query_text = _text(nested_query)
    assert "angella-nested-child" in nested_query_text

    os.environ["SCION_AGENT_ID"] = "angella-nested-child"
    nested_release = module.handle_request({
        "type": "call_tool", "name": "scion_release_claims",
        "arguments": {"files": ["src/api/server.py"], "note": "handoff complete"},
    })
    assert "Released" in _text(nested_release)

    restored_parent_claim = _get_claim(shared_dir, backend, "src/api")
    assert "src/api/server.py" not in restored_parent_claim.get("exclusions", [])

    os.environ["SCION_AGENT_ID"] = "angella-mixed-owner"
    mixed_exclusive = module.handle_request({
        "type": "call_tool", "name": "scion_claim_files",
        "arguments": {"files": ["docs/runbook"], "mode": "exclusive", "intent": "Own runbook area"},
    })
    mixed_advisory = module.handle_request({
        "type": "call_tool", "name": "scion_claim_files",
        "arguments": {"files": ["README.md"], "mode": "advisory", "intent": "Lightweight README note"},
    })
    
    os.environ["SCION_AGENT_ID"] = "angella-mixed-observer"
    mixed_query = module.handle_request({
        "type": "call_tool", "name": "scion_query_peers",
        "arguments": {"query": "Can I edit the README?", "candidate_files": ["README.md"]},
    })
    assert "angella-mixed-owner -> README.md" in _text(mixed_query)

    repo_root = Path(tmp_root) / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(repo_root)], check=True, capture_output=True, text=True)
    (repo_root / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_root), "add", "README.md"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo_root), "-c", "user.name=Scion Test", "-c", "user.email=scion@example.com", "commit", "-m", "init"], check=True, capture_output=True, text=True)

    os.environ["SCION_AGENT_ID"] = "angella-gamma"
    gamma_worktree_path = Path(tmp_root) / "wt-gamma"
    prepared = module.handle_request({
        "type": "call_tool", "name": "scion_prepare_worktree",
        "arguments": {"repo_root": str(repo_root), "worktree_path": str(gamma_worktree_path), "branch": "codex/scion-gamma", "base_branch": "main"},
    })
    assert "Prepared worktree for angella-gamma" in _text(prepared)
    assert gamma_worktree_path.is_dir()
    assert _has_worktree(shared_dir, backend, "codex/scion-gamma")

    os.environ["SCION_AGENT_ID"] = "angella-delta"
    conflicting_worktree = module.handle_request({
        "type": "call_tool", "name": "scion_prepare_worktree",
        "arguments": {"repo_root": str(repo_root), "worktree_path": str(Path(tmp_root) / "wt-delta"), "branch": "codex/scion-gamma", "base_branch": "main"},
    })
    assert "error" in conflicting_worktree

    os.environ["SCION_AGENT_ID"] = "angella-gamma"
    removed = module.handle_request({
        "type": "call_tool", "name": "scion_remove_worktree",
        "arguments": {"repo_root": str(repo_root), "branch": "codex/scion-gamma", "worktree_path": str(gamma_worktree_path)},
    })
    assert "Removed worktree" in _text(removed)
    assert not gamma_worktree_path.exists()
    assert not _has_worktree(shared_dir, backend, "codex/scion-gamma")

def main() -> int:
    module = _load_module()

    original_env = {
        "SCION_SHARED_DIR": os.environ.get("SCION_SHARED_DIR"),
        "SCION_AGENT_ID": os.environ.get("SCION_AGENT_ID"),
        "SCION_TTL_SECONDS": os.environ.get("SCION_TTL_SECONDS"),
        "SCION_BACKEND": os.environ.get("SCION_BACKEND"),
    }

    backends = ["file", "sqlite"]
    try:
        for backend in backends:
            print(f"--- Running tests for SCION_BACKEND={backend} ---")
            with tempfile.TemporaryDirectory() as tmp_root:
                run_test_suite_for_backend(module, backend, tmp_root)
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
