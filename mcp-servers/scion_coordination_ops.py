#!/usr/bin/env python3
"""
MCP Server for Scion-style coordination.
Provides file-backed and network-backed peer discovery, file claiming, 
and worktree management within a shared Scion Grove.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# --- Core Interfaces ---

class ScionProvider(ABC):
    """Abstract base class for Scion coordination backends."""

    @abstractmethod
    def broadcast(self, agent_id: str, message: str, files: list[str], status: str, intent: str, ttl_seconds: int | None, metadata: dict[str, Any]) -> dict[str, Any]:
        """Broadcast a message and optional claims to all peers."""
        pass

    @abstractmethod
    def claim_files(self, agent_id: str, files: list[str], mode: str, intent: str, message: str, ttl_seconds: int | None, takeover_from: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Claim a set of files or directories for the agent."""
        pass

    @abstractmethod
    def release_claims(self, agent_id: str, files: list[str], note: str, ttl_seconds: int | None) -> dict[str, Any]:
        """Release one or more file claims."""
        pass

    @abstractmethod
    def heartbeat(self, agent_id: str, status: str | None, intent: str | None, message: str | None, ttl_seconds: int | None) -> dict[str, Any]:
        """Refresh the agent's TTL and update status."""
        pass

    @abstractmethod
    def register_worktree(self, agent_id: str, repo_root: Path, worktree: dict[str, Any], ttl_seconds: int | None, status: str | None, intent: str | None, message: str | None) -> dict[str, Any]:
        """Register a worktree reservation in the shared state."""
        pass

    @abstractmethod
    def prepare_worktree(self, agent_id: str, repo_root: Path, branch: str, base_branch: str, worktree_path: Path, allow_dirty_root: bool, ttl_seconds: int | None) -> dict[str, Any]:
        """Prepare and reserve a git worktree."""
        pass

    @abstractmethod
    def remove_worktree(self, agent_id: str, repo_root: Path, branch: str, worktree_path: Path, force: bool, ttl_seconds: int | None) -> dict[str, Any]:
        """Remove a worktree reservation and directory."""
        pass

    @abstractmethod
    def inspect_state(self, include_events: bool, event_limit: int) -> dict[str, Any]:
        """Return a human-readable summary of the current state."""
        pass

    @abstractmethod
    def query_peers(self, agent_id: str, query: str, candidate_files: list[str]) -> dict[str, Any]:
        """Query peer activity and check for conflicts with candidate files."""
        pass

    @abstractmethod
    def prune_stale(self, event_retention_seconds: int) -> dict[str, Any]:
        """Clean up expired agent states and events."""
        pass


# --- Common Utilities ---

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _angella_root() -> Path:
    configured = os.environ.get("ANGELLA_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.cwd().resolve()


def _shared_dir() -> Path:
    configured = os.environ.get("SCION_SHARED_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (_angella_root() / ".scion" / "shared").resolve()


def _normalize_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.rstrip("/")


def _normalize_paths(values: list[str] | None) -> list[str]:
    if not values:
        return []
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_path(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return sorted(output)


def _agent_id() -> str:
    configured = os.environ.get("SCION_AGENT_ID", "").strip()
    if configured:
        return configured
    return f"angella-{socket.gethostname()}-{os.getpid()}"


def _default_ttl_seconds() -> int:
    raw = os.environ.get("SCION_TTL_SECONDS", "").strip()
    if raw.isdigit():
        return max(30, int(raw))
    return 900


def _run_git(repo_root: Path, args: list[str], *, cwd: Path | None = None) -> str:
    command = ["git", "-C", str(repo_root), *args]
    result = subprocess.run(
        command,
        cwd=str(cwd or repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(stderr)
    return result.stdout.strip()


def _repo_root(path_value: str | None) -> Path:
    candidate = Path(path_value).expanduser().resolve() if path_value else _angella_root()
    top = _run_git(candidate, ["rev-parse", "--show-toplevel"])
    return Path(top).resolve()


def _format_worktree(worktree: dict[str, Any] | None) -> str:
    if not worktree:
        return ""
    parts = []
    if worktree.get("branch"): parts.append(f"branch={worktree['branch']}")
    if worktree.get("path"): parts.append(f"path={worktree['path']}")
    return " ".join(parts)


def _paths_overlap(p1: str, p2: str) -> bool:
    return p1 == p2 or p1.startswith(f"{p2}/") or p2.startswith(f"{p1}/")


def _path_within(candidate: str, container: str) -> bool:
    return candidate == container or candidate.startswith(f"{container}/")


# --- File-Backed Provider Implementation ---

class FileScionProvider(ScionProvider):
    def __init__(self, shared_dir: Path):
        self.shared_dir = shared_dir
        self.agents_dir = shared_dir / "agents"
        self.events_dir = shared_dir / "events"
        self.claims_dir = shared_dir / "claims"
        self.worktrees_dir = shared_dir / "worktrees"
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        for d in [self.agents_dir, self.events_dir, self.claims_dir, self.worktrees_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _agent_state_path(self, agent_id: str) -> Path:
        return self.agents_dir / f"{agent_id}.json"

    def _claim_record_path(self, claimed_path: str) -> Path:
        return self.claims_dir / f"{_normalize_path(claimed_path)}.json"

    def _worktree_record_path(self, branch: str) -> Path:
        return self.worktrees_dir / f"{_normalize_path(branch)}.json"

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists(): return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except:
            return {}

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            temp_path = Path(f.name)
        temp_path.replace(path)

    def _load_agent_state(self, agent_id: str) -> dict[str, Any]:
        state = self._read_json(self._agent_state_path(agent_id))
        if not state:
            state = {"agent_id": agent_id, "status": "idle", "claimed_files": [], "worktree": {}}
        return state

    def _save_agent_state(self, agent_id: str, state: dict[str, Any], ttl_seconds: int | None = None) -> None:
        now = time.time()
        ttl = ttl_seconds or _default_ttl_seconds()
        state.update({
            "updated_at": _iso_now(),
            "updated_at_epoch": now,
            "expires_at_epoch": now + ttl
        })
        self._write_json(self._agent_state_path(agent_id), state)

    def broadcast(self, agent_id: str, message: str, files: list[str], status: str, intent: str, ttl_seconds: int | None, metadata: dict[str, Any]) -> dict[str, Any]:
        state = self._load_agent_state(agent_id)
        state.update({"status": status, "intent": intent, "message": message, "metadata": metadata})
        if files: state["claimed_files"] = _normalize_paths(files)
        self._save_agent_state(agent_id, state, ttl_seconds)
        
        event = {"agent_id": agent_id, "kind": "broadcast", "timestamp": _iso_now(), "payload": {"message": message}}
        self._write_json(self.events_dir / f"{int(time.time()*1000)}-{agent_id}-broadcast.json", event)
        return {"content": [{"type": "text", "text": f"Broadcast recorded for {agent_id}."}]}

    def claim_files(self, agent_id: str, files: list[str], mode: str, intent: str, message: str, ttl_seconds: int | None, takeover_from: str, metadata: dict[str, Any]) -> dict[str, Any]:
        normalized = _normalize_paths(files)
        overlap_found = False
        took_over_from = set()
        nested_takeover_count = 0
        
        # Load all existing claims to find parent/nested conflicts
        existing_claim_records = []
        for p in self.claims_dir.rglob("*.json"):
            rec = self._read_json(p)
            if rec and rec.get("expires_at_epoch", 0) > time.time():
                rec["_path"] = p
                existing_claim_records.append(rec)

        metadata_for_new_claims = {}

        for f in normalized:
            matching_conflicts = [r for r in existing_claim_records if r.get("agent_id") != agent_id and _paths_overlap(f, r.get("claimed_path", ""))]
            
            for conflict in matching_conflicts:
                owner = conflict.get("agent_id")
                claimed = conflict.get("claimed_path", "")
                
                if mode == "exclusive":
                    if f not in conflict.get("exclusions", []):
                        raise RuntimeError(f"Conflicting Scion claims detected: {owner} -> {f}")
                elif mode == "takeover" and owner == takeover_from:
                    if f == claimed:
                        took_over_from.add(owner)
                        owner_state = self._load_agent_state(owner)
                        owner_claims = owner_state.get("claimed_files", [])
                        if f in owner_claims:
                            owner_claims.remove(f)
                            self._save_agent_state(owner, owner_state)
                    elif _path_within(f, claimed):
                        took_over_from.add(owner)
                        nested_takeover_count += 1
                        exclusions = conflict.get("exclusions", [])
                        if f not in exclusions:
                            exclusions.append(f)
                            conflict["exclusions"] = exclusions
                            self._write_json(conflict["_path"], {k: v for k, v in conflict.items() if not k.startswith("_")})
                        
                        # Remember parent info for new claim
                        metadata_for_new_claims[f] = {
                            "decomposed_from_agent": owner,
                            "decomposed_from_claimed_path": claimed
                        }
                else:
                    if f not in conflict.get("exclusions", []):
                        overlap_found = True

        state = self._load_agent_state(agent_id)
        current_claims = set(state.get("claimed_files", []))
        current_claims.update(normalized)
        state["claimed_files"] = sorted(list(current_claims))
        self._save_agent_state(agent_id, state, ttl_seconds)

        now = time.time()
        ttl = ttl_seconds or _default_ttl_seconds()
        if mode in {"exclusive", "takeover"}:
            for f in normalized:
                payload = {
                    "agent_id": agent_id, "claimed_path": f, "mode": mode, "expires_at_epoch": now + ttl, "exclusions": []
                }
                if f in metadata_for_new_claims:
                    payload.update(metadata_for_new_claims[f])
                self._write_json(self._claim_record_path(f), payload)
        
        text = f"Claimed {len(normalized)} file(s) for {agent_id}: {', '.join(normalized)}"
        if mode != "advisory":
            text += f"\nClaim mode: {mode}"
        if overlap_found:
            text += f"\nWarning: overlapping claims detected with active peers."
        if took_over_from:
            if nested_takeover_count > 0:
                text += f"\nTook over claims from: {', '.join(sorted(took_over_from))}"
                text += "\nNested takeover decomposed broader parent claims via exclusions."
            else:
                text += f"\nTook over exact claims from: {', '.join(sorted(took_over_from))}"
        return {"content": [{"type": "text", "text": text}]}

    def release_claims(self, agent_id: str, files: list[str], note: str, ttl_seconds: int | None) -> dict[str, Any]:
        state = self._load_agent_state(agent_id)
        current = state.get("claimed_files", [])
        to_release = _normalize_paths(files) if files else current
        remaining = [f for f in current if f not in to_release]
        
        state["claimed_files"] = remaining
        if note: state["message"] = note
        self._save_agent_state(agent_id, state, ttl_seconds)
        
        for f in to_release:
            path = self._claim_record_path(f)
            if path.exists():
                existing = self._read_json(path)
                if existing.get("agent_id") == agent_id:
                    # Restore parent coverage if nested takeover
                    parent_agent = existing.get("decomposed_from_agent")
                    parent_path = existing.get("decomposed_from_claimed_path")
                    if parent_agent and parent_path:
                        parent_record_path = self._claim_record_path(parent_path)
                        if parent_record_path.exists():
                            parent_record = self._read_json(parent_record_path)
                            if parent_record.get("agent_id") == parent_agent:
                                exclusions = parent_record.get("exclusions", [])
                                if f in exclusions:
                                    exclusions.remove(f)
                                    parent_record["exclusions"] = exclusions
                                    self._write_json(parent_record_path, parent_record)
                    path.unlink()
        return {"content": [{"type": "text", "text": f"Released {len(to_release)} claim(s) for {agent_id}."}]}

    def heartbeat(self, agent_id: str, status: str | None, intent: str | None, message: str | None, ttl_seconds: int | None) -> dict[str, Any]:
        state = self._load_agent_state(agent_id)
        if status: state["status"] = status
        if intent: state["intent"] = intent
        if message: state["message"] = message
        self._save_agent_state(agent_id, state, ttl_seconds)
        return {"content": [{"type": "text", "text": f"Heartbeat recorded for {agent_id}."}]}

    def register_worktree(self, agent_id: str, repo_root: Path, worktree: dict[str, Any], ttl_seconds: int | None, status: str | None, intent: str | None, message: str | None) -> dict[str, Any]:
        branch = worktree.get("branch")
        if not branch: raise ValueError("Worktree must have a branch.")
        
        # Check for worktree conflicts
        path_raw = worktree.get("path")
        if path_raw:
            worktree_path = Path(path_raw).expanduser().resolve()
            for p in self.worktrees_dir.rglob("*.json"):
                rec = self._read_json(p)
                if rec and rec.get("expires_at_epoch", 0) > time.time():
                    if rec.get("agent_id") != agent_id:
                        if rec.get("branch") == branch or Path(rec.get("path", "")).expanduser().resolve() == worktree_path:
                            raise RuntimeError(f"Conflicting Scion worktree reservations detected: {rec.get('agent_id')} -> branch={rec.get('branch')} path={rec.get('path')}")

        now = time.time()
        ttl = ttl_seconds or _default_ttl_seconds()
        self._write_json(self._worktree_record_path(branch), {**worktree, "agent_id": agent_id, "expires_at_epoch": now + ttl})
        
        state = self._load_agent_state(agent_id)
        state["worktree"] = worktree
        if status: state["status"] = status
        self._save_agent_state(agent_id, state, ttl_seconds)
        return {"content": [{"type": "text", "text": f"Registered worktree for {agent_id}: branch={branch}"}]}

    def prepare_worktree(self, agent_id: str, repo_root: Path, branch: str, base_branch: str, worktree_path: Path, allow_dirty_root: bool, ttl_seconds: int | None) -> dict[str, Any]:
        if not allow_dirty_root:
            status = _run_git(repo_root, ["status", "--porcelain"])
            if status: raise RuntimeError("Repo root is dirty.")
        
        # Check for conflicts BEFORE git operations
        for p in self.worktrees_dir.rglob("*.json"):
            rec = self._read_json(p)
            if rec and rec.get("expires_at_epoch", 0) > time.time():
                if rec.get("agent_id") != agent_id:
                    if rec.get("branch") == branch or Path(rec.get("path", "")).expanduser().resolve() == worktree_path.resolve():
                        raise RuntimeError(f"Conflicting Scion worktree reservations detected: {rec.get('agent_id')} -> branch={rec.get('branch')} path={rec.get('path')}")

        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        _run_git(repo_root, ["worktree", "add", "-b", branch, str(worktree_path), base_branch])
        
        worktree = {"path": str(worktree_path), "branch": branch, "base_branch": base_branch}
        # Call register_worktree but return a custom message
        self.register_worktree(agent_id, repo_root, worktree, ttl_seconds, "planning", None, None)
        return {"content": [{"type": "text", "text": f"Prepared worktree for {agent_id}: branch={branch} base={base_branch} path={worktree_path}"}]}

    def remove_worktree(self, agent_id: str, repo_root: Path, branch: str, worktree_path: Path, force: bool, ttl_seconds: int | None) -> dict[str, Any]:
        args = ["worktree", "remove"]
        if force: args.append("--force")
        args.append(str(worktree_path))
        _run_git(repo_root, args)
        
        path = self._worktree_record_path(branch)
        if path.exists(): path.unlink()
        
        state = self._load_agent_state(agent_id)
        state["worktree"] = {}
        self._save_agent_state(agent_id, state, ttl_seconds)
        return {"content": [{"type": "text", "text": f"Removed worktree for {agent_id}: branch={branch} path={worktree_path}"}]}

    def inspect_state(self, include_events: bool, event_limit: int) -> dict[str, Any]:
        lines = [f"Shared dir: {self.shared_dir}"]
        agents = sorted(self.agents_dir.glob("*.json"))
        if not agents:
            lines.append("Active agents: none")
        else:
            lines.append("Active agents:")
            for a in agents:
                data = self._read_json(a)
                if data.get("expires_at_epoch", 0) > time.time():
                    line = f"- {data.get('agent_id')} status={data.get('status')} claims={','.join(data.get('claimed_files', []))}"
                    wt = _format_worktree(data.get("worktree"))
                    if wt: line += f" worktree={wt}"
                    lines.append(line)
        
        claims = sorted(self.claims_dir.glob("*.json"))
        if not claims:
            lines.append("Authoritative claims: none")
        else:
            lines.append("Authoritative claims:")
            for c in claims:
                data = self._read_json(c)
                if data.get("expires_at_epoch", 0) > time.time():
                    line = f"- {data.get('claimed_path')} owner={data.get('agent_id')} mode={data.get('mode')}"
                    excl = data.get("exclusions", [])
                    if excl: line += f" (excluding: {','.join(excl)})"
                    lines.append(line)

        wts = sorted(self.worktrees_dir.glob("*.json"))
        if not wts:
            lines.append("Reserved worktrees: none")
        else:
            lines.append("Reserved worktrees:")
            for w in wts:
                data = self._read_json(w)
                if data.get("expires_at_epoch", 0) > time.time():
                    lines.append(f"- owner={data.get('agent_id')} branch={data.get('branch')} path={data.get('path')}")

        if include_events:
            events = sorted(self.events_dir.glob("*.json"), reverse=True)[:event_limit]
            if not events:
                lines.append("Recent events: none")
            else:
                lines.append("Recent events:")
                for e in events:
                    data = self._read_json(e)
                    lines.append(f"- {e.name} kind={data.get('kind')} agent={data.get('agent_id')}")

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    def query_peers(self, agent_id: str, query: str, candidate_files: list[str]) -> dict[str, Any]:
        normalized = _normalize_paths(candidate_files)
        
        # Load all existing claims to find conflicts correctly (respecting exclusions)
        claim_records = []
        for p in self.claims_dir.rglob("*.json"):
            rec = self._read_json(p)
            if rec and rec.get("expires_at_epoch", 0) > time.time() and rec.get("agent_id") != agent_id:
                claim_records.append(rec)

        conflicts = []
        authoritative_paths = set()
        for rec in claim_records:
            owner = rec.get('agent_id')
            claimed = rec.get('claimed_path', "")
            authoritative_paths.add((owner, claimed))
            for c in normalized:
                if _paths_overlap(c, claimed):
                    if c not in rec.get("exclusions", []):
                        conflicts.append(f"{owner} -> {c} (peer claim: {claimed})")

        peers = []
        for f in self.agents_dir.glob("*.json"):
            data = self._read_json(f)
            pid = data.get("agent_id")
            if pid == agent_id: continue
            if data.get("expires_at_epoch", 0) <= time.time(): continue
            
            peer_claims = data.get("claimed_files", [])
            # Also check for advisory conflicts (claims not in claim_records)
            for pc in peer_claims:
                if (pid, pc) not in authoritative_paths:
                    for c in normalized:
                        if _paths_overlap(c, pc):
                            conflicts.append(f"{pid} -> {c} (peer claim: {pc})")
            
            peers.append(f"{pid} status={data.get('status')} claims={','.join(peer_claims)}")

        text = ""
        if conflicts:
            text += "Conflicts detected with active peers:\n" + "\n".join(sorted(list(set(conflicts)))) + "\n\n"
        else:
            text += "No direct conflicts detected.\n\n"
        
        text += "Active peers:\n" + ("\n".join(peers) if peers else "none")
        return {"content": [{"type": "text", "text": text}]}

    def prune_stale(self, event_retention_seconds: int) -> dict[str, Any]:
        now = time.time()
        agent_count = 0
        for f in self.agents_dir.glob("*.json"):
            if self._read_json(f).get("expires_at_epoch", 0) < now:
                f.unlink()
                agent_count += 1
        
        claim_count = 0
        for f in self.claims_dir.rglob("*.json"):
            if self._read_json(f).get("expires_at_epoch", 0) < now:
                f.unlink()
                claim_count += 1
        
        worktree_count = 0
        for f in self.worktrees_dir.rglob("*.json"):
            if self._read_json(f).get("expires_at_epoch", 0) < now:
                f.unlink()
                worktree_count += 1

        cutoff = now - max(60, event_retention_seconds)
        event_count = 0
        for f in self.events_dir.glob("*.json"):
            try:
                ts = int(f.name.split("-")[0])
                if ts / 1000.0 < cutoff:
                    f.unlink()
                    event_count += 1
            except:
                pass

        return {"content": [{"type": "text", "text": f"Pruned {agent_count} stale agent state file(s) {claim_count} stale claim file(s) {worktree_count} stale worktree record(s) and {event_count} expired event(s)."}]}


# --- Redis-Backed Provider Implementation ---

class RedisScionProvider(ScionProvider):
    def __init__(self, host: str, port: int):
        import redis
        self.r = redis.Redis(host=host, port=port, decode_responses=True)
        self.prefix = "scion"

    def _agent_key(self, agent_id: str) -> str: return f"{self.prefix}:agent:{agent_id}"
    def _claim_key(self, path: str) -> str: return f"{self.prefix}:claim:{_normalize_path(path)}"
    def _worktree_key(self, branch: str) -> str: return f"{self.prefix}:worktree:{_normalize_path(branch)}"

    def broadcast(self, agent_id: str, message: str, files: list[str], status: str, intent: str, ttl_seconds: int | None, metadata: dict[str, Any]) -> dict[str, Any]:
        ttl = ttl_seconds or _default_ttl_seconds()
        key = self._agent_key(agent_id)
        state = {
            "agent_id": agent_id, "status": status, "message": message, "intent": intent,
            "claimed_files": json.dumps(_normalize_paths(files)), "metadata": json.dumps(metadata),
            "updated_at": _iso_now()
        }
        self.r.hset(key, mapping=state)
        self.r.expire(key, ttl)
        self.r.xadd(f"{self.prefix}:events", {"agent_id": agent_id, "kind": "broadcast", "message": message, "timestamp": _iso_now()})
        return {"content": [{"type": "text", "text": f"Broadcast recorded (Redis) for {agent_id}."}]}

    def claim_files(self, agent_id: str, files: list[str], mode: str, intent: str, message: str, ttl_seconds: int | None, takeover_from: str, metadata: dict[str, Any]) -> dict[str, Any]:
        ttl = ttl_seconds or _default_ttl_seconds()
        normalized = _normalize_paths(files)
        overlap_found = False
        took_over_from = set()
        
        # Load all existing claims from Redis to find conflicts
        claim_keys = self.r.keys(f"{self.prefix}:claim:*")
        existing_claims = []
        for ck in claim_keys:
            raw = self.r.get(ck)
            if raw:
                try:
                    cdata = json.loads(raw)
                    cdata["_key"] = ck
                    existing_claims.append(cdata)
                except: continue

        metadata_for_new_claims = {}

        for f in normalized:
            matching_conflicts = [r for r in existing_claims if r.get("agent_id") != agent_id and _paths_overlap(f, r.get("claimed_path", ""))]
            
            for conflict in matching_conflicts:
                owner = conflict.get("agent_id")
                claimed = conflict.get("claimed_path", "")
                
                if mode == "exclusive":
                    if f not in conflict.get("exclusions", []):
                        raise RuntimeError(f"Conflicting Scion claims detected (Redis): {owner} -> {f}")
                elif mode == "takeover" and owner == takeover_from:
                    if f == claimed:
                        took_over_from.add(owner)
                        # Remove exact claim from owner's state (best effort)
                        okey = self._agent_key(owner)
                        ostate_raw = self.r.hget(okey, "claimed_files")
                        if ostate_raw:
                            oclaims = json.loads(ostate_raw)
                            if f in oclaims:
                                oclaims.remove(f)
                                self.r.hset(okey, "claimed_files", json.dumps(oclaims))
                    elif _path_within(f, claimed):
                        took_over_from.add(owner)
                        exclusions = conflict.get("exclusions", [])
                        if f not in exclusions:
                            exclusions.append(f)
                            conflict["exclusions"] = exclusions
                            self.r.set(conflict["_key"], json.dumps({k:v for k,v in conflict.items() if not k.startswith("_")}), keepttl=True)
                        
                        metadata_for_new_claims[f] = {
                            "decomposed_from_agent": owner,
                            "decomposed_from_claimed_path": claimed
                        }
                else:
                    if f not in conflict.get("exclusions", []):
                        overlap_found = True

        agent_key = self._agent_key(agent_id)
        current_raw = self.r.hget(agent_key, "claimed_files")
        current = json.loads(current_raw) if current_raw else []
        new_claims_list = sorted(list(set(current + normalized)))
        self.r.hset(agent_key, "claimed_files", json.dumps(new_claims_list))
        self.r.expire(agent_key, ttl)

        if mode in {"exclusive", "takeover"}:
            for f in normalized:
                payload = {
                    "agent_id": agent_id, "claimed_path": f, "mode": mode, "exclusions": []
                }
                if f in metadata_for_new_claims:
                    payload.update(metadata_for_new_claims[f])
                self.r.set(self._claim_key(f), json.dumps(payload), ex=ttl)
        
        text = f"Claimed (Redis) {len(normalized)} file(s) for {agent_id}: {', '.join(normalized)}"
        if mode != "advisory": text += f"\nClaim mode: {mode}"
        if overlap_found: text += f"\nWarning: overlapping claims detected with active peers."
        if took_over_from: text += f"\nTook over claims from: {', '.join(sorted(took_over_from))}"
        return {"content": [{"type": "text", "text": text}]}

    def release_claims(self, agent_id: str, files: list[str], note: str, ttl_seconds: int | None) -> dict[str, Any]:
        agent_key = self._agent_key(agent_id)
        current_raw = self.r.hget(agent_key, "claimed_files")
        current = json.loads(current_raw) if current_raw else []
        to_release = _normalize_paths(files) if files else current
        remaining = [f for f in current if f not in to_release]
        
        for f in to_release:
            ckey = self._claim_key(f)
            raw = self.r.get(ckey)
            if raw:
                existing = json.loads(raw)
                if existing.get("agent_id") == agent_id:
                    parent_agent = existing.get("decomposed_from_agent")
                    parent_path = existing.get("decomposed_from_claimed_path")
                    if parent_agent and parent_path:
                        pkey = self._claim_key(parent_path)
                        praw = self.r.get(pkey)
                        if praw:
                            prec = json.loads(praw)
                            if prec.get("agent_id") == parent_agent:
                                excl = prec.get("exclusions", [])
                                if f in excl:
                                    excl.remove(f)
                                    prec["exclusions"] = excl
                                    self.r.set(pkey, json.dumps(prec), keepttl=True)
                    self.r.delete(ckey)
        
        self.r.hset(agent_key, "claimed_files", json.dumps(remaining))
        if note: self.r.hset(agent_key, "message", note)
        return {"content": [{"type": "text", "text": f"Released (Redis) {len(to_release)} claim(s) for {agent_id}."}]}

    def heartbeat(self, agent_id: str, status: str | None, intent: str | None, message: str | None, ttl_seconds: int | None) -> dict[str, Any]:
        ttl = ttl_seconds or _default_ttl_seconds()
        key = self._agent_key(agent_id)
        if status: self.r.hset(key, "status", status)
        if intent: self.r.hset(key, "intent", intent)
        if message: self.r.hset(key, "message", message)
        self.r.hset(key, "updated_at", _iso_now())
        self.r.expire(key, ttl)
        return {"content": [{"type": "text", "text": f"Heartbeat (Redis) recorded for {agent_id}."}]}

    def register_worktree(self, agent_id: str, repo_root: Path, worktree: dict[str, Any], ttl_seconds: int | None, status: str | None, intent: str | None, message: str | None) -> dict[str, Any]:
        branch = worktree.get("branch")
        if not branch: raise ValueError("Worktree must have a branch.")
        ttl = ttl_seconds or _default_ttl_seconds()
        self.r.set(self._worktree_key(branch), json.dumps({**worktree, "agent_id": agent_id}), ex=ttl)
        
        key = self._agent_key(agent_id)
        self.r.hset(key, "worktree", json.dumps(worktree))
        if status: self.r.hset(key, "status", status)
        self.r.expire(key, ttl)
        return {"content": [{"type": "text", "text": f"Registered worktree (Redis) for {agent_id}: branch={branch}"}]}

    def prepare_worktree(self, agent_id: str, repo_root: Path, branch: str, base_branch: str, worktree_path: Path, allow_dirty_root: bool, ttl_seconds: int | None) -> dict[str, Any]:
        if not allow_dirty_root:
            status = _run_git(repo_root, ["status", "--porcelain"])
            if status: raise RuntimeError("Repo root is dirty.")
        _run_git(repo_root, ["worktree", "add", "-b", branch, str(worktree_path), base_branch])
        return self.register_worktree(agent_id, repo_root, {"path": str(worktree_path), "branch": branch, "base_branch": base_branch}, ttl_seconds, "planning", None, None)

    def remove_worktree(self, agent_id: str, repo_root: Path, branch: str, worktree_path: Path, force: bool, ttl_seconds: int | None) -> dict[str, Any]:
        args = ["worktree", "remove"]
        if force: args.append("--force")
        args.append(str(worktree_path))
        _run_git(repo_root, args)
        self.r.delete(self._worktree_key(branch))
        
        akey = self._agent_key(agent_id)
        self.r.hdel(akey, "worktree")
        return {"content": [{"type": "text", "text": f"Removed worktree (Redis) for {agent_id}: branch={branch}"}]}

    def inspect_state(self, include_events: bool, event_limit: int) -> dict[str, Any]:
        lines = [f"Backend: Redis ({self.r.connection_pool.connection_kwargs.get('host')})"]
        
        akeys = self.r.keys(f"{self.prefix}:agent:*")
        if not akeys:
            lines.append("Active agents: none")
        else:
            lines.append("Active agents:")
            for k in sorted(akeys):
                data = self.r.hgetall(k)
                cid = data.get("agent_id")
                claims = json.loads(data.get("claimed_files", "[]"))
                line = f"- {cid} status={data.get('status')} claims={','.join(claims)}"
                wt = json.loads(data.get("worktree", "{}"))
                if wt: line += f" worktree={_format_worktree(wt)}"
                lines.append(line)
        
        ckeys = self.r.keys(f"{self.prefix}:claim:*")
        if not ckeys:
            lines.append("Authoritative claims: none")
        else:
            lines.append("Authoritative claims:")
            for k in sorted(ckeys):
                raw = self.r.get(k)
                if raw:
                    data = json.loads(raw)
                    line = f"- {data.get('claimed_path')} owner={data.get('agent_id')} mode={data.get('mode')}"
                    excl = data.get("exclusions", [])
                    if excl: line += f" (excluding: {','.join(excl)})"
                    lines.append(line)

        wkeys = self.r.keys(f"{self.prefix}:worktree:*")
        if not wkeys:
            lines.append("Reserved worktrees: none")
        else:
            lines.append("Reserved worktrees:")
            for k in sorted(wkeys):
                raw = self.r.get(k)
                if raw:
                    data = json.loads(raw)
                    lines.append(f"- owner={data.get('agent_id')} branch={data.get('branch')} path={data.get('path')}")

        if include_events:
            # Redis Stream for events
            try:
                events = self.r.xrevrange(f"{self.prefix}:events", count=event_limit)
                if not events:
                    lines.append("Recent events: none")
                else:
                    lines.append("Recent events (Stream):")
                    for eid, edata in events:
                        lines.append(f"- {eid} kind={edata.get('kind')} agent={edata.get('agent_id')} msg={edata.get('message')}")
            except:
                lines.append("Recent events: (stream unavailable)")

        return {"content": [{"type": "text", "text": "\n".join(lines)}]}

    def query_peers(self, agent_id: str, query: str, candidate_files: list[str]) -> dict[str, Any]:
        normalized = _normalize_paths(candidate_files)
        
        ckeys = self.r.keys(f"{self.prefix}:claim:*")
        conflicts = []
        authoritative_paths = set()
        for k in ckeys:
            raw = self.r.get(k)
            if not raw: continue
            rec = json.loads(raw)
            owner = rec.get("agent_id")
            if owner == agent_id: continue
            
            claimed = rec.get("claimed_path", "")
            authoritative_paths.add((owner, claimed))
            for c in normalized:
                if _paths_overlap(c, claimed):
                    if c not in rec.get("exclusions", []):
                        conflicts.append(f"{owner} -> {c} (peer claim: {claimed})")

        akeys = self.r.keys(f"{self.prefix}:agent:*")
        peers = []
        for k in akeys:
            data = self.r.hgetall(k)
            pid = data.get("agent_id")
            if pid == agent_id: continue
            
            peer_claims = json.loads(data.get("claimed_files", "[]"))
            for pc in peer_claims:
                if (pid, pc) not in authoritative_paths:
                    for c in normalized:
                        if _paths_overlap(c, pc):
                            conflicts.append(f"{pid} -> {c} (peer claim: {pc})")
            peers.append(f"{pid} status={data.get('status')} claims={','.join(peer_claims)}")

        text = ""
        if conflicts:
            text += "Conflicts detected (Redis) with active peers:\n" + "\n".join(sorted(list(set(conflicts)))) + "\n\n"
        else:
            text += "No direct conflicts detected (Redis).\n\n"
        
        text += "Active peers (Redis):\n" + ("\n".join(peers) if peers else "none")
        return {"content": [{"type": "text", "text": text}]}

    def prune_stale(self, event_retention_seconds: int) -> dict[str, Any]:
        # Redis auto-prunes via TTL for most things.
        # Events in Stream might need manual pruning if we want to limit size.
        try:
            self.r.xtrim(f"{self.prefix}:events", maxlen=1000, approximate=True)
        except: pass
        return {"content": [{"type": "text", "text": "Redis state auto-pruned via TTL; Stream trimmed to last 1000 items."}]}


# --- SQLite-Backed Provider Implementation ---

class SqliteScionProvider(ScionProvider):
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        cursor = conn.cursor()
        
        # Agents table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            status TEXT,
            intent TEXT,
            message TEXT,
            metadata TEXT,
            claimed_files TEXT,
            worktree TEXT,
            updated_at TEXT,
            expires_at_epoch REAL
        )
        """)
        
        # Claims table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            claimed_path TEXT PRIMARY KEY,
            agent_id TEXT,
            mode TEXT,
            exclusions TEXT,
            expires_at_epoch REAL,
            metadata TEXT
        )
        """)
        
        # Worktrees table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS worktrees (
            branch TEXT PRIMARY KEY,
            path TEXT,
            agent_id TEXT,
            expires_at_epoch REAL,
            metadata TEXT
        )
        """)
        
        # Events table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT,
            kind TEXT,
            message TEXT,
            timestamp TEXT,
            payload TEXT
        )
        """)
        
        # Indexes for performance (Boris Point 1: Pre-computing)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_claims_agent ON claims(agent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_agents_expiry ON agents(expires_at_epoch)")
        
        conn.commit()
        conn.close()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def broadcast(self, agent_id: str, message: str, files: list[str], status: str, intent: str, ttl_seconds: int | None, metadata: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        ttl = ttl_seconds or _default_ttl_seconds()
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO agents (agent_id, status, intent, message, metadata, updated_at, expires_at_epoch)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    status=excluded.status, intent=excluded.intent, message=excluded.message, 
                    metadata=excluded.metadata, updated_at=excluded.updated_at, expires_at_epoch=excluded.expires_at_epoch
            """, (agent_id, status, intent, message, json.dumps(metadata), _iso_now(), now + ttl))
            if files:
                conn.execute("UPDATE agents SET claimed_files = ? WHERE agent_id = ?", (json.dumps(_normalize_paths(files)), agent_id))
            
            conn.execute("""
                INSERT INTO events (agent_id, kind, message, timestamp, payload)
                VALUES (?, ?, ?, ?, ?)
            """, (agent_id, "broadcast", message, _iso_now(), json.dumps({"files": files})))
            conn.commit()
            return {"content": [{"type": "text", "text": f"Broadcast recorded (SQLite) for {agent_id}."}]}
        finally:
            conn.close()

    def claim_files(self, agent_id: str, files: list[str], mode: str, intent: str, message: str, ttl_seconds: int | None, takeover_from: str, metadata: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        ttl = ttl_seconds or _default_ttl_seconds()
        normalized = _normalize_paths(files)
        overlap_found = False
        took_over_from = set()
        
        conn = self._get_conn()
        try:
            # Load all existing active claims (Boris Point 1: Use index-backed query)
            cursor = conn.execute("SELECT * FROM claims WHERE expires_at_epoch > ?", (now,))
            existing_claims = [dict(r) for r in cursor.fetchall() if r["agent_id"] != agent_id]
            
            metadata_for_new_claims = {}
            for f in normalized:
                matching_conflicts = [r for r in existing_claims if _paths_overlap(f, r["claimed_path"])]
                for conflict in matching_conflicts:
                    owner = conflict["agent_id"]
                    claimed = conflict["claimed_path"]
                    exclusions = json.loads(conflict.get("exclusions", "[]"))
                    
                    if mode == "exclusive":
                        if f not in exclusions:
                            raise RuntimeError(f"Conflicting Scion claims detected (SQLite): {owner} -> {f}")
                    elif mode == "takeover" and owner == takeover_from:
                        took_over_from.add(owner)
                        if f == claimed:
                            conn.execute("DELETE FROM claims WHERE claimed_path = ?", (f,))
                        elif _path_within(f, claimed):
                            if f not in exclusions:
                                exclusions.append(f)
                                conn.execute("UPDATE claims SET exclusions = ? WHERE claimed_path = ?", (json.dumps(exclusions), claimed))
                            metadata_for_new_claims[f] = {"decomposed_from_agent": owner, "decomposed_from_claimed_path": claimed}
                    else:
                        if f not in exclusions: overlap_found = True

            # Update agent state
            cursor = conn.execute("SELECT claimed_files FROM agents WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            current_claims = set(json.loads(row["claimed_files"] if row and row["claimed_files"] else "[]"))
            current_claims.update(normalized)
            
            conn.execute("""
                INSERT INTO agents (agent_id, claimed_files, updated_at, expires_at_epoch)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    claimed_files=excluded.claimed_files, updated_at=excluded.updated_at, expires_at_epoch=excluded.expires_at_epoch
            """, (agent_id, json.dumps(sorted(list(current_claims))), _iso_now(), now + ttl))

            if mode in {"exclusive", "takeover"}:
                for f in normalized:
                    payload = {"agent_id": agent_id, "claimed_path": f, "mode": mode, "expires_at_epoch": now + ttl, "exclusions": "[]"}
                    if f in metadata_for_new_claims: payload.update(metadata_for_new_claims[f])
                    conn.execute("""
                        INSERT OR REPLACE INTO claims (claimed_path, agent_id, mode, exclusions, expires_at_epoch, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (f, agent_id, mode, payload.get("exclusions", "[]"), now + ttl, json.dumps(payload)))
            
            conn.commit()
            text = f"Claimed {len(normalized)} file(s) for {agent_id}: {', '.join(normalized)}"
            if mode != "advisory":
                text += f"\nClaim mode: {mode}"
            if overlap_found:
                text += f"\nWarning: overlapping claims detected with active peers."
            if took_over_from:
                text += f"\nTook over exact claims from: {', '.join(sorted(took_over_from))}"
            return {"content": [{"type": "text", "text": text}]}
        finally:
            conn.close()

    def release_claims(self, agent_id: str, files: list[str], note: str, ttl_seconds: int | None) -> dict[str, Any]:
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT claimed_files FROM agents WHERE agent_id = ?", (agent_id,))
            row = cursor.fetchone()
            if not row or not row["claimed_files"]: return {"content": [{"type": "text", "text": "No claims found."}]}
            
            current = json.loads(row["claimed_files"])
            to_release = _normalize_paths(files) if files else current
            remaining = [f for f in current if f not in to_release]
            
            for f in to_release:
                cursor = conn.execute("SELECT * FROM claims WHERE claimed_path = ? AND agent_id = ?", (f, agent_id))
                claim = cursor.fetchone()
                if claim:
                    meta = json.loads(claim["metadata"] or "{}")
                    parent_agent = meta.get("decomposed_from_agent")
                    parent_path = meta.get("decomposed_from_claimed_path")
                    if parent_agent and parent_path:
                        # Restore parent coverage
                        cursor = conn.execute("SELECT exclusions FROM claims WHERE claimed_path = ? AND agent_id = ?", (parent_path, parent_agent))
                        p_row = cursor.fetchone()
                        if p_row:
                            excl = json.loads(p_row["exclusions"])
                            if f in excl:
                                excl.remove(f)
                                conn.execute("UPDATE claims SET exclusions = ? WHERE claimed_path = ?", (json.dumps(excl), parent_path))
                    conn.execute("DELETE FROM claims WHERE claimed_path = ?", (f,))
            
            conn.execute("UPDATE agents SET claimed_files = ?, message = ?, updated_at = ? WHERE agent_id = ?", 
                         (json.dumps(remaining), note, _iso_now(), agent_id))
            conn.commit()
            return {"content": [{"type": "text", "text": f"Released (SQLite) {len(to_release)} claim(s)."}]}
        finally:
            conn.close()

    def heartbeat(self, agent_id: str, status: str | None, intent: str | None, message: str | None, ttl_seconds: int | None) -> dict[str, Any]:
        now = time.time()
        ttl = ttl_seconds or _default_ttl_seconds()
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO agents (agent_id, status, intent, message, updated_at, expires_at_epoch)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    status=COALESCE(excluded.status, agents.status),
                    intent=COALESCE(excluded.intent, agents.intent),
                    message=COALESCE(excluded.message, agents.message),
                    updated_at=excluded.updated_at,
                    expires_at_epoch=excluded.expires_at_epoch
            """, (agent_id, status, intent, message, _iso_now(), now + ttl))
            conn.commit()
            return {"content": [{"type": "text", "text": f"Heartbeat (SQLite) recorded for {agent_id}."}]}
        finally:
            conn.close()

    def register_worktree(self, agent_id: str, repo_root: Path, worktree: dict[str, Any], ttl_seconds: int | None, status: str | None, intent: str | None, message: str | None) -> dict[str, Any]:
        branch = worktree.get("branch")
        now = time.time()
        ttl = ttl_seconds or _default_ttl_seconds()
        conn = self._get_conn()
        try:
            conn.execute("INSERT OR REPLACE INTO worktrees (branch, path, agent_id, expires_at_epoch, metadata) VALUES (?, ?, ?, ?, ?)",
                         (branch, worktree.get("path"), agent_id, now + ttl, json.dumps(worktree)))
            conn.execute("""
                INSERT INTO agents (agent_id, worktree, status, updated_at, expires_at_epoch)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    worktree=excluded.worktree,
                    status=COALESCE(excluded.status, agents.status),
                    updated_at=excluded.updated_at,
                    expires_at_epoch=excluded.expires_at_epoch
            """, (agent_id, json.dumps(worktree), status, _iso_now(), now + ttl))
            conn.commit()
            return {"content": [{"type": "text", "text": f"Registered worktree for {agent_id}: branch={branch}"}]}
        finally:
            conn.close()

    def prepare_worktree(self, agent_id: str, repo_root: Path, branch: str, base_branch: str, worktree_path: Path, allow_dirty_root: bool, ttl_seconds: int | None) -> dict[str, Any]:
        if not allow_dirty_root:
            status = _run_git(repo_root, ["status", "--porcelain"])
            if status: raise RuntimeError("Repo root is dirty.")
        _run_git(repo_root, ["worktree", "add", "-b", branch, str(worktree_path), base_branch])
        self.register_worktree(agent_id, repo_root, {"path": str(worktree_path), "branch": branch, "base_branch": base_branch}, ttl_seconds, "planning", None, None)
        return {"content": [{"type": "text", "text": f"Prepared worktree for {agent_id}: branch={branch} base={base_branch} path={worktree_path}"}]}

    def remove_worktree(self, agent_id: str, repo_root: Path, branch: str, worktree_path: Path, force: bool, ttl_seconds: int | None) -> dict[str, Any]:
        args = ["worktree", "remove"]
        if force: args.append("--force")
        args.append(str(worktree_path))
        _run_git(repo_root, args)
        
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM worktrees WHERE branch = ?", (branch,))
            conn.execute("UPDATE agents SET worktree = '{}' WHERE agent_id = ?", (agent_id,))
            conn.commit()
            return {"content": [{"type": "text", "text": f"Removed worktree for {agent_id}: branch={branch} path={worktree_path}"}]}
        finally:
            conn.close()

    def inspect_state(self, include_events: bool, event_limit: int) -> dict[str, Any]:
        conn = self._get_conn()
        now = time.time()
        try:
            lines = [f"Backend: SQLite ({self.db_path})"]
            
            cursor = conn.execute("SELECT * FROM agents WHERE expires_at_epoch > ?", (now,))
            agents = [dict(r) for r in cursor.fetchall()]
            if not agents: lines.append("Active agents: none")
            else:
                lines.append("Active agents:")
                for a in agents:
                    cl_raw = a['claimed_files']
                    cl_list = json.loads(cl_raw) if cl_raw else []
                    line = f"- {a['agent_id']} status={a['status']} claims={','.join(cl_list)}"
                    wt_raw = a.get('worktree')
                    wt = _format_worktree(json.loads(wt_raw) if wt_raw else None)
                    if wt: line += f" worktree={wt}"
                    lines.append(line)
            
            cursor = conn.execute("SELECT * FROM claims WHERE expires_at_epoch > ?", (now,))
            claims = [dict(r) for r in cursor.fetchall()]
            if not claims: lines.append("Authoritative claims: none")
            else:
                lines.append("Authoritative claims:")
                for c in claims:
                    lines.append(f"- {c['claimed_path']} owner={c['agent_id']} mode={c['mode']}")

            if include_events:
                cursor = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (event_limit,))
                events = [dict(r) for r in cursor.fetchall()]
                if not events: lines.append("Recent events: none")
                else:
                    lines.append("Recent events:")
                    for e in events: lines.append(f"- {e['timestamp']} {e['kind']} by {e['agent_id']}: {e['message']}")

            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
        finally:
            conn.close()

    def query_peers(self, agent_id: str, query: str, candidate_files: list[str]) -> dict[str, Any]:
        normalized = _normalize_paths(candidate_files)
        now = time.time()
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT * FROM claims WHERE expires_at_epoch > ? AND agent_id != ?", (now, agent_id))
            claim_records = [dict(r) for r in cursor.fetchall()]
            
            conflicts = []
            authoritative_paths = set()
            for rec in claim_records:
                owner = rec['agent_id']
                claimed = rec['claimed_path']
                authoritative_paths.add((owner, claimed))
                exclusions = json.loads(rec.get("exclusions", "[]"))
                for c in normalized:
                    if _paths_overlap(c, claimed):
                        if c not in exclusions:
                            conflicts.append(f"{owner} -> {c} (peer claim: {claimed})")
            
            cursor = conn.execute("SELECT * FROM agents WHERE expires_at_epoch > ? AND agent_id != ?", (now, agent_id))
            peers = []
            for a in cursor.fetchall():
                pid = a['agent_id']
                peer_claims = json.loads(a['claimed_files'] if a['claimed_files'] else "[]")
                for pc in peer_claims:
                    if (pid, pc) not in authoritative_paths:
                        for c in normalized:
                            if _paths_overlap(c, pc):
                                conflicts.append(f"{pid} -> {c} (peer claim: {pc})")
                peers.append(f"{pid} status={a['status']} claims={','.join(peer_claims)}")
            
            text = ""
            if conflicts: text += "Conflicts detected with active peers:\n" + "\n".join(sorted(list(set(conflicts)))) + "\n\n"
            else: text += "No direct conflicts detected.\n\n"
            text += "Active peers:\n" + ("\n".join(peers) if peers else "none")
            return {"content": [{"type": "text", "text": text}]}
        finally:
            conn.close()

    def prune_stale(self, event_retention_seconds: int) -> dict[str, Any]:
        now = time.time()
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM agents WHERE expires_at_epoch < ?", (now,))
            conn.execute("DELETE FROM claims WHERE expires_at_epoch < ?", (now,))
            conn.execute("DELETE FROM worktrees WHERE expires_at_epoch < ?", (now,))
            conn.execute("DELETE FROM events WHERE timestamp < ?", 
                         (datetime.fromtimestamp(now - event_retention_seconds, tz=timezone.utc).isoformat(),))
            conn.commit()
            return {"content": [{"type": "text", "text": "Pruned stale SQLite records."}]}
        finally:
            conn.close()


# --- Factory & Handler ---

import sqlite3

def get_provider() -> ScionProvider:
    backend = os.environ.get("SCION_BACKEND", "sqlite").strip().lower()
    if backend == "redis":
        host = os.environ.get("REDIS_HOST", "localhost")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        return RedisScionProvider(host, port)
    if backend == "sqlite":
        db_path = _shared_dir() / "scion.db"
        return SqliteScionProvider(db_path)
    return FileScionProvider(_shared_dir())


def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    provider = get_provider()
    tool = request.get("name")
    args = request.get("arguments", {})
    agent_id = _agent_id()

    try:
        if tool == "scion_broadcast":
            return provider.broadcast(agent_id, args.get("message", ""), args.get("files", []), args.get("status", "active"), args.get("intent", ""), args.get("ttl_seconds"), args.get("metadata", {}))
        if tool == "scion_claim_files":
            mode = str(args.get("mode", "")).strip().lower() or "advisory"
            if bool(args.get("strict", False)): mode = "exclusive"
            return provider.claim_files(agent_id, args.get("files", []), mode, args.get("intent", ""), args.get("message", ""), args.get("ttl_seconds"), args.get("takeover_from", ""), args.get("metadata", {}))
        if tool == "scion_release_claims":
            return provider.release_claims(agent_id, args.get("files", []), args.get("note", ""), args.get("ttl_seconds"))
        if tool == "scion_heartbeat":
            return provider.heartbeat(agent_id, status=args.get("status"), intent=args.get("intent"), message=args.get("message"), ttl_seconds=args.get("ttl_seconds"))
        if tool == "scion_inspect_state":
            return provider.inspect_state(args.get("include_events", True), args.get("event_limit", 10))
        if tool == "scion_query_peers":
            return provider.query_peers(agent_id, args.get("query", ""), args.get("candidate_files", []))
        if tool == "scion_prune_stale":
            return provider.prune_stale(args.get("event_retention_seconds", 86400))
        
        if tool == "scion_prepare_worktree":
            repo_root = _repo_root(args.get("repo_root"))
            branch = args.get("branch") or f"scion-{agent_id}"
            base_branch = args.get("base_branch") or "main"
            worktree_path = Path(args.get("worktree_path") or str(_angella_root() / ".scion" / "worktrees" / branch))
            return provider.prepare_worktree(agent_id, repo_root, branch, base_branch, worktree_path, args.get("allow_dirty_root", False), args.get("ttl_seconds"))
        
        if tool == "scion_remove_worktree":
            repo_root = _repo_root(args.get("repo_root"))
            branch = args.get("branch")
            worktree_path = Path(args.get("worktree_path"))
            return provider.remove_worktree(agent_id, repo_root, branch, worktree_path, args.get("force", True), args.get("ttl_seconds"))

        if tool == "scion_register_worktree":
            repo_root = _repo_root(args.get("repo_root"))
            worktree = {"path": args.get("worktree_path") or args.get("path"), "branch": args.get("branch")}
            return provider.register_worktree(agent_id, repo_root, worktree, args.get("ttl_seconds"), args.get("status"), args.get("intent"), args.get("message"))

        return {"error": f"Unknown tool: {tool}"}
    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    for line in sys.stdin:
        try:
            req = json.loads(line.strip())
            print(json.dumps(handle_request(req)), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)
