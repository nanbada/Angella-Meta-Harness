# SOP: Scion Branch Topology & Multi-Agent Scheduling

이 문서는 Scion file-backed coordination 하에서 여러 Angella 에이전트가 협업할 때 준수해야 하는 브랜치 구조와 작업 스케줄링 정책을 정의합니다.

## 1. Branch Topology: Hub-and-Spoke

모든 Scion 에이전트는 **Hub-and-Spoke** 모델을 따릅니다.

- **Hub (main)**: 모든 에이전트의 베이스가 되는 브랜치입니다.
- **Spoke (codex/scion-<agent-id>)**: 각 에이전트가 `scion_prepare_worktree`를 통해 생성하는 독립적인 작업 브랜치입니다.
- **Sub-Spoke**: 대규모 작업을 다시 쪼개는 경우, 상위 에이전트의 브랜치를 베이스로 하는 nested 브랜치를 생성할 수 있습니다.

### 브랜치 생명주기
1. `scion_prepare_worktree`로 `main`에서 `codex/scion-<agent-id>`를 분기합니다.
2. 작업 완료 후 `main`으로 직접 머지하지 않고, `export_meta_loop_change` 등을 통해 Draft PR을 생성합니다.
3. PR이 머지되거나 작업이 취소되면 `scion_remove_worktree`로 로컬 예약과 브랜치를 정리합니다.

## 2. Multi-Agent Scheduling Policy

에이전트 간의 작업 우선순위와 충돌 해결을 위한 스케줄링 규칙입니다.

### Priority Tiers (작업 우선순위)
- **Tier 1: Emergency Fixes**: 빌드 실패, 중대 회귀(Regression) 복구. (Exclusive Claim 필수)
- **Tier 2: Directives**: 사용자로부터 직접 명시된 작업.
- **Tier 3: Autoresearch**: 자율적인 최적화 및 리서치 루프. (Advisory Claim 권장)

### Scheduling Rules
1. **No Overlap without Takeover**: 동일 파일에 대해 두 개 이상의 `exclusive` claim이 존재할 수 없습니다. 이미 점유된 파일을 수정해야 하는 경우, 기존 점유자에게 `scion_query_peers`로 의도를 묻고 `takeover` 협상을 수행해야 합니다.
2. **Fair Heartbeat**: 모든 active 에이전트는 최소 5분마다 `scion_heartbeat`를 갱신해야 합니다. Heartbeat가 끊긴 에이전트의 claim은 `scion_prune_stale`에 의해 회수될 수 있습니다.
3. **Decomposition First**: 큰 작업을 수행하는 에이전트는 세부 작업을 다른 에이전트에게 위임할 때 `mode=takeover`를 통해 특정 파일/디렉터리의 소유권을 명확히 넘겨야 합니다.

## 3. Conflict Resolution

- **Soft Conflict**: `advisory` 모드에서 감지된 겹침. 에이전트가 스스로 `scion_broadcast`를 통해 진행 여부를 결정하거나 사용자에게 묻습니다.
- **Hard Conflict**: `exclusive` 모드에서 점유 실패. 점유한 에이전트의 작업 완료를 기다리거나, `Tier`가 더 높은 경우 `takeover`를 시도합니다.
- **Stale Claim**: Heartbeat가 끊긴 claim. 후속 에이전트는 `scion_prune_stale` 후 해당 영역을 점유할 권리를 가집니다.
