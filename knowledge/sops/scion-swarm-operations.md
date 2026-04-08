# SOP: Scion Swarm Operations

Scion 기반 병렬 작업 시 Angella 에이전트는 아래 순서를 따릅니다.

## 1. Session Start

- `scion_prune_stale`로 stale state를 먼저 정리합니다.
- `scion_inspect_state`로 현재 active peer와 recent event를 확인합니다.

## 2. Before Editing

- 수정 후보 파일이 정해지면 `scion_query_peers`로 overlap을 확인합니다.
- 충돌을 허용하지 않는 작업이면 `scion_claim_files`를 `strict=true`로 호출합니다.

## 3. During Work

- 긴 작업은 `scion_heartbeat`로 TTL을 연장합니다.
- 중요한 발견이나 계획 변경은 `scion_broadcast`로 남깁니다.

## 4. Finish

- 수정 범위가 끝나면 `scion_release_claims`로 claim을 해제합니다.
- 남길 가치가 있는 coordination lesson은 LLM-Wiki에 저장합니다.

## 5. Non-Goals

- Scion state를 git tracked artifact로 남기지 않습니다.
- peer conflict를 사람 판단 없이 자동 merge하지 않습니다.
