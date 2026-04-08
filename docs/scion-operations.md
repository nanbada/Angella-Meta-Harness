# Scion Operations

Angella의 Phase 7 Scion 기능은 실서비스 hub가 아니라 **file-backed coordination MVP**입니다.
기본 shared state 경로는 `.scion/shared`이며, 필요하면 `SCION_SHARED_DIR`로 다른 공유 디렉터리를 지정할 수 있습니다.

## Shared State Layout

```text
.scion/shared/
├── agents/
│   └── <agent-id>.json
└── events/
    └── <timestamp>-<agent-id>-<kind>.json
```

- `agents/`: active agent state, status, intent, claimed files, TTL
- `events/`: broadcast, claim, release, heartbeat 같은 recent event log

## Environment Variables

- `SCION_SHARED_DIR`
  - shared coordination state root override
- `SCION_AGENT_ID`
  - 현재 agent identity override
- `SCION_TTL_SECONDS`
  - agent state TTL

## Tool Workflow

1. `scion_prune_stale`
   - 세션 시작 시 stale state와 오래된 이벤트를 먼저 정리
2. `scion_query_peers`
   - 수정 전 candidate file overlap 확인
3. `scion_claim_files`
   - 실제 수정 범위를 shared state에 claim
   - `strict=true`면 겹치는 claim이 있을 때 바로 실패
4. `scion_heartbeat`
   - 긴 작업 중 TTL 연장 및 상태 갱신
5. `scion_broadcast`
   - 작업 시작/중간 상태/발견 사항 전파
6. `scion_release_claims`
   - 작업 종료 시 claim 해제
7. `scion_inspect_state`
   - active peer와 recent event 관측

## Example

```json
{"type":"call_tool","name":"scion_prune_stale","arguments":{"event_retention_seconds":3600}}
{"type":"call_tool","name":"scion_query_peers","arguments":{"query":"Can I edit recipes/autoresearch-loop.yaml?","candidate_files":["recipes/autoresearch-loop.yaml"]}}
{"type":"call_tool","name":"scion_claim_files","arguments":{"files":["recipes/autoresearch-loop.yaml"],"intent":"Phase 7 coordination hardening","strict":true}}
{"type":"call_tool","name":"scion_heartbeat","arguments":{"status":"active","message":"updating recipe coordination guidance"}}
{"type":"call_tool","name":"scion_release_claims","arguments":{"files":["recipes/autoresearch-loop.yaml"],"note":"done"}}
```

## Current Limits

- hard locking이 아니라 file-backed coordination입니다.
- TTL 기반이므로 heartbeat 없이 장시간 멈추면 stale state로 간주될 수 있습니다.
- worktree 생성/프로세스 orchestration 자체는 아직 외부가 담당합니다.
