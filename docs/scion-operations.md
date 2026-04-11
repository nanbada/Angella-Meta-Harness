# Scion Operations (v3.1 Optimized)

Angella의 Scion 조정 레이어는 기존의 File-backed 방식에서 **SQLite Backend**로 전면 전환되어 원자성(Atomicity)과 고성능을 제공합니다.

## Shared State (SQLite Backbone)

기본 DB 경로는 `.scion/shared/scion.db`이며, `SCION_BACKEND=sqlite` 환경 변수를 통해 활성화됩니다.

### Database Schema
- **`agents`**: 에이전트 상태, 의도, 현재 점유 중인 파일 목록, TTL 정보.
- **`claims`**: 특정 파일 경로에 대한 배타적/공유 점유 권한 및 `exclusions`.
- **`worktrees`**: Git Worktree 예약 및 브랜치 소유권 정보.
- **`events`**: Broadcast, Heartbeat 등 실시간 이벤트 스트림.

## Key Advantages
1. **Atomic Transactions**: 다중 에이전트가 동시에 동일 파일을 점유하려 할 때 SQLite의 Row-level 락을 통해 충돌을 완벽히 방지합니다.
2. **High Performance**: `rglob`으로 수백 개의 JSON을 읽는 대신 인덱싱된 SQL 쿼리로 즉시 상태를 조회합니다.
3. **Consistency**: 파일 시스템 지연으로 인한 상태 불일치(Drift) 문제를 해결합니다.

## Tool Workflow
(기존 툴 체인과 동일하되 백엔드만 투명하게 교체됨)
1. `scion_prune_stale`: 만료된 DB 레코드 정리.
2. `scion_claim_files`: `exclusive` 모드 시 DB에 배타적 레코드 생성.
3. `scion_inspect_state`: DB 뷰를 통해 스웜 전체 현황 가시화.

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
- 상세한 브랜치 구조 및 스케줄링 정책은 **[`knowledge/sops/scion-topology-and-scheduling.md`](../knowledge/sops/scion-topology-and-scheduling.md)**를 참조하세요.
