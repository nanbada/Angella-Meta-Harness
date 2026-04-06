# Frontier-First Harness

Angella harness는 `lead + planner + worker` 3역할을 catalog/selector 기반으로 결정합니다.

기본 원칙은 이제 `frontier-first personal agent harness` 입니다.

## Roles

- lead: 최상위 목표 정렬과 최종 판단
- planner: 계획 생성, decomposition, verification framing
- worker: 실제 coding/reasoning/execution

## Default Pattern

- lead: 최신 frontier reasoning model
- planner: 최신 frontier reasoning model
- worker: 최신 frontier worker model

즉 기본 구조는 더 이상 `frontier + local worker`가 아니라 `frontier + frontier + frontier` 입니다.

local LLM은 기본 경로가 아니라 아래 2급 계층으로만 사용합니다.

- fallback: privacy, token, network, connectivity 제약 시 대체 worker
- augment: prefilter, local review, compact retrieval, private knowledge assist
- cache: 반복 검색/압축/로컬 knowledge 작업용 보조 계층

## Canonical Profiles

- `frontier_default`
  - 기본값
  - frontier lead/planner + cost-guarded frontier worker
- `frontier_quality`
  - 최고 성능 우선
  - frontier lead/planner/worker 모두 최고 reasoning 우선
- `frontier_cost_guarded`
  - frontier 품질을 유지하면서 비용 guard 적용
- `frontier_private_fallback`
  - 기본은 frontier
  - privacy/token/network 제약이 명시되면 local fallback worker 허용
- `local_lab`
  - 연구용
  - 기본값 아님
- `frontier_token_saver_lab`
  - frontier 기본 경로

## Routing Metadata

current-selection과 control-plane metadata에는 아래가 기록됩니다.

- `execution_mode`
- `worker_tier`
- `fallback_reason`
- `frontier_reachable`
- `local_cache_enabled`
- `token_saver_enabled`

## Migration Policy

이전 local-first profile naming은 canonical path에서 제거되었습니다.

- removed: `default`
- removed: `frontier_low_cost`
- removed: `local_reasoning`
- removed: `low_latency_apfel`
- removed: `preview_nvfp4`

old profile id를 만나면 silent fallback 없이 새 profile 안내와 함께 실패해야 합니다.

## Optional Experimental Slots

- `qmd`
  - optional search provider
  - builtin SQLite search가 기본
