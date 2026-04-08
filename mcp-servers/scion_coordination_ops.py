#!/usr/bin/env python3
"""
MCP Server for Scion-style coordination.
Provides file-backed peer discovery, file claiming, and broadcast events
within a shared directory that mimics a lightweight Scion Grove.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def _agents_dir() -> Path:
    return _shared_dir() / "agents"


def _events_dir() -> Path:
    return _shared_dir() / "events"


def _claims_dir() -> Path:
    return _shared_dir() / "claims"


def _worktrees_dir() -> Path:
    return _shared_dir() / "worktrees"


def _ensure_layout() -> None:
    _agents_dir().mkdir(parents=True, exist_ok=True)
    _events_dir().mkdir(parents=True, exist_ok=True)
    _claims_dir().mkdir(parents=True, exist_ok=True)
    _worktrees_dir().mkdir(parents=True, exist_ok=True)


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


def _agent_state_path(agent_id: str) -> Path:
    return _agents_dir() / f"{agent_id}.json"


def _claim_record_path(claimed_path: str) -> Path:
    return Path(f"{_claims_dir() / Path(claimed_path)}.json")


def _worktree_record_path(branch: str) -> Path:
    branch_key = _normalize_path(branch)
    return Path(f"{_worktrees_dir() / Path(branch_key)}.json")


def _claimed_path_from_record_path(path: Path) -> str:
    relative = path.relative_to(_claims_dir()).as_posix()
    if relative.endswith(".json"):
        return relative[:-5]
    return relative


def _event_timestamp_prefix() -> int:
    return int(_utc_now().timestamp() * 1000)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return True


def _fresh(state: dict[str, Any]) -> bool:
    expires = float(state.get("expires_at_epoch", 0.0) or 0.0)
    return expires > time.time()


def _load_agent_state(agent_id: str) -> dict[str, Any]:
    path = _agent_state_path(agent_id)
    if path.exists():
        return _read_json(path)
    ttl = _default_ttl_seconds()
    now = time.time()
    return {
        "agent_id": agent_id,
        "status": "idle",
        "intent": "",
        "message": "",
        "claimed_files": [],
        "metadata": {},
        "worktree": {},
        "updated_at": _iso_now(),
        "updated_at_epoch": now,
        "expires_at_epoch": now + ttl,
    }


def _save_agent_state(
    agent_id: str,
    *,
    status: str | None = None,
    intent: str | None = None,
    message: str | None = None,
    claimed_files: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    worktree: dict[str, Any] | None = None,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    state = _load_agent_state(agent_id)
    now = time.time()
    ttl = max(30, ttl_seconds or _default_ttl_seconds())

    if status is not None:
        state["status"] = status
    if intent is not None:
        state["intent"] = intent
    if message is not None:
        state["message"] = message
    if claimed_files is not None:
        state["claimed_files"] = _normalize_paths(claimed_files)
    if metadata is not None:
        state["metadata"] = metadata
    if worktree is not None:
        state["worktree"] = worktree

    state["updated_at"] = _iso_now()
    state["updated_at_epoch"] = now
    state["expires_at_epoch"] = now + ttl

    _write_json(_agent_state_path(agent_id), state)
    return state


def _record_event(agent_id: str, kind: str, payload: dict[str, Any]) -> Path:
    now = _utc_now()
    event = {
        "agent_id": agent_id,
        "kind": kind,
        "timestamp": now.isoformat(),
        "payload": payload,
    }
    path = _events_dir() / f"{int(now.timestamp() * 1000)}-{agent_id}-{kind}.json"
    _write_json(path, event)
    return path


def _active_peers(self_id: str) -> list[dict[str, Any]]:
    peers: list[dict[str, Any]] = []
    for path in sorted(_agents_dir().glob("*.json")):
        try:
            state = _read_json(path)
        except Exception:
            continue
        if state.get("agent_id") == self_id:
            continue
        if not _fresh(state):
            continue
        peers.append(state)
    return peers


def _all_fresh_agents() -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for path in sorted(_agents_dir().glob("*.json")):
        try:
            state = _read_json(path)
        except Exception:
            continue
        if not _fresh(state):
            continue
        agents.append(state)
    return agents


def _paths_overlap(candidate: str, claimed: str) -> bool:
    if candidate == claimed:
        return True
    return candidate.startswith(f"{claimed}/") or claimed.startswith(f"{candidate}/")


def _overlap_pairs(candidate_files: list[str], peer_files: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in _normalize_paths(candidate_files):
        for claimed in _normalize_paths(peer_files):
            if not _paths_overlap(candidate, claimed):
                continue
            pair = (candidate, claimed)
            if pair in seen:
                continue
            seen.add(pair)
            pairs.append(pair)
    return pairs


def _format_conflict_pairs(pairs: list[tuple[str, str]]) -> str:
    rendered: list[str] = []
    for candidate, claimed in pairs:
        if candidate == claimed:
            rendered.append(candidate)
        else:
            rendered.append(f"{candidate} (peer claim: {claimed})")
    return ", ".join(rendered)


def _format_worktree(worktree: dict[str, Any] | None) -> str:
    if not worktree:
        return ""

    path = str(worktree.get("path", "")).strip()
    branch = str(worktree.get("branch", "")).strip()
    base_branch = str(worktree.get("base_branch", "")).strip()
    clean = worktree.get("clean")
    head_sha = str(worktree.get("head_sha", "")).strip()

    parts: list[str] = []
    if branch:
        parts.append(f"branch={branch}")
    if base_branch:
        parts.append(f"base={base_branch}")
    if clean is not None:
        parts.append(f"clean={str(bool(clean)).lower()}")
    if head_sha:
        parts.append(f"head={head_sha}")
    if path:
        parts.append(f"path={path}")
    return " ".join(parts)


def _load_claim_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not _claims_dir().exists():
        return records

    for path in sorted(_claims_dir().rglob("*.json")):
        try:
            record = _read_json(path)
        except Exception:
            continue
        record["_path"] = path
        record["claimed_path"] = _normalize_path(str(record.get("claimed_path", "") or _claimed_path_from_record_path(path)))
        records.append(record)
    return records


def _load_worktree_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not _worktrees_dir().exists():
        return records

    for path in sorted(_worktrees_dir().rglob("*.json")):
        try:
            record = _read_json(path)
        except Exception:
            continue
        record["_path"] = path
        record["branch"] = _normalize_path(str(record.get("branch", "") or path.relative_to(_worktrees_dir()).as_posix()[:-5]))
        records.append(record)
    return records


def _fresh_claim_record(record: dict[str, Any]) -> bool:
    expires = float(record.get("expires_at_epoch", 0.0) or 0.0)
    return expires > time.time()


def _fresh_worktree_record(record: dict[str, Any]) -> bool:
    expires = float(record.get("expires_at_epoch", 0.0) or 0.0)
    return expires > time.time()


def _claim_conflicts_for_files(self_id: str, candidate_files: list[str]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for record in _load_claim_records():
        if not _fresh_claim_record(record):
            continue
        owner = str(record.get("agent_id", "")).strip()
        if not owner or owner == self_id:
            continue
        pairs = _overlap_pairs(candidate_files, [record.get("claimed_path", "")])
        if not pairs:
            continue
        conflicts.append(
            {
                "agent_id": owner,
                "claimed_path": record["claimed_path"],
                "claim_mode": record.get("claim_mode", "exclusive"),
                "pairs": pairs,
                "intent": record.get("intent", ""),
                "message": record.get("message", ""),
                "worktree": record.get("worktree", {}),
                "_path": record["_path"],
                "_record": record,
            }
        )
    return conflicts


def _self_claim_records(agent_id: str) -> list[dict[str, Any]]:
    return [record for record in _load_claim_records() if record.get("agent_id") == agent_id]


def _self_worktree_records(agent_id: str) -> list[dict[str, Any]]:
    return [record for record in _load_worktree_records() if record.get("agent_id") == agent_id]


def _agent_claim_ttl_seconds(state: dict[str, Any]) -> int:
    remaining = int(float(state.get("expires_at_epoch", 0.0) or 0.0) - time.time())
    return max(30, remaining)


def _drop_claimed_files_from_agent(agent_id: str, claimed_paths: list[str]) -> None:
    if not claimed_paths:
        return
    state_path = _agent_state_path(agent_id)
    if not state_path.exists():
        return
    state = _load_agent_state(agent_id)
    removal = set(_normalize_paths(claimed_paths))
    current = _normalize_paths(state.get("claimed_files", []))
    remaining = [item for item in current if item not in removal]
    status = "idle" if not remaining else state.get("status", "active")
    _save_agent_state(
        agent_id,
        status=status,
        intent=state.get("intent", ""),
        message=state.get("message", ""),
        claimed_files=remaining,
        metadata=state.get("metadata", {}),
        worktree=state.get("worktree", {}),
        ttl_seconds=_agent_claim_ttl_seconds(state),
    )


def _claim_payload(
    agent_id: str,
    claimed_path: str,
    *,
    claim_mode: str,
    intent: str,
    message: str,
    metadata: dict[str, Any],
    worktree: dict[str, Any],
    ttl_seconds: int,
) -> dict[str, Any]:
    now = time.time()
    return {
        "agent_id": agent_id,
        "claimed_path": claimed_path,
        "claim_mode": claim_mode,
        "intent": intent,
        "message": message,
        "metadata": metadata,
        "worktree": worktree,
        "claimed_at": _iso_now(),
        "claimed_at_epoch": now,
        "expires_at_epoch": now + max(30, ttl_seconds),
    }


def _worktree_payload(
    agent_id: str,
    *,
    repo_root: Path,
    branch: str,
    base_branch: str,
    worktree_path: Path,
    head_sha: str,
    clean: bool,
    ttl_seconds: int,
) -> dict[str, Any]:
    now = time.time()
    return {
        "agent_id": agent_id,
        "repo_root": str(repo_root),
        "branch": branch,
        "base_branch": base_branch,
        "path": str(worktree_path),
        "head_sha": head_sha,
        "clean": clean,
        "registered_at": _iso_now(),
        "registered_at_epoch": now,
        "expires_at_epoch": now + max(30, ttl_seconds),
    }


def _claim_conflict_text(conflicts: list[dict[str, Any]]) -> str:
    rendered: list[str] = []
    for conflict in conflicts:
        rendered.append(f"{conflict['agent_id']} -> {_format_conflict_pairs(conflict['pairs'])}")
    return "; ".join(rendered)


def _worktree_conflict_text(records: list[dict[str, Any]]) -> str:
    rendered: list[str] = []
    for record in records:
        rendered.append(
            f"{record.get('agent_id', 'unknown')} -> branch={record.get('branch', '')} path={record.get('path', '')}"
        )
    return "; ".join(rendered)


def _default_worktree_root(repo_root: Path) -> Path:
    configured = os.environ.get("SCION_WORKTREE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(tempfile.gettempdir()) / "angella-scion-worktrees" / repo_root.name).resolve()


def _default_worktree_path(repo_root: Path, agent_id: str) -> Path:
    return (_default_worktree_root(repo_root) / agent_id).resolve()


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


def _git_status_clean(repo_root: Path) -> bool:
    output = _run_git(repo_root, ["status", "--porcelain", "--untracked-files=all"])
    return not output.strip()


def _git_worktree_head(repo_root: Path, worktree_path: Path) -> str:
    return _run_git(repo_root, ["-C", str(worktree_path), "rev-parse", "HEAD"])


def _git_worktree_clean(repo_root: Path, worktree_path: Path) -> bool:
    output = _run_git(repo_root, ["-C", str(worktree_path), "status", "--porcelain", "--untracked-files=all"])
    return not output.strip()


def _worktree_metadata_from_runtime(repo_root: Path, worktree_path: Path, branch: str, base_branch: str) -> dict[str, Any]:
    return {
        "path": str(worktree_path),
        "branch": branch,
        "base_branch": base_branch,
        "head_sha": _git_worktree_head(repo_root, worktree_path),
        "clean": _git_worktree_clean(repo_root, worktree_path),
        "registered_at": _iso_now(),
    }


def _update_self_claim_worktree(agent_id: str, worktree: dict[str, Any]) -> None:
    for record in _self_claim_records(agent_id):
        claim_path = record.get("_path")
        if not isinstance(claim_path, Path):
            continue
        refreshed = dict(record)
        refreshed.pop("_path", None)
        refreshed["worktree"] = worktree
        _write_json(claim_path, refreshed)


def _upsert_worktree_record(agent_id: str, repo_root: Path, worktree: dict[str, Any], ttl_seconds: int) -> None:
    branch = _normalize_path(str(worktree.get("branch", "")).strip())
    path_raw = str(worktree.get("path", "")).strip()
    if not branch or not path_raw:
        return

    worktree_path = Path(path_raw).expanduser().resolve()
    conflicts: list[dict[str, Any]] = []
    for record in _load_worktree_records():
        if not _fresh_worktree_record(record):
            continue
        if record.get("branch") == branch and record.get("agent_id") == agent_id:
            continue
        if Path(str(record.get("path", ""))).resolve() == worktree_path and record.get("agent_id") == agent_id:
            continue
        if record.get("branch") == branch or Path(str(record.get("path", ""))).resolve() == worktree_path:
            conflicts.append(record)
    if conflicts:
        raise RuntimeError(f"Conflicting Scion worktree reservations detected: {_worktree_conflict_text(conflicts)}")

    payload = _worktree_payload(
        agent_id,
        repo_root=repo_root,
        branch=branch,
        base_branch=str(worktree.get("base_branch", "")).strip(),
        worktree_path=worktree_path,
        head_sha=str(worktree.get("head_sha", "")).strip(),
        clean=bool(worktree.get("clean", False)),
        ttl_seconds=ttl_seconds,
    )
    _write_json(_worktree_record_path(branch), payload)


def _prepare_worktree(
    agent_id: str,
    *,
    repo_root: Path,
    branch: str,
    base_branch: str,
    worktree_path: Path,
    allow_dirty_root: bool,
    ttl_seconds: int,
) -> dict[str, Any]:
    if not allow_dirty_root and not _git_status_clean(repo_root):
        raise RuntimeError("Refusing to prepare worktree from a dirty repository root.")

    conflicts = []
    for record in _load_worktree_records():
        if not _fresh_worktree_record(record):
            continue
        if record.get("agent_id") == agent_id and record.get("branch") == branch and Path(str(record.get("path", ""))).resolve() == worktree_path:
            if worktree_path.exists():
                return _worktree_payload(
                    agent_id,
                    repo_root=repo_root,
                    branch=branch,
                    base_branch=base_branch,
                    worktree_path=worktree_path,
                    head_sha=_git_worktree_head(repo_root, worktree_path),
                    clean=_git_worktree_clean(repo_root, worktree_path),
                    ttl_seconds=ttl_seconds,
                )
        if record.get("branch") == branch or Path(str(record.get("path", ""))).resolve() == worktree_path:
            conflicts.append(record)
    if conflicts:
        raise RuntimeError(f"Conflicting Scion worktree reservations detected: {_worktree_conflict_text(conflicts)}")

    if worktree_path.exists() and any(worktree_path.iterdir()):
        raise RuntimeError(f"Requested worktree path already exists and is not empty: {worktree_path}")

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _run_git(repo_root, ["worktree", "add", "-b", branch, str(worktree_path), base_branch])
    return _worktree_payload(
        agent_id,
        repo_root=repo_root,
        branch=branch,
        base_branch=base_branch,
        worktree_path=worktree_path,
        head_sha=_git_worktree_head(repo_root, worktree_path),
        clean=_git_worktree_clean(repo_root, worktree_path),
        ttl_seconds=ttl_seconds,
    )


def _remove_worktree_record(branch: str) -> None:
    path = _worktree_record_path(branch)
    path.unlink(missing_ok=True)


def _remove_worktree(
    agent_id: str,
    *,
    repo_root: Path,
    branch: str,
    worktree_path: Path,
    force: bool,
) -> None:
    record_path = _worktree_record_path(branch)
    if record_path.exists():
        try:
            record = _read_json(record_path)
        except Exception:
            record = {}
        owner = str(record.get("agent_id", "")).strip()
        if owner and owner != agent_id:
            raise RuntimeError(f"Worktree reservation for {branch} is owned by {owner}, not {agent_id}.")

    if worktree_path.exists():
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))
        _run_git(repo_root, args)
    _remove_worktree_record(branch)


def _authoritative_claim_files(
    agent_id: str,
    files: list[str],
    *,
    claim_mode: str,
    takeover_from: str,
    intent: str,
    message: str,
    metadata: dict[str, Any],
    worktree: dict[str, Any],
    ttl_seconds: int,
) -> list[dict[str, Any]]:
    created_paths: list[Path] = []
    replaced_records: list[tuple[Path, dict[str, Any]]] = []
    took_over_from: list[dict[str, Any]] = []
    conflicts = _claim_conflicts_for_files(agent_id, files)

    if claim_mode == "exclusive" and conflicts:
        raise RuntimeError(f"Conflicting Scion claims detected: {_claim_conflict_text(conflicts)}")

    if claim_mode == "takeover":
        if not takeover_from:
            raise RuntimeError("takeover_from is required when claim mode is takeover.")
        for conflict in conflicts:
            if conflict["agent_id"] != takeover_from:
                raise RuntimeError(f"Cannot take over claim owned by {conflict['agent_id']}; expected {takeover_from}.")
            if any(candidate != conflict["claimed_path"] for candidate, _claimed in conflict["pairs"]):
                raise RuntimeError(
                    "Takeover only supports exact claim handoff. Split broad claims before taking over nested files."
                )

    try:
        for claimed_path in files:
            claim_path = _claim_record_path(claimed_path)
            current_record = _read_json(claim_path) if claim_path.exists() else {}
            current_owner = str(current_record.get("agent_id", "")).strip()

            payload = _claim_payload(
                agent_id,
                claimed_path,
                claim_mode=claim_mode,
                intent=intent,
                message=message,
                metadata=metadata,
                worktree=worktree,
                ttl_seconds=ttl_seconds,
            )

            if current_record and _fresh_claim_record(current_record) and current_owner not in {"", agent_id}:
                if claim_mode != "takeover" or current_owner != takeover_from or current_record.get("claimed_path") != claimed_path:
                    raise RuntimeError(f"Conflicting Scion claims detected: {_claim_conflict_text(conflicts)}")

            if claim_path.exists():
                if current_record:
                    replaced_records.append((claim_path, current_record))
                    if current_owner and current_owner != agent_id:
                        took_over_from.append(current_record)
                _write_json(claim_path, payload)
                continue

            if _write_json_exclusive(claim_path, payload):
                created_paths.append(claim_path)
                continue

            latest = _read_json(claim_path)
            latest_owner = str(latest.get("agent_id", "")).strip()
            latest_path = _normalize_path(str(latest.get("claimed_path", claimed_path)))
            if _fresh_claim_record(latest) and latest_owner not in {"", agent_id}:
                raise RuntimeError(f"Conflicting Scion claims detected: {_claim_conflict_text(conflicts)}")
            replaced_records.append((claim_path, latest))
            if latest_owner and latest_owner != agent_id:
                took_over_from.append(latest)
            latest["claimed_path"] = latest_path
            _write_json(claim_path, payload)

        for previous in took_over_from:
            _drop_claimed_files_from_agent(str(previous.get("agent_id", "")), [str(previous.get("claimed_path", ""))])
        return took_over_from
    except Exception:
        for path in created_paths:
            path.unlink(missing_ok=True)
        for path, previous in reversed(replaced_records):
            _write_json(path, previous)
        raise


def _summary_for_query(peers: list[dict[str, Any]], candidate_files: list[str]) -> str:
    if not peers:
        return f"No active Scion peers registered in {_shared_dir()}."

    overlaps: list[str] = []
    peer_lines: list[str] = []
    for peer in peers:
        claimed = peer.get("claimed_files", [])
        status = peer.get("status", "unknown")
        message = peer.get("message", "")
        intent = peer.get("intent", "")
        peer_line = f"{peer['agent_id']} status={status}"
        if claimed:
            peer_line += f" claims={','.join(claimed)}"
        if intent:
            peer_line += f" intent={intent}"
        if message:
            peer_line += f" message={message}"
        worktree = _format_worktree(peer.get("worktree", {}))
        if worktree:
            peer_line += f" worktree={worktree}"
        peer_lines.append(peer_line)

        overlap = _overlap_pairs(candidate_files, claimed)
        if overlap:
            overlaps.append(f"{peer['agent_id']} -> {_format_conflict_pairs(overlap)}")

    if overlaps:
        return "Conflicts detected with active peers:\n" + "\n".join(overlaps) + "\n\nActive peers:\n" + "\n".join(peer_lines)
    return "No direct conflicts detected.\n\nActive peers:\n" + "\n".join(peer_lines)


def _conflicts_for_files(self_id: str, candidate_files: list[str]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for peer in _active_peers(self_id):
        overlap = _overlap_pairs(candidate_files, peer.get("claimed_files", []))
        if overlap:
            conflicts.append(
                {
                    "agent_id": peer["agent_id"],
                    "files": [candidate for candidate, _claimed in overlap],
                    "pairs": overlap,
                    "status": peer.get("status", "unknown"),
                    "intent": peer.get("intent", ""),
                    "message": peer.get("message", ""),
                    "worktree": peer.get("worktree", {}),
                }
            )
    return conflicts


def _recent_events(limit: int = 10) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in sorted(_events_dir().glob("*.json"), reverse=True)[:limit]:
        try:
            payload = _read_json(path)
        except Exception:
            continue
        payload["_path"] = path.name
        events.append(payload)
    return events


def _inspect_state_text(*, include_events: bool = True, event_limit: int = 10) -> str:
    agents = _all_fresh_agents()
    lines: list[str] = [f"Shared dir: {_shared_dir()}"]
    if not agents:
        lines.append("Active agents: none")
    else:
        lines.append("Active agents:")
        for agent in agents:
            line = f"- {agent['agent_id']} status={agent.get('status', 'unknown')}"
            claims = agent.get("claimed_files", [])
            if claims:
                line += f" claims={','.join(claims)}"
            intent = agent.get("intent", "")
            if intent:
                line += f" intent={intent}"
            message = agent.get("message", "")
            if message:
                line += f" message={message}"
            worktree = _format_worktree(agent.get("worktree", {}))
            if worktree:
                line += f" worktree={worktree}"
            lines.append(line)

    claim_records = [record for record in _load_claim_records() if _fresh_claim_record(record)]
    if not claim_records:
        lines.append("Authoritative claims: none")
    else:
        lines.append("Authoritative claims:")
        for record in claim_records:
            line = (
                f"- {record.get('claimed_path', 'unknown')} owner={record.get('agent_id', 'unknown')} "
                f"mode={record.get('claim_mode', 'exclusive')}"
            )
            worktree = _format_worktree(record.get("worktree", {}))
            if worktree:
                line += f" worktree={worktree}"
            lines.append(line)

    worktree_records = [record for record in _load_worktree_records() if _fresh_worktree_record(record)]
    if not worktree_records:
        lines.append("Reserved worktrees: none")
    else:
        lines.append("Reserved worktrees:")
        for record in worktree_records:
            line = (
                f"- owner={record.get('agent_id', 'unknown')} branch={record.get('branch', 'unknown')}"
                f" path={record.get('path', 'unknown')}"
            )
            base_branch = str(record.get("base_branch", "")).strip()
            if base_branch:
                line += f" base={base_branch}"
            clean = record.get("clean")
            if clean is not None:
                line += f" clean={str(bool(clean)).lower()}"
            lines.append(line)

    if include_events:
        events = _recent_events(limit=event_limit)
        if not events:
            lines.append("Recent events: none")
        else:
            lines.append("Recent events:")
            for event in events:
                lines.append(
                    f"- {event['_path']} kind={event.get('kind', 'unknown')} agent={event.get('agent_id', 'unknown')}"
                )
    return "\n".join(lines)


def _prune_stale(*, event_retention_seconds: int = 86400) -> dict[str, Any]:
    now = time.time()
    stale_agents: list[str] = []
    pruned_events: list[str] = []
    stale_claims: list[str] = []
    stale_worktrees: list[str] = []

    for path in sorted(_agents_dir().glob("*.json")):
        try:
            state = _read_json(path)
        except Exception:
            path.unlink(missing_ok=True)
            stale_agents.append(path.name)
            continue
        if not _fresh(state):
            path.unlink(missing_ok=True)
            stale_agents.append(path.name)

    cutoff = now - max(60, event_retention_seconds)
    for path in sorted(_events_dir().glob("*.json")):
        try:
            prefix = int(path.name.split("-", 1)[0])
        except Exception:
            continue
        if prefix / 1000.0 < cutoff:
            path.unlink(missing_ok=True)
            pruned_events.append(path.name)

    for path in sorted(_claims_dir().rglob("*.json")):
        remove = False
        try:
            record = _read_json(path)
        except Exception:
            remove = True
            record = {}
        claimed_path = _normalize_path(str(record.get("claimed_path", "") or _claimed_path_from_record_path(path)))
        owner = str(record.get("agent_id", "")).strip()
        if not remove and not _fresh_claim_record(record):
            remove = True
        if not remove and (not owner or not claimed_path):
            remove = True
        if not remove:
            owner_path = _agent_state_path(owner)
            if not owner_path.exists():
                remove = True
            else:
                try:
                    owner_state = _read_json(owner_path)
                except Exception:
                    remove = True
                else:
                    if not _fresh(owner_state):
                        remove = True
                    elif claimed_path not in _normalize_paths(owner_state.get("claimed_files", [])):
                        remove = True
        if remove:
            path.unlink(missing_ok=True)
            stale_claims.append(str(path.relative_to(_claims_dir())))

    for path in sorted(_worktrees_dir().rglob("*.json")):
        remove = False
        try:
            record = _read_json(path)
        except Exception:
            remove = True
            record = {}

        owner = str(record.get("agent_id", "")).strip()
        branch = _normalize_path(str(record.get("branch", "") or path.relative_to(_worktrees_dir()).as_posix()[:-5]))
        worktree_path = str(record.get("path", "")).strip()
        if not remove and not _fresh_worktree_record(record):
            remove = True
        if not remove and (not owner or not branch or not worktree_path):
            remove = True
        if not remove:
            owner_path = _agent_state_path(owner)
            if not owner_path.exists():
                remove = True
            else:
                try:
                    owner_state = _read_json(owner_path)
                except Exception:
                    remove = True
                else:
                    owner_worktree = owner_state.get("worktree", {})
                    if not _fresh(owner_state):
                        remove = True
                    elif str(owner_worktree.get("branch", "")).strip() != branch:
                        remove = True
                    elif str(owner_worktree.get("path", "")).strip() != worktree_path:
                        remove = True
        if remove:
            path.unlink(missing_ok=True)
            stale_worktrees.append(str(path.relative_to(_worktrees_dir())))

    return {
        "stale_agents_removed": stale_agents,
        "events_removed": pruned_events,
        "claims_removed": stale_claims,
        "worktrees_removed": stale_worktrees,
    }


def handle_request(request: dict) -> dict:
    if request.get("type") != "call_tool":
        return {"error": "Only call_tool requests are supported."}

    _ensure_layout()

    tool = request.get("name")
    args = request.get("arguments", {})
    agent_id = _agent_id()

    if tool == "scion_broadcast":
        message = args.get("message")
        if not message:
            return {"error": "Missing 'message' argument."}
        files = _normalize_paths(args.get("files", []))
        status = args.get("status", "active")
        metadata = args.get("metadata", {})
        ttl_seconds = args.get("ttl_seconds")

        previous = _load_agent_state(agent_id)
        state = _save_agent_state(
            agent_id,
            status=status,
            message=message,
            intent=args.get("intent", previous.get("intent", "")),
            claimed_files=files if files else previous.get("claimed_files", []),
            metadata=metadata,
            worktree=previous.get("worktree", {}),
            ttl_seconds=ttl_seconds,
        )
        event_path = _record_event(agent_id, "broadcast", {"message": message, "files": state.get("claimed_files", [])})
        text = (
            f"Broadcast recorded for {agent_id} in {_shared_dir()} "
            f"(claims={len(state.get('claimed_files', []))}, event={event_path.name})."
        )
        print(f"[SCION BROADCAST from {agent_id}] {message}", file=sys.stderr)
        return {"content": [{"type": "text", "text": text}]}

    if tool == "scion_register_worktree":
        worktree_path_raw = str(args.get("worktree_path", args.get("path", ""))).strip()
        if not worktree_path_raw:
            return {"error": "Missing 'worktree_path' argument."}
        state = _load_agent_state(agent_id)
        repo_root = _repo_root(args.get("repo_root"))
        ttl = max(30, int(args.get("ttl_seconds", _default_ttl_seconds())))
        worktree = {
            "path": str(Path(worktree_path_raw).expanduser().resolve()),
            "branch": str(args.get("branch", "")).strip(),
            "base_branch": str(args.get("base_branch", "")).strip(),
            "head_sha": str(args.get("head_sha", "")).strip(),
            "clean": args.get("clean"),
            "registered_at": _iso_now(),
        }
        try:
            _upsert_worktree_record(agent_id, repo_root, worktree, ttl)
        except RuntimeError as exc:
            return {"error": str(exc)}
        _save_agent_state(
            agent_id,
            status=args.get("status", state.get("status", "planning")),
            intent=args.get("intent", state.get("intent", "")),
            message=args.get("message", state.get("message", "")),
            claimed_files=state.get("claimed_files", []),
            metadata=state.get("metadata", {}),
            worktree=worktree,
            ttl_seconds=ttl,
        )
        _record_event(agent_id, "worktree", worktree)
        return {"content": [{"type": "text", "text": f"Registered worktree for {agent_id}: {_format_worktree(worktree)}"}]}

    if tool == "scion_prepare_worktree":
        state = _load_agent_state(agent_id)
        ttl = max(30, int(args.get("ttl_seconds", _default_ttl_seconds())))
        branch = _normalize_path(str(args.get("branch", "")).strip() or f"codex/scion-{agent_id}")
        base_branch = str(args.get("base_branch", "main")).strip() or "main"
        repo_root = _repo_root(args.get("repo_root"))
        worktree_path_raw = str(args.get("worktree_path", "")).strip()
        worktree_path = Path(worktree_path_raw).expanduser().resolve() if worktree_path_raw else _default_worktree_path(repo_root, agent_id)
        allow_dirty_root = bool(args.get("allow_dirty_root", False))
        try:
            reservation = _prepare_worktree(
                agent_id,
                repo_root=repo_root,
                branch=branch,
                base_branch=base_branch,
                worktree_path=worktree_path,
                allow_dirty_root=allow_dirty_root,
                ttl_seconds=ttl,
            )
        except RuntimeError as exc:
            return {"error": str(exc)}

        _write_json(_worktree_record_path(branch), reservation)
        worktree = _worktree_metadata_from_runtime(repo_root, worktree_path, branch, base_branch)
        _save_agent_state(
            agent_id,
            status=args.get("status", state.get("status", "planning")),
            intent=args.get("intent", state.get("intent", "")),
            message=args.get("message", state.get("message", "")),
            claimed_files=state.get("claimed_files", []),
            metadata=state.get("metadata", {}),
            worktree=worktree,
            ttl_seconds=ttl,
        )
        _update_self_claim_worktree(agent_id, worktree)
        _record_event(agent_id, "prepare-worktree", reservation)
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Prepared worktree for {agent_id}: branch={branch} base={base_branch} "
                        f"path={worktree_path}"
                    ),
                }
            ]
        }

    if tool == "scion_remove_worktree":
        state = _load_agent_state(agent_id)
        worktree = state.get("worktree", {})
        branch = _normalize_path(str(args.get("branch", "")).strip() or str(worktree.get("branch", "")).strip())
        if not branch:
            return {"error": "Missing branch for worktree removal."}
        worktree_path_raw = str(args.get("worktree_path", "")).strip() or str(worktree.get("path", "")).strip()
        if not worktree_path_raw:
            return {"error": "Missing worktree_path for worktree removal."}
        repo_root = _repo_root(args.get("repo_root"))
        worktree_path = Path(worktree_path_raw).expanduser().resolve()
        try:
            _remove_worktree(
                agent_id,
                repo_root=repo_root,
                branch=branch,
                worktree_path=worktree_path,
                force=bool(args.get("force", True)),
            )
        except RuntimeError as exc:
            return {"error": str(exc)}

        _save_agent_state(
            agent_id,
            status=args.get("status", state.get("status", "idle")),
            intent=state.get("intent", ""),
            message=args.get("message", state.get("message", "")),
            claimed_files=state.get("claimed_files", []),
            metadata=state.get("metadata", {}),
            worktree={},
            ttl_seconds=args.get("ttl_seconds"),
        )
        _update_self_claim_worktree(agent_id, {})
        _record_event(agent_id, "remove-worktree", {"branch": branch, "path": str(worktree_path)})
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Removed worktree for {agent_id}: branch={branch} path={worktree_path}",
                }
            ]
        }

    if tool == "scion_claim_files":
        files = _normalize_paths(args.get("files"))
        if not files:
            return {"error": "Missing 'files' argument."}
        conflicts = _conflicts_for_files(agent_id, files)
        claim_mode = str(args.get("mode", "")).strip().lower() or "advisory"
        if bool(args.get("strict", False)):
            claim_mode = "exclusive"
        if claim_mode not in {"advisory", "exclusive", "takeover"}:
            return {"error": "Invalid claim mode. Use advisory, exclusive, or takeover."}
        takeover_from = str(args.get("takeover_from", "")).strip()
        if claim_mode == "exclusive":
            authoritative_conflicts = _claim_conflicts_for_files(agent_id, files)
            if authoritative_conflicts:
                return {"error": f"Conflicting Scion claims detected: {_claim_conflict_text(authoritative_conflicts)}"}

        state = _load_agent_state(agent_id)
        current = set(_normalize_paths(state.get("claimed_files", [])))
        current.update(files)
        intent = args.get("intent", state.get("intent", ""))
        ttl_seconds = args.get("ttl_seconds")
        message = args.get("message", state.get("message", ""))
        metadata = args.get("metadata", state.get("metadata", {}))
        worktree = state.get("worktree", {})
        authoritative_handoffs: list[dict[str, Any]] = []
        ttl = max(30, ttl_seconds or _default_ttl_seconds())
        try:
            if claim_mode in {"exclusive", "takeover"}:
                authoritative_handoffs = _authoritative_claim_files(
                    agent_id,
                    files,
                    claim_mode=claim_mode,
                    takeover_from=takeover_from,
                    intent=intent,
                    message=message,
                    metadata=metadata,
                    worktree=worktree,
                    ttl_seconds=ttl,
                )
        except RuntimeError as exc:
            return {"error": str(exc)}

        _save_agent_state(
            agent_id,
            status="claiming",
            intent=intent,
            message=message,
            claimed_files=sorted(current),
            metadata=metadata,
            worktree=worktree,
            ttl_seconds=ttl_seconds,
        )
        event_payload: dict[str, Any] = {"files": files, "intent": intent, "mode": claim_mode}
        if takeover_from:
            event_payload["takeover_from"] = takeover_from
        _record_event(agent_id, "claim", event_payload)
        text = f"Claimed {len(files)} file(s) for {agent_id}: {', '.join(files)}"
        if claim_mode != "advisory":
            text += f"\nClaim mode: {claim_mode}"
        if conflicts:
            conflict_text = "; ".join(f"{item['agent_id']} -> {_format_conflict_pairs(item['pairs'])}" for item in conflicts)
            text += f"\nWarning: overlapping claims with {conflict_text}"
        if authoritative_handoffs:
            handoff_text = ", ".join(sorted({str(record.get("agent_id", "")) for record in authoritative_handoffs}))
            text += f"\nTook over exact claims from: {handoff_text}"
        return {"content": [{"type": "text", "text": text}]}

    if tool == "scion_release_claims":
        files = _normalize_paths(args.get("files", []))
        state = _load_agent_state(agent_id)
        current = _normalize_paths(state.get("claimed_files", []))
        current_set = set(current)
        if files:
            requested = set(files)
            released = [item for item in current if item in requested]
            remaining = [item for item in current if item not in requested]
        else:
            released = current
            remaining = []
        status = "idle" if not remaining else state.get("status", "active")
        _save_agent_state(
            agent_id,
            status=status,
            intent=state.get("intent", ""),
            message=args.get("note", state.get("message", "")),
            claimed_files=remaining,
            metadata=state.get("metadata", {}),
            worktree=state.get("worktree", {}),
            ttl_seconds=args.get("ttl_seconds"),
        )
        release_targets = set(released)
        for record in _self_claim_records(agent_id):
            claimed_path = _normalize_path(str(record.get("claimed_path", "")))
            if not claimed_path:
                continue
            if files and claimed_path not in release_targets:
                continue
            claim_path = record.get("_path")
            if isinstance(claim_path, Path):
                claim_path.unlink(missing_ok=True)
        _record_event(agent_id, "release", {"released_files": released, "remaining_files": remaining})
        text = f"Released {len(released)} claim(s) for {agent_id}."
        if files and len(released) != len(files):
            missing = [item for item in files if item not in current_set]
            if missing:
                text += f"\nNot currently claimed: {', '.join(missing)}"
        return {"content": [{"type": "text", "text": text}]}

    if tool == "scion_heartbeat":
        state = _load_agent_state(agent_id)
        ttl_seconds = args.get("ttl_seconds")
        saved = _save_agent_state(
            agent_id,
            status=args.get("status", state.get("status", "active")),
            intent=args.get("intent", state.get("intent", "")),
            message=args.get("message", state.get("message", "")),
            claimed_files=state.get("claimed_files", []),
            metadata=state.get("metadata", {}),
            worktree=state.get("worktree", {}),
            ttl_seconds=ttl_seconds,
        )
        try:
            _upsert_worktree_record(
                agent_id,
                _repo_root(args.get("repo_root")),
                state.get("worktree", {}),
                max(30, int(ttl_seconds or _default_ttl_seconds())),
            )
        except RuntimeError:
            pass
        for record in _self_claim_records(agent_id):
            claimed_path = _normalize_path(str(record.get("claimed_path", "")))
            if not claimed_path:
                continue
            claim_path = record.get("_path")
            if not isinstance(claim_path, Path):
                continue
            refreshed = _claim_payload(
                agent_id,
                claimed_path,
                claim_mode=str(record.get("claim_mode", "exclusive") or "exclusive"),
                intent=saved.get("intent", ""),
                message=saved.get("message", ""),
                metadata=state.get("metadata", {}),
                worktree=state.get("worktree", {}),
                ttl_seconds=max(30, ttl_seconds or _default_ttl_seconds()),
            )
            _write_json(claim_path, refreshed)
        _record_event(agent_id, "heartbeat", {"status": saved.get("status", "unknown")})
        return {"content": [{"type": "text", "text": f"Heartbeat recorded for {agent_id}."}]}

    if tool == "scion_inspect_state":
        include_events = bool(args.get("include_events", True))
        event_limit = int(args.get("event_limit", 10))
        return {"content": [{"type": "text", "text": _inspect_state_text(include_events=include_events, event_limit=event_limit)}]}

    if tool == "scion_prune_stale":
        result = _prune_stale(event_retention_seconds=int(args.get("event_retention_seconds", 86400)))
        text = (
            f"Pruned {len(result['stale_agents_removed'])} stale agent state file(s) "
            f"{len(result['claims_removed'])} stale claim file(s) "
            f"{len(result['worktrees_removed'])} stale worktree record(s) "
            f"and {len(result['events_removed'])} expired event(s)."
        )
        return {"content": [{"type": "text", "text": text}]}

    if tool == "scion_query_peers":
        query = args.get("query")
        if not query:
            return {"error": "Missing 'query' argument."}
        candidate_files = _normalize_paths(args.get("candidate_files", args.get("files", [])))
        peers = _active_peers(agent_id)
        text = _summary_for_query(peers, candidate_files)
        print(f"[SCION QUERY by {agent_id}] {query}", file=sys.stderr)
        return {"content": [{"type": "text", "text": text}]}

    return {"error": f"Unknown tool: {tool}"}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--describe":
        print(
            json.dumps(
                {
                    "tools": [
                        {
                            "name": "scion_broadcast",
                            "description": "Records a broadcast message and optional claimed files into file-backed shared Scion state.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "message": {"type": "string", "description": "The message or finding to broadcast."},
                                    "files": {"type": "array", "items": {"type": "string"}, "description": "Optional list of repo-relative files or areas associated with the broadcast."},
                                    "intent": {"type": "string", "description": "Optional work intent summary."},
                                    "status": {"type": "string", "description": "Agent status label such as active or planning."},
                                    "ttl_seconds": {"type": "integer", "description": "Optional TTL for this agent state."},
                                    "metadata": {"type": "object", "description": "Optional arbitrary metadata."},
                                },
                                "required": ["message"],
                            },
                        },
                        {
                            "name": "scion_claim_files",
                            "description": "Claims one or more files or repo areas in shared Scion state to reduce edit conflicts or acquire authoritative locks.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "files": {"type": "array", "items": {"type": "string"}, "description": "Repo-relative files or areas to claim."},
                                    "intent": {"type": "string", "description": "Optional short intent for the claim."},
                                    "message": {"type": "string", "description": "Optional note to attach to the agent state."},
                                    "mode": {"type": "string", "description": "Claim mode: advisory, exclusive, or takeover."},
                                    "strict": {"type": "boolean", "description": "Legacy alias for mode=exclusive."},
                                    "takeover_from": {"type": "string", "description": "Required when mode=takeover. Exact claim owner to take over from."},
                                    "ttl_seconds": {"type": "integer", "description": "Optional TTL for this agent state."},
                                    "metadata": {"type": "object", "description": "Optional arbitrary metadata."},
                                },
                                "required": ["files"],
                            },
                        },
                        {
                            "name": "scion_register_worktree",
                            "description": "Registers the current agent's assigned worktree and branch metadata in shared Scion state.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "worktree_path": {"type": "string", "description": "Absolute or repo-relative worktree path."},
                                    "path": {"type": "string", "description": "Legacy alias for worktree_path."},
                                    "repo_root": {"type": "string", "description": "Optional git repository root used for reservation context."},
                                    "branch": {"type": "string", "description": "Current branch for this worktree."},
                                    "base_branch": {"type": "string", "description": "Base branch for the worktree."},
                                    "head_sha": {"type": "string", "description": "Optional current HEAD sha."},
                                    "clean": {"type": "boolean", "description": "Whether the worktree is currently clean."},
                                    "status": {"type": "string", "description": "Optional updated agent status label."},
                                    "intent": {"type": "string", "description": "Optional intent to attach to the registration."},
                                    "message": {"type": "string", "description": "Optional message to attach to the registration."},
                                    "ttl_seconds": {"type": "integer", "description": "Optional TTL for this agent state."},
                                },
                                "required": ["worktree_path"],
                            },
                        },
                        {
                            "name": "scion_prepare_worktree",
                            "description": "Creates and reserves a git worktree for the current agent, then records its branch/path metadata in Scion state.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "repo_root": {"type": "string", "description": "Optional git repository root. Defaults to ANGELLA_ROOT/current working directory."},
                                    "worktree_path": {"type": "string", "description": "Optional target worktree path. Defaults under /tmp or SCION_WORKTREE_ROOT."},
                                    "branch": {"type": "string", "description": "Optional branch name. Defaults to codex/scion-<agent-id>."},
                                    "base_branch": {"type": "string", "description": "Base branch to branch from. Defaults to main."},
                                    "allow_dirty_root": {"type": "boolean", "description": "Allow preparing from a dirty repository root. Defaults to false."},
                                    "status": {"type": "string", "description": "Optional updated agent status label."},
                                    "intent": {"type": "string", "description": "Optional intent to attach to the prepared worktree."},
                                    "message": {"type": "string", "description": "Optional message to attach to the prepared worktree."},
                                    "ttl_seconds": {"type": "integer", "description": "Optional TTL for the agent/worktree reservation."},
                                },
                            },
                        },
                        {
                            "name": "scion_remove_worktree",
                            "description": "Removes the current agent's git worktree reservation and clears registered worktree metadata.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "repo_root": {"type": "string", "description": "Optional git repository root. Defaults to ANGELLA_ROOT/current working directory."},
                                    "worktree_path": {"type": "string", "description": "Optional worktree path. Defaults to the registered worktree path."},
                                    "branch": {"type": "string", "description": "Optional branch to remove. Defaults to the registered worktree branch."},
                                    "force": {"type": "boolean", "description": "Whether to force worktree removal. Defaults to true."},
                                    "status": {"type": "string", "description": "Optional updated agent status label after removal."},
                                    "message": {"type": "string", "description": "Optional message to attach after removal."},
                                    "ttl_seconds": {"type": "integer", "description": "Optional TTL for the updated agent state."},
                                },
                            },
                        },
                        {
                            "name": "scion_release_claims",
                            "description": "Releases all or a subset of the current agent's claimed files from shared Scion state.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "files": {"type": "array", "items": {"type": "string"}, "description": "Optional subset of files to release. Omit to release all claims."},
                                    "note": {"type": "string", "description": "Optional note to leave when releasing claims."},
                                    "ttl_seconds": {"type": "integer", "description": "Optional TTL for the updated agent state."},
                                },
                            },
                        },
                        {
                            "name": "scion_heartbeat",
                            "description": "Refreshes the current agent's TTL and status without changing its claimed files.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string", "description": "Optional updated status label."},
                                    "intent": {"type": "string", "description": "Optional updated intent summary."},
                                    "message": {"type": "string", "description": "Optional updated status message."},
                                    "ttl_seconds": {"type": "integer", "description": "Optional TTL for the refreshed state."},
                                },
                            },
                        },
                        {
                            "name": "scion_inspect_state",
                            "description": "Inspects the current file-backed Scion shared state and recent events.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "include_events": {"type": "boolean", "description": "Whether to include recent events."},
                                    "event_limit": {"type": "integer", "description": "Maximum number of recent events to list."},
                                },
                            },
                        },
                        {
                            "name": "scion_prune_stale",
                            "description": "Removes expired agent state files and old event files from the shared Scion directory.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "event_retention_seconds": {"type": "integer", "description": "Retention window for event files."},
                                },
                            },
                        },
                        {
                            "name": "scion_query_peers",
                            "description": "Queries file-backed shared Scion state to discover active peers and overlapping file claims.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "The question to ask about peer agent activity."},
                                    "candidate_files": {"type": "array", "items": {"type": "string"}, "description": "Optional repo-relative files or areas to compare against peer claims."},
                                    "files": {"type": "array", "items": {"type": "string"}, "description": "Legacy alias for candidate_files."},
                                },
                                "required": ["query"],
                            },
                        },
                    ]
                }
            )
        )
        sys.exit(0)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            res = handle_request(req)
            print(json.dumps(res), flush=True)
        except Exception as exc:  # pragma: no cover - stdio guard
            print(json.dumps({"error": str(exc)}), flush=True)
