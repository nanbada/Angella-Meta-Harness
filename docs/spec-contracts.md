# Angella Technical Specifications

이 문서는 Angella 하네스에서 동작하는 모든 에이전트가 준수해야 하는 기술적 규격과 계약을 정의합니다.

## 1. Intent Contract (의도 계약)
루프 시작 전(Phase 0), 에이전트는 아래 항목을 포함하는 구조화된 의도를 반드시 수립해야 합니다.
- `ideal_state_8_12_words`: 목표 상태 요약 (8~12단어)
- `metric_key`: 최적화 대상 메트릭 (`build_time`, `bundle_size` 등)
- `intent_summary`: 상세 개선 의도
- `metric_reason`: 왜 이 메트릭을 선택했는지
- `non_goals`: 작업 시 보존해야 할 영역 (Side-effect 방지)
- `success_threshold`: 개선 인정 기준 (%)
- `binary_acceptance_checks`: 성공/실패를 가르는 절대적 체크리스트
- `operator_constraints`: 운영상 제약 사항
- `first_hypotheses`: 초기 가설 3~5개

## 2. Benchmark Contract (측정 계약)
모든 벤치마크 도구(MCP)는 아래 필드를 포함한 표준 JSON을 반환해야 합니다.
- `success`: 측정 성공 여부 (bool)
- `metric_key`: 측정된 메트릭 이름
- `metric_value`: 측정 수치 (float)
- `duration_seconds`: 실행 시간
- `exit_code`: 프로세스 종료 코드
- `stdout_tail` / `stderr_tail`: 마지막 로그 (문맥 파악용)
- `aux_metrics`: 부가 메트릭 (메모리 사용량 등)

## 3. Git 운영 규칙 (Git Protocols)
- **Isolation**: 사용자의 현재 브랜치를 직접 수정하지 않으며, 항상 `angella/run-<timestamp>` 브랜치에서 작업합니다.
- **Preflight**: Dirty Worktree(미커밋 변경사항 존재) 상태에서는 루프를 시작하지 않습니다.
- **Ratchet**: `compare_metrics` 결과가 개선일 때만 `keep` 하고, 그 외에는 즉시 `git revert HEAD --no-edit`를 수행합니다.

## 4. Scion Topology Contract (군집 조정 계약)
다중 에이전트 환경에서 작업 충돌을 방지하기 위해 아래 규약을 준수합니다.
- **Hub-and-Spoke**: 모든 작업 브랜치는 `main`에서 분기하며, 작업 완료 시 PR을 통해 통합됩니다.
- **Tiered Priority**: 작업 성격에 따라 우선순위(`Emergency` > `Directive` > `Autoresearch`)를 부여하고 경합 시 상위 티어가 우선권을 가집니다.
- **Fair Heartbeat**: 모든 에이전트는 5분 이내 주기로 상태를 갱신해야 하며, 유효하지 않은 Claim은 `scion_prune_stale` 대상이 됩니다.

## 5. Transparency (투명성)
- 모든 기록은 `run_id` 단위로 `$ANGELLA_ROOT/logs/Goose Logs/`에 저장됩니다.
- **Session Log**: 각 iteration의 가설, 시도, 측정값, 판정 근거 기록.
- **Final Report**: 전체 루프의 성공 여부, 최종 메트릭, 누적 Git Diff 요약.
- **Telemetry**: `control_plane` 모듈을 통해 모든 이벤트가 JSONL 형태로 기록됩니다.
