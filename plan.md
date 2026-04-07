# Angella Plan

## 1. 문서 목적

이 문서는 [`reference.md`](reference.md)의 최초 요청사항을 현재 저장소 기준으로 재구성한 계획 문서다. 목표는 두 가지다.

1. 원래 의도였던 Goose 기반 로컬 자율 최적화 시스템의 방향을 보존한다.
2. 현재 실제 구현 상태와 미래 확장 구상을 분리해서 설계-구현 불일치를 줄인다.

## 2. 원래 요청사항 해석

`reference.md`가 가리키는 축은 다음 3개다.

1. Goose를 핵심 실행 엔진으로 삼는다.
2. Mac 내장 AI를 활용하는 `apfel` 같은 로컬 네이티브 모델 경로를 검토한다.
3. 2026년 AI 에이전트 설계 화두인 Autoresearch, Intent-Based Engineering, Scaffolding, Transparency를 제품 설계에 반영한다.

즉 Angella는 단순한 Goose 설정 모음이 아니라, 로컬 Mac 환경에서 반복 가능한 self-optimize loop를 제공하는 orchestration layer가 되어야 한다.

## 3. 제품 비전

Angella는 다음 문제를 푸는 도구다.

- 사용자가 특정 프로젝트를 지정하면 AI가 개선 의도를 명확히 정리한다.
- 변경을 작게 쪼개어 시도하고 metric으로 판정한다.
- 개선되면 keep, 아니면 revert한다.
- 과정 전체를 로그로 남겨 재현성과 투명성을 보장한다.

핵심은 "좋은 모델 하나"가 아니라 "좋은 루프 하나"다. 모델 품질은 교체 가능하지만, 루프의 안정성, 측정, 복구, 기록은 제품 정체성에 해당한다.

## 4. 설계 배경

### 4.1 Goose를 채택하는 이유

Goose는 CLI/recipe/extension 기반으로 도구 호출과 에이전트 흐름을 조합하기 좋다. Angella는 Goose를 포크 대체재로 만들려는 것이 아니라, Goose 위에 self-optimize workflow를 얹는 배포 레이어로 위치시킨다.

### 4.2 Intent-Based Engineering 반영

사용자 요청은 바로 코드 변경으로 들어가면 안 된다. 먼저 최적화 의도를 짧고 검증 가능한 문장으로 정규화해야 한다. 이 단계가 빠지면 루프가 "열심히 수정하지만 무엇을 최적화하는지 불명확한 상태"로 흐르기 쉽다.

### 4.3 Autoresearch / Ratchet Loop 반영

핵심 반복 단위는 아래 구조를 따른다.

1. 목표를 명시한다.
2. baseline을 측정한다.
3. 하나의 가설만 구현한다.
4. 다시 측정한다.
5. 개선이면 keep, 아니면 revert한다.
6. 결과를 남긴다.

이 구조는 성능 실험, 빌드 시간 단축, 추론 속도 개선 같은 과제에 특히 적합하다.

### 4.4 Scaffolding 반영

실제 업무의 큰 부분은 "문제를 푸는 사고"보다 "실행 구조를 유지하는 일"이다. Angella의 가치도 개별 프롬프트보다 setup, recipe, benchmark, revert, log, report를 패키징하는 스캐폴딩에 있다.

### 4.5 Transparency 반영

iteration별 metric, git diff, verdict를 남겨야 한다. 그래야 실패를 분석할 수 있고, 개선된 결과를 재사용할 수 있다. 로그는 부가 기능이 아니라 제품의 신뢰성 계층이다.

## 5. 현재 구현 상태

저장소에는 다음 구성요소가 있다.

- [`setup.sh`](setup.sh)
  Goose CLI, Ollama, 모델, Python MCP 의존성, 렌더된 Goose config를 설치한다.
- [`config/goose-config.yaml`](config/goose-config.yaml)
  Goose 전역 설정 템플릿이다.
- [`recipes/autoresearch-loop.yaml`](recipes/autoresearch-loop.yaml)
  메인 ratchet loop recipe 템플릿이다.
- [`mcp-servers/metric_benchmark.py`](mcp-servers/metric_benchmark.py)
  benchmark 실행과 metric 비교를 담당한다.
- [`mcp-servers/obsidian_auto_log.py`](mcp-servers/obsidian_auto_log.py)
  iteration 로그와 최종 보고서를 저장한다.
- [`.env.mlx.example`](.env.mlx.example)
  MLX/Ollama/Goose 관련 환경 변수 예시를 제공하고, 실제 `.env.mlx`는 로컬 전용으로 유지한다.

현재 구현은 "Goose + Ollama + MCP" 경로에는 도달해 있다. 반면 `apfel`과 다중 provider routing은 아직 제품 설계상 후보이며, 실제 기본 경로는 아니다.

## 6. 현재 아키텍처와 목표 아키텍처

### 6.1 현재 아키텍처

- 실행 엔진: Goose
- 기본 모델 경로: Ollama
- 평가/측정: metric benchmark MCP
- 로그/투명성: obsidian auto log MCP
- 배포 방식: setup 기반 로컬 설치

### 6.2 목표 아키텍처

장기적으로는 provider를 3계층으로 나누는 것이 맞다.

- Orchestration layer
  Goose가 workflow, 도구 호출, recipe 실행을 담당
- Model layer
  Ollama, Gemini, 향후 apfel을 역할별로 배치
- Evidence layer
  benchmark, git history, 로그, 보고서가 판단 근거를 담당

즉 모델은 교체 가능해야 하고, loop와 evidence는 고정되어야 한다.

### 6.3 v1 운영 계약

실제 구현 단계에서는 아래 계약을 고정한다.

- 공식 기본 flow는 `recipes/autoresearch-loop.yaml` 하나다.
- 기본 실행 경로는 Goose + Ollama + generic benchmark MCP + logger MCP다.
- 프로젝트별 benchmark MCP와 `recipes/sub/*.yaml`은 같은 계약을 만족하는 선택형 adapter다.
- 루프는 clean Git 저장소에서만 시작한다.
- 모든 run은 전용 브랜치 `angella/run-<timestamp>`에서 수행한다.
- baseline 전에 `run_id`, `start_commit`, Intent Contract를 고정한다.
- benchmark 계층은 `success`, `metric_key`, `metric_value`, `duration_seconds`, `exit_code`, `stdout_tail`, `stderr_tail`, `aux_metrics`를 공통 출력으로 사용한다.
- benchmark non-zero exit, parse 실패, timeout은 모두 failure iteration이며 baseline을 갱신하지 않는다.
- transparency는 날짜 단위 로그가 아니라 run-scoped log를 기준으로 남긴다.

## 7. 핵심 설계 원칙

### 7.1 이식성 우선

절대 경로를 기본값으로 두지 않는다. 설정 파일과 recipe는 설치 시점에 렌더링한다.

### 7.2 루프 안정성 우선

루프는 반드시 측정 가능하고 되돌릴 수 있어야 한다. 신규 파일 생성, 실패 iteration, dirty worktree를 모두 고려해야 한다.

### 7.3 의도 정규화 우선

사용자 요청은 바로 구현하지 않고 목표 metric, 임계값, 허용 가능한 tradeoff로 정리해야 한다.

### 7.4 스캐폴딩 우선

setup, config, benchmark, logging, reporting을 제품 기능으로 취급한다. 이것들은 "부가 도구"가 아니다.

### 7.5 투명성 우선

각 iteration의 이유, 변경, 측정, 판정이 로그에 남아야 한다.

### 7.6 구현과 비전 분리

문서는 현재 지원 기능과 미래 구상을 분리해서 적어야 한다. 아직 지원하지 않는 `apfel` 경로를 기본 동작처럼 문서화하면 안 된다.

### 7.7 실행 계약 우선

설계 문서만이 아니라 setup, recipe, MCP, README가 같은 계약을 공유해야 한다. 특히 다음은 문서 표현이 아니라 실제 인터페이스로 취급한다.

- `setup.sh --yes`, `setup.sh --check`
- template placeholder 렌더링 규칙
- benchmark/logger payload 스키마
- dirty worktree 차단 정책
- run branch와 run_id 기록 규칙

## 8. 설계 결함과 교정 방향

이미 드러난 배포/운영 결함은 다음과 같다.

1. 경로 하드코딩
2. `python`/`python3` 실행 불일치
3. `GOOGLE_API_KEY` 덮어쓰기
4. 신규 파일이 누락되는 ratchet commit 전략
5. setup가 pip 실패를 성공처럼 보이게 하는 오류

이 결함들은 단순 구현 실수가 아니라, Angella가 스캐폴딩 계층을 제품으로 취급해야 한다는 요구를 다시 보여준다.

## 9. reference.md 기반 추가 보강 포인트

### 9.1 apfel 통합은 "후속 확장"으로 명확히 위치시켜야 함

`reference.md`에는 apfel이 중요한 단서로 남아 있지만 현재 저장소는 이를 지원하지 않는다. 따라서 설계상으로는 다음과 같이 두는 것이 맞다.

- 현재 기본 경로: Goose + Ollama + Gemini
- 후속 실험 경로: Goose + apfel native provider

즉 apfel은 제거 대상이 아니라, 문서상에서 현재 미구현 확장 후보로 복원되어야 한다.

### 9.2 Intent Clarifier 계층이 plan에 더 명시되어야 함

현재 문서는 ratchet loop를 설명하지만 "의도를 정규화하는 첫 단계"의 중요성이 충분히 드러나지 않는다. 목표, metric, threshold, non-goal을 먼저 고정하는 단계가 plan 상위 레벨에 승격되어야 한다.

### 9.3 Transparency를 보고서 기능이 아니라 운영 원칙으로 승격해야 함

지금 문서도 logging을 언급하지만, design principle과 success metric에 더 직접 연결하는 편이 맞다.

### 9.4 Scaffolding을 백로그 우선순위 판단 기준으로 써야 함

새 기능을 추가할 때 "모델을 하나 더 붙이는 일"보다 "실패를 줄이는 구조를 만드는 일"을 우선시해야 한다. 이 기준이 roadmap에 드러나야 한다.

## 10. 단계별 실행 계획

### Phase 1. 배포 안정화

목표는 clone 후 setup, then run이 실제로 성공하는 상태를 만드는 것이다.

- setup가 설치와 실패를 정확히 판정
- Goose config/recipe를 템플릿 렌더링
- Python 실행 경로 일치
- `.env.mlx`의 안전한 인증 처리

완료 기준:

- 임의 경로 clone 후 첫 실행 가능
- MCP 부팅 실패율 최소화
- 설치 실패가 성공처럼 보이지 않음

### Phase 2. 루프 무결성 강화

목표는 ratchet loop를 운영 가능한 수준으로 만드는 것이다.

- `git add -A` 기준의 완전한 stage
- revert 후 작업 디렉터리 무결성 검증
- dirty worktree 정책 명문화
- baseline 측정과 threshold 판정의 일관성 확보

완료 기준:

- 신규 파일 포함 iteration도 복구 가능
- 실패 실험의 흔적이 논리적으로 제거됨

### Phase 3. Intent Layer 강화

목표는 요청을 바로 수정하지 않고, 최적화 계약으로 바꾸는 것이다.

- objective metric 강제
- threshold와 non-goal 명시
- target project 분석 단계 강화
- recipe 상단에 intent clarification 규칙 명문화

완료 기준:

- 루프 시작 전에 "무엇을 왜 최적화하는지"가 항상 명확함

### Phase 4. Transparency Layer 강화

목표는 결과뿐 아니라 근거를 남기는 것이다.

- iteration별 제안, 선택 이유, 측정값 기록
- keep/revert 판정 근거 저장
- 최종 보고서 요약 정형화

완료 기준:

- 사후 분석만으로도 어떤 변경이 왜 남았는지 추적 가능

### Phase 5. Provider 확장

이 단계부터 `apfel` 같은 새로운 provider를 검토한다.

- apfel 통합 feasibility 검증
- 역할별 provider 분리
- native model과 Ollama의 성능/지연/안정성 비교

완료 기준:

- 기본 경로를 깨지 않고 provider 실험 가능

### Phase 6. Personal Agent & LLM-Wiki 통합 (완료)

목표는 RAG 기반을 탈피하여 LLM 스스로 위키를 관리하는 OS 개인비서로의 확장이다.

- LLM-Wiki (`knowledge/raw/` vs `knowledge/wiki/` 레이어 분리) 적용 및 `llm-wiki-compiler` 파이프라인 연동 완료.
- 데스크톱 통합을 위한 Personal Context MCP (`read_calendar_events`, `read_reminders`, `read_clipboard`) 연동 완료.
- 무거운 구형 Meta-Loop(약 160KB 분량의 control_plane 등) 코드를 삭제하여 토큰/성능 최적화 완료.
- Gemma 4 + MLX + TurboQuant 아키텍처에 대응하는 Native Tool-call/Parsing 한계를 Harness단에서 회피할 수 있는 체제 마련.

완료 기준:

- 새로운 Personal Recipe 실행 시 LLM이 스스로 Context를 ingest하고 위키에 구조화된 기록을 남김 (달성).

## 11. 우선순위 백로그

### P0

- 배포 경로 이식성
- Python/pip 설치 안정성
- ratchet-safe commit/revert
- 안전한 env 처리

### P1

- intent clarification 강화
- dirty worktree 정책 강화
- README와 실제 실행 흐름 동기화
- transparency 로그 구조 보강

### P2

- 프로젝트 타입별 metric parser 개선
- baseline resume
- failure taxonomy
- 최종 보고서 품질 개선

### P3

- apfel 통합
- provider routing 실험
- Goose Desktop/CLI 공통 UX 정리

## 12. 비목표

현재 단계에서 아래 항목은 우선순위가 아니다.

- Goose 자체를 대체하는 독자 에이전트 런타임 구현
- 다중 OS 정식 지원
- 분산 실행 인프라
- 화려한 UI나 브랜딩 중심 개선

## 13. 성공 지표

- 새 머신의 임의 경로 clone 후 15분 내 첫 실행 가능
- setup 실패가 명확하게 드러남
- 기본 recipe 실행 시 MCP 부팅 실패율이 낮음
- iteration별 metric, verdict, git diff가 남음
- 사용자가 "무엇을 최적화 중인지"를 루프 시작 전에 이해할 수 있음
- 향후 apfel/provider 확장이 기본 경로를 깨지 않음

## 14. 다음 액션

다음 작업 순서는 아래가 맞다.

1. setup와 README를 실제 동작 기준으로 계속 정리한다.
2. recipe에 intent clarification 계약을 더 명확히 반영한다.
3. logging/reporting 구조를 보강한다.
4. benchmark parser 정확도를 높인다.
5. 그 다음에야 apfel/provider 확장을 검토한다.

요점은 단순하다. `reference.md`가 말하는 본질은 "모델을 더 붙여라"가 아니라 "좋은 에이전트 스캐폴딩을 만들어라"에 가깝다. Angella는 그 방향으로 설계되어야 한다.
