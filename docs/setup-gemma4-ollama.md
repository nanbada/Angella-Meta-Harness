# Gemma 4 + Ollama Local Worker Guide

이 문서는 Angella에서 Gemma 4 Ollama local worker를 실제 `setup -> catalog resolution -> Goose runtime`까지 연결하는 현재 기준 가이드입니다.

## 목표

- Gemma 4 Ollama 경로를 실제 setup/runtime 경로로 사용합니다.
- Ollama 경로는 **Ollama API** topology를 canonical path로 사용합니다.
- `unsloth/gemma-4-26B-A4B-it-GGUF` 모델을 사용하여 로컬에서 고성능 추론 및 Tool-calling을 수행합니다.
- Ollama의 `thinking` 필드가 Goose의 JSON 파싱을 방해하지 않도록 **ollama-proxy**를 경유합니다.

## 1. 기본 설치

```bash
git clone https://github.com/nanbada/Angella.git
cd Angella

bash setup.sh --check
bash setup.sh --yes
```

`setup.sh`는 bootstrap/check/install 단계에서 `.env.mlx`가 있으면 자동으로 읽고, 없으면 `.env.mlx.example`를 기본값으로 사용합니다.

## 2. Ollama Canonical Env

로컬 Ollama worker를 쓰려면 `.env.mlx.example`를 복사한 뒤 canonical env를 채우세요.

```bash
cp .env.mlx.example .env.mlx
```

`.env.mlx` 예시:

```bash
export ANGELLA_LOCAL_WORKER_BACKEND=ollama
export ANGELLA_OLLAMA_BASE_URL=http://127.0.0.1:11435  # Proxy port
export ANGELLA_WORKER_MODEL=gemma4:26b-gguf
```

## 3. Ollama Proxy 실행

Ollama는 Gemma 4 모델 사용 시 응답에 `thinking` 필드를 포함할 수 있으며, 이는 Goose의 엄격한 JSON 파싱을 방해합니다. 이를 해결하기 위해 투명 프록시를 실행해야 합니다.

```bash
python3 scripts/ollama_proxy.py &
```

이 프록시는 11435 포트에서 대기하며, 11434 포트의 Ollama 서버로 요청을 전달하고 응답에서 `thinking` 필드를 제거합니다.

## 4. GGUF 모델 등록 (Modelfile)

Unsloth의 Gemma 4 GGUF 모델을 Ollama에 등록하려면 프로젝트 루트의 `Modelfile.gemma4-gguf`를 사용하세요.

```bash
ollama create gemma4:26b-gguf -f Modelfile.gemma4-gguf
```

## 5. Setup 자동화

Ollama env가 채워져 있으면 Angella는 아래를 자동 처리합니다.

- `bash setup.sh --list-models`
  - `ollama_gemma4_26b_gguf`의 활성화 여부 출력
- `bash setup.sh --check --worker-model ollama_gemma4_26b_gguf`
  - proxy 및 Ollama health 검사
- `bash setup.sh --install-only`
  - Goose custom provider 및 config 자동 렌더링

## 6. Runtime Usage

Ollama worker가 선택된 상태에서 Goose는 setup이 렌더링한 provider/model 조합을 사용합니다.

```bash
goose run --recipe ~/.config/goose/recipes/autoresearch-loop.yaml -s
```

`ollama-proxy`가 실행 중인지 반드시 확인하세요.

## 7. Knowledge Path

- 모든 지식 자료는 repo 내부 `knowledge/`에 저장됩니다.
- `knowledge/sources/`: 수집된 원천 자료
- `knowledge/wiki/`: 구조화된 지식 페이지
- `knowledge/sops/`: 운영 절차 및 실패 패턴

## 8. 완료 기준

- `.env.mlx` 설정만으로 Ollama worker가 자동 인식된다.
- `ollama-proxy`를 통해 Goose가 에러 없이 도구를 호출한다.
- `unsloth/gemma-4-26B-A4B-it-GGUF` 모델이 정상적으로 추론을 수행한다.
