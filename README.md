# Angella

MacBook Pro M3 36GB에서 [Goose](https://github.com/block/goose)를 활용해 실행하는 adaptive hybrid harness입니다.

Angella는 frontier lead/planner + local worker + control plane 구조를 사용합니다. 모델은 더 이상 고정값이 아니라 catalog/selector로 결정되며, 기본 실행 흐름은 [`recipes/autoresearch-loop.yaml`](recipes/autoresearch-loop.yaml) 하나로 고정합니다.

## 핵심 동작

Angella는 clean Git 저장소에서만 시작합니다.

1. 대상 프로젝트가 Git 저장소인지 확인합니다.
2. tracked 변경과 untracked 파일을 포함해 worktree가 깨끗한지 확인합니다.
3. 현재 브랜치가 아니라 `angella/run-<timestamp>` 전용 실행 브랜치를 만듭니다.
4. Intent Contract를 고정하고 baseline을 측정합니다.
5. edit → benchmark → keep/revert를 반복합니다.
6. 모든 iteration을 `run_id` 기준 로그와 final report로 남깁니다.

핵심은 모델 이름 하나가 아니라, 의도 계약, selector 기반 모델 해상도, 객관적 메트릭, 안전한 revert, 그리고 run-scoped transparency입니다.

## 빠른 시작

### 1. 사전 점검

```bash
bash setup.sh --check
```

이 모드는 설치 없이 아래만 검증합니다.

- 필수 런타임 존재 여부
- Python/pip 사용 가능 여부
- Angella 템플릿 렌더링 가능 여부
- placeholder 또는 개발자 전용 절대 경로 누락 여부

### 2. 설치

```bash
bash setup.sh
```

무인 설치가 필요하면 아래를 사용합니다.

```bash
bash setup.sh --yes
```

`setup.sh`는 다음을 수행합니다.

- Stage 1: bootstrap
  - Goose CLI 확인 또는 Homebrew 설치
  - Ollama 확인 및 서버 시작 여부 점검
  - harness catalog/profile resolution
  - selected worker runtime 확인
  - reusable bootstrap Python env 준비
- Stage 2: install
  - Goose config와 recipe/sub-recipe 렌더링
  - custom provider/apfel template 렌더링
  - control-plane 디렉토리 생성
  - Angella 로그 디렉토리 생성
  - follow-up 실행 정보 출력

### 3. 환경 변수 적용

```bash
cp .env.mlx.example .env.mlx
source .env.mlx
```

`.env.mlx.example`는 커밋되는 예시 파일이고, 실제 로컬 환경 파일은 `.env.mlx`로 두고 git에는 올리지 않습니다. 이 파일은 `ANGELLA_ROOT`와 `OBSIDIAN_VAULT_PATH`를 결정적으로 설정합니다. 별도 override가 없으면 로그는 Angella 설치 경로 하위 `logs/`에 저장됩니다.

Repo-local cache paths:

- bootstrap env: `.cache/angella/bootstrap-venv`
- uv cache: `.cache/angella/uv`
- pip cache: `.cache/angella/pip`
- optional wheelhouse: `vendor/wheels`

선택적으로 stage를 분리해서 실행할 수도 있습니다.

```bash
bash setup.sh --bootstrap-only
bash setup.sh --install-only
```

wheelhouse를 미리 채우려면:

```bash
bash scripts/build-wheelhouse.sh
```

Harness catalog를 보려면:

```bash
bash setup.sh --list-models
bash setup.sh --list-harness-profiles
```

특정 조합을 강제하려면:

```bash
bash setup.sh --yes \
  --harness-profile default \
  --lead-model openai_gpt_5_2_pro \
  --planner-model anthropic_claude_sonnet_4 \
  --worker-model ollama_gemma4_26b
```

### 4. Lead/Planner Credential 확인

Angella는 lead/planner를 catalog/selector로 고릅니다. 기본 catalog에는 Google, Anthropic, OpenAI frontier 후보가 들어 있으며, `setup.sh`는 필요한 credential 존재 여부만 안내합니다.

직접 설정하려면:

```bash
goose configure
```

또는 셸에서 미리 export 합니다.

### 5. Autoresearch loop 실행

```bash
goose run --recipe ~/.config/goose/recipes/autoresearch-loop.yaml -s
```

Harness self-optimize recipe도 설치 후 바로 사용할 수 있습니다.

```bash
goose run --recipe ~/.config/goose/recipes/harness-self-optimize.yaml -s
```

입력 파라미터:

- `target_project_path`: 최적화할 프로젝트의 절대 경로
- `objective_metric`: `build_time`, `tokens_per_second`, `latency_ms`, `bundle_size`
- `benchmark_command`: 실제 benchmark 명령
- `max_iterations`: 최대 반복 횟수
- `improvement_threshold`: keep 판정 임계값

예시:

```bash
goose run --recipe ~/.config/goose/recipes/autoresearch-loop.yaml -s \
  --params target_project_path=/absolute/path/to/project \
  --params objective_metric=build_time \
  --params benchmark_command='npm run build'
```

## Intent Contract

루프는 baseline 전에 아래 계약을 고정합니다.

- `ideal_state_8_12_words`
- `metric_key`
- `intent_summary`
- `metric_reason`
- `non_goals`
- `success_threshold`
- `binary_acceptance_checks`
- `operator_constraints`
- `first_hypotheses`

이 값은 baseline 로그와 final report에 모두 기록됩니다.

## Benchmark Contract

기본 benchmark MCP와 프로젝트별 adapter는 모두 같은 핵심 payload를 반환해야 합니다.

- `success`
- `metric_key`
- `metric_value`
- `duration_seconds`
- `exit_code`
- `stdout_tail`
- `stderr_tail`
- `aux_metrics`

판정 규칙:

- `success=false`면 실패 iteration입니다.
- benchmark non-zero exit, metric parse 실패, timeout은 모두 revert 대상입니다.
- 실패 iteration은 baseline을 갱신하지 않습니다.

## Git 운영 규칙

- dirty worktree에서는 시작하지 않습니다.
- 사용자의 현재 브랜치에서 직접 수정하지 않습니다.
- 각 run은 `angella/run-<timestamp>` 브랜치에서 수행합니다.
- 각 iteration은 candidate commit 생성 후 benchmark를 거쳐 keep 또는 `git revert HEAD --no-edit`로 정리합니다.
- run 종료 후 자동으로 원래 브랜치로 돌아가지 않습니다.

## 로그와 Transparency

기본 로그 경로:

`$ANGELLA_ROOT/logs/Goose Logs/`

환경변수 `OBSIDIAN_VAULT_PATH`를 주면 그 경로를 우선합니다.

생성 파일:

- `<run_id>.md`: baseline, iteration별 keep/revert/failure 기록
- `<run_id>-FINAL.md`: 최종 결과와 전체 diff 요약

로그에는 다음이 포함됩니다.

- `run_id`
- `start_commit`
- `candidate_commit`
- `decision`
- `improvement_percent`
- `benchmark_command`
- `working_directory`
- `failure_reason`
- Intent Contract

Control-plane runtime state:

- `.cache/angella/control-plane/runs/<run_id>/intent.json`
- `.cache/angella/control-plane/runs/<run_id>/telemetry.jsonl`
- `.cache/angella/control-plane/runs/<run_id>/summary.json`
- `.cache/angella/control-plane/runs/<run_id>/report.md`
- `.cache/angella/control-plane/failures/open/*.json`
- `.cache/angella/control-plane/queue/meta-loop/*.json`
- `.cache/angella/control-plane/install/summary.json`
- `.cache/angella/control-plane/install/telemetry.jsonl`

Accepted harness meta-loop run은 다음을 자동으로 수행할 수 있습니다.

- SOP/skill draft 생성
- promotion rule 충족 시 tracked `knowledge/` 로 승격
- 기존 tracked knowledge 파일이 있으면 run-scoped addendum merge
- 같은 accepted run이 만든 open failure artifact는 `failures/closed/` 로 정리
- `codex/` 브랜치 push + draft PR 생성
- stale draft / queue artifact 정리
- inspection tool로 recent runs / failures / drafts / queue 상태 조회
- inspection tool을 `format=markdown` 으로 호출해 operator-facing dashboard 생성
- component description tool로 benchmark command / acceptance checks / priority files 조회

verification-only run은 `report.md` 와 `summary.json` 만 남기고 finalize/export/promotion 을 실행하지 않습니다.

- verification-only summary에는 `objective_component` 가 유지되어 inspection에서 component가 사라지지 않습니다
- self-optimize recipe는 관련 failure type 또는 worker pattern에 대응하는 tracked `knowledge/sops/`, `knowledge/skills/` 를 먼저 읽고 없으면 없다고 명시합니다

`dry_run=true` 경로는 preview 전용이며 draft 파일, queue entry, branch 상태를 실제로 바꾸지 않습니다.

Accepted export branch는 deterministic naming policy를 사용합니다.

- prefix: `codex/meta-loop-`
- objective와 run id slug는 길이 제한이 있다
- 마지막에 stable hash suffix가 붙는다

Accepted meta-loop export PR은 proof/reference artifact가 기본값입니다.

- 첫 문단에 `Reference proof only. Not intended for merge.` 를 넣는다
- primary structure PR은 `#6` 을 기준으로 링크한다
- proof PR은 merge 대상이 아니라 accepted-run evidence 보존용으로 유지한다

Install stage는 rendered Goose config/recipe hash를 현재 target hash와 비교합니다.

- drift 정보는 bootstrap state와 `.cache/angella/control-plane/install/summary.json` 에 기록됩니다
- `bash setup.sh --install-only --yes` 는 deterministic overwrite 를 수행합니다
- interactive install은 drift warning 후 overwrite 여부를 기록합니다

preview worker를 다시 도입할 때는 [`docs/preview-worker-reintroduction.md`](/Users/nanbada/projects/Angella/docs/preview-worker-reintroduction.md) 의 gating 전략을 따른다.

promotion body 품질 기준은 [`docs/promotion-content-quality.md`](/Users/nanbada/projects/Angella/docs/promotion-content-quality.md) 에 정리한다.

## 프로젝트별 Adapter

기본 flow는 generic benchmark MCP를 사용합니다. 아래 adapter는 같은 출력 계약과 `run_benchmark`/`compare_metrics` 인터페이스를 제공하는 선택형 대체재입니다.

| 프로젝트 | 서버 파일 | 주요 metric |
|----------|-----------|-------------|
| Next.js | [`mcp-servers/metric_benchmark_nextjs.py`](mcp-servers/metric_benchmark_nextjs.py) | `build_time`, `bundle_size` |
| Python/MLX | [`mcp-servers/metric_benchmark_python.py`](mcp-servers/metric_benchmark_python.py) | `tokens_per_second`, `latency_ms` |
| Swift/SwiftUI | [`mcp-servers/metric_benchmark_swift.py`](mcp-servers/metric_benchmark_swift.py) | `build_time`, `latency_ms` |

이 adapter들은 공식 기본 경로가 아니며, main recipe를 바꾸지 않고 교체 가능한 benchmark backend로만 취급합니다.

## 프로젝트 구조

```text
Angella/
├── setup.sh
├── .env.mlx.example
├── .goosehints
├── .cache/                         # local bootstrap/cache/control-plane only
├── config/
│   ├── harness-models.yaml
│   ├── harness-profiles.yaml
│   ├── goose-config.yaml
│   ├── init-config.yaml
│   └── custom-providers/
├── docs/
│   ├── hybrid-harness.md
│   ├── setup-check-optimization-history.md
│   └── setup-installer-architecture.md
├── knowledge/
│   ├── sops/
│   └── skills/
├── scripts/
│   ├── harness_catalog.py
│   ├── build-wheelhouse.sh
│   ├── setup-common.sh
│   ├── setup-bootstrap.sh
│   ├── setup-install.sh
│   └── test_setup_flows.sh
├── recipes/
│   ├── autoresearch-loop.yaml
│   ├── harness-self-optimize.yaml
│   └── sub/
│       ├── code-optimize.yaml
│       └── evaluate-metric.yaml
├── mcp-servers/
│   ├── common.py
│   ├── metric_benchmark.py
│   ├── metric_benchmark_nextjs.py
│   ├── metric_benchmark_python.py
│   ├── metric_benchmark_swift.py
│   ├── obsidian_auto_log.py
│   └── requirements.txt
├── .github/workflows/
│   └── repo-checks.yml
└── logs/
```
