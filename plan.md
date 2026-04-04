# Angella Plan

## 1. 목표

Angella는 Goose 기반의 로컬 자율 최적화 루프를 패키징한 프로젝트다. 핵심 목표는 다음 3가지다.

1. 사용자가 특정 프로젝트를 지정하면 코드 수정, 벤치마크, keep/revert를 반복하는 실행 가능한 recipe를 제공한다.
2. M3 + Ollama/MLX 환경에서 안정적으로 동작하도록 셋업, 설정, 로그 흐름을 일관되게 제공한다.
3. 실험성 데모가 아니라 재현 가능한 운영 도구로 발전시킨다.

## 2. 현재 상태 요약

저장소에는 이미 주요 구성요소가 있다.

- `setup.sh`: Goose, Ollama, Python MCP 의존성, Goose config를 설치한다.
- `config/goose-config.yaml`: Goose 전역 설정과 MCP 확장을 등록한다.
- `recipes/autoresearch-loop.yaml`: self-optimize loop의 메인 recipe다.
- `mcp-servers/metric_benchmark.py`: 벤치마크 실행 및 metric 비교 도구를 제공한다.
- `mcp-servers/obsidian_auto_log.py`: iteration 로그와 최종 보고서를 저장한다.
- `.env.mlx`: MLX/Ollama/Goose 환경 변수를 제공한다.

문제는 구현 자체보다 패키징과 운영 경계가 불명확하다는 점이다. 현재 문서와 설정은 "개인 실험 환경"과 "다른 머신에서도 동작하는 배포물" 사이를 오가고 있다. 이 상태에서는 설치 성공과 실제 실행 성공이 분리된다.

## 3. 핵심 설계 원칙

### 3.1 이식성 우선

저장소 외부 절대 경로를 기본값으로 두지 않는다. 설정 파일, recipe, MCP 실행 경로는 저장소 루트를 기준으로 계산되거나 설치 시점에 템플릿 치환되어야 한다.

### 3.2 설정은 선언적, 설치는 변환형

`config/goose-config.yaml`은 배포 템플릿으로 취급한다. `setup.sh`는 이 템플릿을 그대로 복사하는 대신 현재 설치 경로와 실행 가능한 인터프리터를 반영한 결과물을 생성해야 한다.

### 3.3 루프는 반드시 되돌릴 수 있어야 함

ratchet loop는 "실패 시 완전 복구"가 핵심이다. 따라서 iteration 중 생성된 신규 파일까지 포함해 항상 동일한 단위로 stage/commit/revert가 가능해야 한다.

### 3.4 환경 파일은 덮어쓰기보다 보존이 우선

공유 `.env`류 파일은 사용자의 기존 인증 정보를 깨뜨리면 안 된다. 예시값은 문서에 두고, 실제 `export`는 "이미 값이 없을 때만" 적용한다.

### 3.5 문서와 구현은 1:1로 맞아야 함

README, `plan.md`, recipe, config, setup 스크립트가 서로 다른 실행 방식을 말하면 유지보수가 무너진다. 문서는 반드시 현재 저장소 기준의 실제 동작만 설명해야 한다.

## 4. 목표 아키텍처

### 4.1 실행 흐름

1. 사용자가 `setup.sh`로 로컬 환경을 준비한다.
2. 사용자가 `.env.mlx`를 로드하고 Goose를 실행한다.
3. Goose는 `recipes/autoresearch-loop.yaml`을 사용해 대상 프로젝트를 분석한다.
4. Goose는 `developer` 확장으로 파일 수정과 git 작업을 수행한다.
5. Goose는 `metric-benchmark` MCP로 objective metric을 측정하고, `compare_metrics`로 keep/revert를 판단한다.
6. Goose는 `obsidian-auto-log` MCP로 iteration 로그와 최종 보고서를 저장한다.

### 4.2 구성요소 책임

- `setup.sh`
  설치 검증, 템플릿 렌더링, 경로 주입, 최소 사전점검 담당.
- `config/goose-config.yaml`
  Goose가 로드할 전역 확장과 기본 동작 정의.
- `recipes/autoresearch-loop.yaml`
  최적화 루프의 행위 프로토콜 정의.
- `mcp-servers/metric_benchmark.py`
  측정과 판정 로직 제공.
- `mcp-servers/obsidian_auto_log.py`
  실험 투명성, 추적성, 결과 보관 담당.
- `.env.mlx`
  성능 관련 기본 환경 변수만 제공.

## 5. 확인된 설계 결함

현재 저장소 기준으로 우선 해결해야 할 설계 결함은 다음과 같다.

1. Goose config와 recipe가 저장소 절대 경로에 묶여 있어 다른 머신에서 바로 깨진다.
2. recipe의 commit 전략이 `git commit -am` 기반이라 신규 파일 생성 시 ratchet 복구가 불완전하다.
3. `.env.mlx`가 `GOOGLE_API_KEY`를 무조건 덮어써 기존 인증값을 파괴한다.
4. Goose config는 MCP를 `python`으로 실행하지만 `setup.sh`는 `pip3`만 확인하므로 `python3`만 있는 환경에서 부팅이 실패할 수 있다.

이 4개는 단순 버그가 아니라 배포 설계 문제다. 따라서 개별 수정이 아니라 설치/설정/recipe 책임을 다시 나눠야 한다.

## 6. 최적화된 실행 계획

### Phase 1. 배포 안정화

목표는 "clone 후 setup, then run"이 실제로 성공하는 상태를 만드는 것이다.

- `setup.sh`에서 실행 가능한 Python 인터프리터를 판별한다.
- Goose config를 템플릿 치환 방식으로 생성한다.
- recipe/slash command/MCP 경로를 설치 경로 기준으로 주입한다.
- `.env.mlx`에서 인증키를 기본 보존 방식으로 바꾼다.

완료 기준:

- 임의 경로에 clone한 뒤 `bash setup.sh` 실행 시 Goose config가 올바른 실제 경로를 가리킨다.
- `python` shim이 없어도 MCP 서버가 뜬다.
- 기존 `GOOGLE_API_KEY`가 유지된다.

### Phase 2. 루프 무결성 강화

목표는 keep/revert가 항상 같은 단위로 동작하도록 보장하는 것이다.

- iteration 직전 `git status --short` 기준으로 작업 범위를 점검한다.
- commit 전에 신규 파일을 포함하도록 명시적으로 stage한다.
- revert 전략이 생성 파일까지 완전히 되돌리는지 검증한다.
- dirty worktree 정책을 문서화한다.

완료 기준:

- 신규 파일 생성이 포함된 iteration도 정상 commit/revert된다.
- 실패 iteration 후 작업 디렉토리가 이전 상태와 논리적으로 동일하다.

### Phase 3. 운영 문서 정리

목표는 README와 `plan.md`가 실제 구현의 단일 진실 공급원이 되는 것이다.

- 빠른 시작 절차를 실제 스크립트/recipe 기준으로 통일한다.
- 환경 변수, 의존성, 지원 범위, known limitations를 명시한다.
- "개인 커스터마이징 예시"와 "기본 배포 경로"를 분리한다.

완료 기준:

- 신규 사용자가 README만 보고 설치와 첫 실행을 끝낼 수 있다.
- `plan.md`가 설계 원칙, 리스크, 우선순위를 설명한다.

### Phase 4. 실험 고도화

배포 안정화 이후에만 고도화 작업을 진행한다.

- 프로젝트 타입별 metric parser 정교화
- 실패 iteration에 대한 원인 분류
- baseline 자동 저장 및 resume
- 로그 요약 품질 개선
- Desktop/CLI 공통 진입점 정리

## 7. 우선순위 백로그

### P0

- 경로 하드코딩 제거
- Python 인터프리터 탐지 및 통일
- `.env.mlx` 인증 변수 보존
- recipe의 stage/commit 절차 수정

### P1

- setup 스크립트의 템플릿 렌더링 도입
- dirty worktree 사전 검사 강화
- README 실행 절차와 실제 구현 동기화

### P2

- Next.js/Python/Swift 전용 parser 정확도 개선
- 로그 파일 구조 표준화
- 장기 실행용 실패 복구 전략 추가

## 8. 비목표

현재 단계에서 아래 항목은 우선순위가 아니다.

- Goose 포크 자체를 배포판처럼 재구성하는 작업
- 여러 OS를 동시에 정식 지원하는 작업
- 멀티노드 분산 실행
- UI/브랜딩 고도화

## 9. 성공 지표

프로젝트 성공 여부는 아래 기준으로 판단한다.

- 새 머신의 임의 경로 clone 후 15분 내 첫 실행 가능
- 기본 recipe 실행 시 MCP 부팅 실패율 0에 근접
- 신규 파일이 포함된 iteration에서도 revert 정확도 유지
- README 기준 셋업 성공률 향상
- 로그에서 iteration별 metric과 verdict를 재현 가능

## 10. 다음 액션

바로 실행해야 할 작업 순서는 다음과 같다.

1. `setup.sh`를 템플릿 기반 설치 스크립트로 수정한다.
2. `config/goose-config.yaml`과 `recipes/autoresearch-loop.yaml`에서 절대 경로와 `python` 가정을 제거한다.
3. `.env.mlx`의 `GOOGLE_API_KEY` 처리를 안전하게 바꾼다.
4. recipe의 git stage/commit 전략을 ratchet-safe 방식으로 교체한다.
5. README를 실제 동작 기준으로 다시 맞춘다.

이 순서를 지키는 이유는 단순하다. 지금 프로젝트의 병목은 모델 품질이 아니라 실행 재현성과 설치 신뢰성이다. 배포 경계가 안정화된 뒤에야 self-optimize loop의 성능 실험이 의미를 가진다.
