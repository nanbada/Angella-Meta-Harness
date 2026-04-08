# Scion Operations

Angella의 Phase 7 Scion 기능은 실서비스 hub가 아니라 **file-backed coordination MVP**입니다.
기본 shared state 경로는 `.scion/shared`이며, 필요하면 `SCION_SHARED_DIR`로 다른 공유 디렉터리를 지정할 수 있습니다.

## Shared State Layout

```text
.scion/shared/
├── agents/
│   └── <agent-id>.json
├── claims/
│   └── <repo-area>.json
└── events/
    └── <timestamp>-<agent-id>-<kind>.json
```

- `agents/`: active agent state, status, intent, claimed files, TTL
- `claims/`: authoritative exclusive claim records and explicit takeover handoff state
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
2. `scion_prepare_worktree`
   - clean root repo 기준으로 dedicated git worktree를 만들고 branch/path를 예약
   - 기본 branch는 `codex/scion-<agent-id>`, 기본 path는 `/tmp/angella-scion-worktrees/<repo>/<agent-id>`
3. `scion_query_peers`
   - 수정 전 candidate file overlap 확인
4. `scion_claim_files`
   - 실제 수정 범위를 shared state에 claim
   - `mode=advisory`는 기존 MVP처럼 warning 기반 coordination
   - `strict=true` 또는 `mode=exclusive`는 authoritative claim file을 만들고 겹치면 실패
   - `mode=takeover` + `takeover_from=<agent-id>`는 exact handoff 또는 broad parent claim으로부터 nested path handoff를 수행
5. `scion_register_worktree`
   - 현재 agent가 작업 중인 worktree path / branch / clean 상태를 등록
   - `scion_inspect_state`와 peer query에 worktree metadata를 노출
6. `scion_heartbeat`
   - 긴 작업 중 TTL 연장 및 상태 갱신
7. `scion_broadcast`
   - 작업 시작/중간 상태/발견 사항 전파
8. `scion_release_claims`
   - 작업 종료 시 claim 해제
9. `scion_remove_worktree`
   - 작업 종료 후 reserved git worktree를 제거하고 metadata를 비움
10. `scion_inspect_state`
   - active peer와 recent event 관측

## Example

```json
{"type":"call_tool","name":"scion_prune_stale","arguments":{"event_retention_seconds":3600}}
{"type":"call_tool","name":"scion_prepare_worktree","arguments":{"repo_root":"/Users/example/Angella","worktree_path":"/tmp/angella-scion-alpha","branch":"codex/scion-alpha","base_branch":"main"}}
{"type":"call_tool","name":"scion_query_peers","arguments":{"query":"Can I edit recipes/autoresearch-loop.yaml?","candidate_files":["recipes/autoresearch-loop.yaml"]}}
{"type":"call_tool","name":"scion_claim_files","arguments":{"files":["recipes/autoresearch-loop.yaml"],"intent":"Phase 7 coordination hardening","mode":"exclusive"}}
{"type":"call_tool","name":"scion_heartbeat","arguments":{"status":"active","message":"updating recipe coordination guidance"}}
{"type":"call_tool","name":"scion_release_claims","arguments":{"files":["recipes/autoresearch-loop.yaml"],"note":"done"}}
{"type":"call_tool","name":"scion_remove_worktree","arguments":{"repo_root":"/Users/example/Angella","branch":"codex/scion-alpha","worktree_path":"/tmp/angella-scion-alpha"}}
```

## Takeover Handoff

- `mode=takeover`는 같은 claim path에 대한 exact handoff를 지원합니다.
- broad parent claim과 nested child path 조합이면 parent claim record에 `exclusions`를 추가하는 방식으로 safe decomposition을 수행합니다.
- nested takeover는 `takeover_from=<agent-id>`가 broad parent owner와 일치할 때만 허용됩니다.
- nested child claim이 release 또는 stale prune으로 사라지면 parent claim의 exclusion은 자동으로 복구됩니다.
- broader path가 더 좁은 child claim을 덮어쓰는 방향의 widening takeover는 허용하지 않습니다.

## Current Limits

- advisory mode는 여전히 hard locking이 아니라 file-backed coordination입니다.
- exclusive mode는 authoritative claim file을 쓰고, `scion_prepare_worktree`를 함께 쓰면 branch/path ownership까지 예약합니다.
- TTL 기반이므로 heartbeat 없이 장시간 멈추면 stale state로 간주될 수 있습니다.
- Scion은 이제 git worktree 생성/제거 helper까지 제공하지만, 더 복잡한 branch topology 결정과 multi-stage scheduling은 아직 외부 orchestration이 담당합니다.
