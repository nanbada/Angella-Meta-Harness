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


def _ensure_layout() -> None:
    _agents_dir().mkdir(parents=True, exist_ok=True)
    _events_dir().mkdir(parents=True, exist_ok=True)


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


def _overlap(candidate_files: list[str], peer_files: list[str]) -> list[str]:
    candidate = set(_normalize_paths(candidate_files))
    peer = set(_normalize_paths(peer_files))
    return sorted(candidate & peer)


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
        peer_lines.append(peer_line)

        overlap = _overlap(candidate_files, claimed)
        if overlap:
            overlaps.append(f"{peer['agent_id']} -> {', '.join(overlap)}")

    if overlaps:
        return "Conflicts detected with active peers:\n" + "\n".join(overlaps) + "\n\nActive peers:\n" + "\n".join(peer_lines)
    return "No direct conflicts detected.\n\nActive peers:\n" + "\n".join(peer_lines)


def _conflicts_for_files(self_id: str, candidate_files: list[str]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for peer in _active_peers(self_id):
        overlap = _overlap(candidate_files, peer.get("claimed_files", []))
        if overlap:
            conflicts.append(
                {
                    "agent_id": peer["agent_id"],
                    "files": overlap,
                    "status": peer.get("status", "unknown"),
                    "intent": peer.get("intent", ""),
                    "message": peer.get("message", ""),
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

    return {
        "stale_agents_removed": stale_agents,
        "events_removed": pruned_events,
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
            ttl_seconds=ttl_seconds,
        )
        event_path = _record_event(agent_id, "broadcast", {"message": message, "files": state.get("claimed_files", [])})
        text = (
            f"Broadcast recorded for {agent_id} in {_shared_dir()} "
            f"(claims={len(state.get('claimed_files', []))}, event={event_path.name})."
        )
        print(f"[SCION BROADCAST from {agent_id}] {message}", file=sys.stderr)
        return {"content": [{"type": "text", "text": text}]}

    if tool == "scion_claim_files":
        files = _normalize_paths(args.get("files"))
        if not files:
            return {"error": "Missing 'files' argument."}
        conflicts = _conflicts_for_files(agent_id, files)
        strict = bool(args.get("strict", False))
        if strict and conflicts:
            conflict_text = "; ".join(f"{item['agent_id']} -> {', '.join(item['files'])}" for item in conflicts)
            return {"error": f"Conflicting Scion claims detected: {conflict_text}"}
        state = _load_agent_state(agent_id)
        current = set(_normalize_paths(state.get("claimed_files", [])))
        current.update(files)
        intent = args.get("intent", state.get("intent", ""))
        ttl_seconds = args.get("ttl_seconds")
        saved = _save_agent_state(
            agent_id,
            status="claiming",
            intent=intent,
            message=args.get("message", state.get("message", "")),
            claimed_files=sorted(current),
            metadata=args.get("metadata", state.get("metadata", {})),
            ttl_seconds=ttl_seconds,
        )
        _record_event(agent_id, "claim", {"files": files, "intent": intent})
        text = f"Claimed {len(files)} file(s) for {agent_id}: {', '.join(files)}"
        if conflicts:
            conflict_text = "; ".join(f"{item['agent_id']} -> {', '.join(item['files'])}" for item in conflicts)
            text += f"\nWarning: overlapping claims with {conflict_text}"
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
            ttl_seconds=args.get("ttl_seconds"),
        )
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
            ttl_seconds=ttl_seconds,
        )
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
                            "description": "Claims one or more files or repo areas in shared Scion state to reduce edit conflicts.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "files": {"type": "array", "items": {"type": "string"}, "description": "Repo-relative files or areas to claim."},
                                    "intent": {"type": "string", "description": "Optional short intent for the claim."},
                                    "message": {"type": "string", "description": "Optional note to attach to the agent state."},
                                    "ttl_seconds": {"type": "integer", "description": "Optional TTL for this agent state."},
                                    "metadata": {"type": "object", "description": "Optional arbitrary metadata."},
                                },
                                "required": ["files"],
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
