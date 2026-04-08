# Gemma 4 + MLX Local Worker Guide

이 문서는 Angella에서 Gemma 4 MLX local worker를 실제 `setup -> catalog resolution -> Goose runtime`까지 연결하는 현재 기준 가이드입니다.

## 목표

- Gemma 4 MLX 경로를 문서용 메모가 아니라 실제 setup/runtime 경로로 사용합니다.
- MLX 경로는 **OpenAI-compatible local endpoint** topology를 canonical path로 사용합니다.
- `ollama_gemma4_26b`는 기본 local fallback으로 남기고, `mlx_gemma4_31b_it_4bit`는 고품질 local worker로 노출합니다.
- 로컬 구현, 코드 수정, 다단계 작업용 worker는 Gemma 4를 우선 사용하고, apfel은 단순 확인/짧은 질문 보조용으로만 제한합니다.

## 1. 기본 설치

```bash
git clone https://github.com/nanbada/Angella.git
cd Angella

bash setup.sh --check
bash setup.sh --yes
```

`setup.sh`는 bootstrap/check/install 단계에서 `.env.mlx`가 있으면 자동으로 읽고, 없으면 `.env.mlx.example`를 기본값으로 사용합니다.

## 2. MLX Canonical Env

로컬 MLX worker를 쓰려면 `.env.mlx.example`를 복사한 뒤 canonical env를 채우세요.

```bash
cp .env.mlx.example .env.mlx
```

`.env.mlx` 예시:

```bash
export ANGELLA_LOCAL_WORKER_BACKEND=mlx
export ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1
export ANGELLA_MLX_MODEL=mlx-community/gemma-4-31b-it-4bit
```

지원되는 backend 값:

- `ollama`: 기본 local fallback 경로
- `mlx`: OpenAI-compatible local endpoint 경로

Deprecated alias는 한 phase 동안만 유지됩니다.

```bash
export ANGELLA_APFEL_BASE_URL=http://127.0.0.1:11435/v1
export ANGELLA_APFEL_MODEL=apple-foundationmodel
```

새 설정에서는 `ANGELLA_MLX_BASE_URL`, `ANGELLA_MLX_MODEL`을 우선 사용하세요.

## 3. Local LLM 역할 분리

- `mlx_gemma4_31b_it_4bit`
  - 로컬 구현, 코드 수정, schema 정리, 여러 단계 reasoning이 필요한 worker 경로
  - `personal_agent_tier`에서 `ANGELLA_LOCAL_CONTEXT_NEEDED=true` 또는 `ANGELLA_PRIVATE_MODE=true`면 local fallback worker로도 사용 가능
- `apfel_foundationmodel`
  - 짧은 확인, 단순 질문 응답, 저지연 보조 확인용 legacy local assistant
  - 기본 implementation worker나 primary coding worker로는 사용하지 않음

## 4. Setup가 자동으로 해주는 일

MLX env가 채워져 있으면 Angella는 아래를 자동 처리합니다.

- `bash setup.sh --list-models`
  - `mlx_gemma4_31b_it_4bit`의 enabled/disabled 이유를 출력
- `bash setup.sh --check --worker-model mlx_gemma4_31b_it_4bit`
  - endpoint health를 검사하고 성공 또는 actionable failure를 반환
- `bash setup.sh --install-only`
  - Goose custom provider `angella_mlx_local`을 자동 렌더링

따라서 `config/harness-models.yaml`을 수동 편집할 필요가 없습니다.

## 5. Acceptance Checks

MLX endpoint가 준비된 상태에서 아래 명령으로 제품화 경로를 검증합니다.

```bash
bash setup.sh --list-models
bash setup.sh --list-harness-profiles
bash setup.sh --check --worker-model mlx_gemma4_31b_it_4bit
bash setup.sh --install-only --worker-model mlx_gemma4_31b_it_4bit --yes
```

기대 결과:

- `mlx_gemma4_31b_it_4bit`가 enabled로 보임
- `local_lab` 프로파일이 MLX worker를 선택할 수 있음
- Goose custom provider `angella_mlx_local`이 렌더링됨
- endpoint가 비정상이면 `ANGELLA_LOCAL_WORKER_BACKEND=mlx`와 `ANGELLA_MLX_BASE_URL` 기준의 실패 메시지가 출력됨

## 6. Bootstrap Runtime Probe

bootstrap venv의 `mlx` / `mlx_lm` import가 안전하게 되는지 보려면 아래 probe를 사용하세요.

```bash
python3 scripts/check_mlx_runtime.py --python .cache/angella/bootstrap-venv/bin/python
```

이 probe는 child process에서 import를 시도하므로, MLX import가 abort되어도 부모 진단 프로세스는 살아남습니다.

대표적인 분류:

- `ok`
  - bootstrap venv에서 `mlx`, `mlx_lm` import 성공
- `metal_device_init_crash`
  - Metal device 초기화 단계에서 abort
  - Codex 안에서는 sandbox / Metal visibility 제한일 수 있으므로, 필요하면 같은 probe를 sandbox 밖에서도 다시 실행해 비교
- `missing_module`
  - bootstrap venv에 `mlx` 또는 `mlx_lm`가 설치되지 않음

## 7. MLX Server Launcher

bootstrap venv에 들어 있는 `mlx_lm.server`를 canonical env 기준으로 띄우려면 아래 launcher를 사용하세요.

```bash
python3 scripts/start_mlx_server.py --dry-run
```

기본값:

- `ANGELLA_MLX_BASE_URL`가 없으면 `http://127.0.0.1:11435/v1`
- `ANGELLA_MLX_MODEL`이 없으면 `mlx-community/gemma-4-31b-it-4bit`
- server binary는 `.cache/angella/bootstrap-venv/bin/mlx_lm.server`

launcher는 `ANGELLA_MLX_MODEL`을 그대로 `--model`에 넘깁니다. `mlx_lm` 소스 기준으로 이 값은:

- 이미 변환된 local MLX model path일 수도 있고
- Hugging Face repo id일 수도 있습니다

즉 host network가 열려 있으면 repo id에서 직접 snapshot download를 트리거할 수 있습니다.

실행 예시:

```bash
export ANGELLA_LOCAL_WORKER_BACKEND=mlx
export ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1
export ANGELLA_MLX_MODEL=mlx-community/gemma-4-31b-it-4bit

python3 scripts/start_mlx_server.py
```

추가 server flag가 필요하면 `--` 뒤에 그대로 넘기세요.

```bash
python3 scripts/start_mlx_server.py -- --log-level DEBUG
```

## 8. Runtime Usage

MLX worker가 선택된 상태에서 Goose는 setup이 렌더링한 provider/model 조합만 사용합니다.

```bash
goose run --recipe ~/.config/goose/recipes/autoresearch-loop.yaml -s
```

또는 personal agent loop:

```bash
goose run --recipe ~/.config/goose/recipes/personal-agent-loop.yaml -s
```

`tool_parser_wrapper.py`는 이미 repo에 포함되어 있으므로 별도 wrapper 코드를 다시 추가할 필요가 없습니다.

## 9. Knowledge Path

- raw knowledge source는 repo 내부 `knowledge/sources/`에 저장됩니다.
- note 저장과 personal-context ingest는 외부 knowledge override가 아니라 이 내부 경로를 canonical source root로 사용합니다.

## 10. 완료 기준

Phase 5는 아래가 만족되면 완료로 봅니다.

- 새 clone 환경에서 `.env.mlx`만 채우면 MLX worker가 자동 인식된다.
- MLX endpoint가 없거나 죽어 있으면 setup이 명확한 실패 이유를 반환한다.
- runtime은 `angella_mlx_local` provider와 resolved model만 소비한다.
