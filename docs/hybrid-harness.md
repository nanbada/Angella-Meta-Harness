# Hybrid Harness

Angella harness는 `lead + planner + worker` 3역할을 고정 모델이 아니라 catalog/selector 기반으로 결정합니다.

## Roles

- lead: 전체 목표 정렬과 최종 판단
- planner: 계획 생성과 decomposition
- worker: 실제 local execution/coding/reasoning

## Default pattern

- lead: `best_reasoning_frontier`
- planner: `best_reasoning_frontier`
- worker: `best_local_coder`

즉 기본 구조는 “frontier online lead/planner + local MLX worker”입니다.

## Worker profiles

- `default`: frontier lead/planner + qwen local coder
- `frontier_low_cost`: 비용 절충형 frontier lead/planner + local coder
- `local_reasoning`: frontier lead/planner + gemma reasoning worker
- `low_latency_apfel`: frontier lead/planner + apfel low-latency worker
- `preview_nvfp4`: frontier lead/planner + NVFP4 preview worker

## Selection model

모델은 이름으로 직접 박히지 않고 selector policy로 선택됩니다.

- `best_reasoning_frontier`
- `best_reasoning_frontier_low_cost`
- `best_local_coder`
- `best_local_low_latency`
- `best_local_reasoning`

새로운 더 강한 lead/planner 모델이 생기면 catalog score만 갱신하면 되고, installer는 같은 profile id를 유지한 채 새 모델을 자동 선택할 수 있습니다.
