# Preview Worker Reintroduction Strategy

Preview worker는 catalog에서 제거된 상태이며, 재도입은 아래 조건을 모두 만족할 때만 허용합니다.

## Preconditions

- preview 모델 항목이 `config/harness-models.yaml`에 다시 추가된다
- worker 항목은 반드시 `flags: ["preview", ...]` 를 가진다
- `availability_check`는 env flag와 실제 provider health/model check를 함께 가진다
- 기본 profile은 preview selector를 사용하지 않는다

## Selector policy

- preview profile만 `best_local_preview` 를 사용한다
- `default`, `frontier_low_cost`, `local_reasoning` 은 preview 후보를 절대 기본값으로 사용하지 않는다
- preview selector tie-break는 `reasoning_score`, `tool_use_score`, `stability_score`, `priority` 순서를 따른다

## Required tests

- preview model이 catalog에 없으면 `preview_nvfp4` profile은 disabled로 출력된다
- preview model이 catalog에 있고 flag/env/provider check가 모두 통과하면 `preview_nvfp4` profile이 활성화된다
- setup install 결과물에 preview profile metadata가 정확히 반영된다
- accepted meta-loop finalize가 preview worker run도 동일하게 draft/promotion/export 경로를 따른다

## Rollout

1. preview worker를 catalog에 gated candidate로 추가한다
2. local sandbox host에서 `setup.sh --list-harness-profiles` 와 실제 `--yes` flow를 검증한다
3. preview worker 전용 accepted run 1회를 수행한다
4. 반복적으로 유효하면 tracked skill/SOP로 승격한다
