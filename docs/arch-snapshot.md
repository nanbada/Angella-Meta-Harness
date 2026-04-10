# Angella Architecture Snapshot (v3) - Meta-Harness

이 문서는 Angella 하네스의 현재 기술적 구현 상태와 구조를 정의하는 단일 진실 공급원(SSOT)입니다. v3부터는 Goose 기반의 Recipe 체제를 완전히 탈피하여 Gemini Native의 Meta-Harness 구조로 전환되었습니다.

## 1. 아키텍처 패러다임 전환 (Meta-Harness)
- **Brain/Hand Decoupling**: Anthropic의 Meta-Harness 철학을 계승하여, 추론을 담당하는 **Brains**(.gemini/agents)와 실행을 담당하는 **Hands**(.gemini/skills + mcp-servers)를 완전히 분리했습니다.
- **Supervisor Orchestration**: 메인 Gemini 세션(Supervisor)이 복잡한 작업을 연구(Researcher), 구현(Implementer), 검증(Reviewer), 기록(Archivist) 에이전트에게 전략적으로 위임합니다.
- **Session Evidence Store**: `telemetry/logs/harness_activity.md`를 단순한 텍스트 로그가 아닌, 복구 가능한 실행 이력(Append-only Event Stream)으로 취급합니다.

## 2. 하드웨어 및 모델 정책 (Gemma 4 + Ollama)
- **대상 하드웨어**: MacBook Pro M3 Pro (36GB RAM 권장)
- **워커 모델**: `<!--VAR:OLLAMA_MODEL_NAME-->gemma-4-26B-A4B-it-GGUF<!--/VAR-->` (Ollama 기반)
- **Tool-calling 및 Thinking 보정**: Gemma 4의 네이티브 태그 파싱 오류 및 Ollama의 `thinking` 필드 간섭을 하네스 단(`scripts/ollama_proxy.py` 및 `tool_parser_wrapper.py`)에서 가로채어 보정합니다.
- **Native Context Management**: `output_compactor.py`를 통해 에이전트 간 주고받는 대량의 터미널 출력을 실시간으로 요약하여 토큰 효율을 극대화합니다.

## 3. 프로젝트 구조 (Directory Map)
```text
Angella/
├── setup.sh                    # 통합 설치 및 의존성 점검 (Meta-Harness 최적화)
├── GEMINI.md                   # Supervisor 운영 프로토콜 및 에이전트 행동 강령
├── .gemini/                    # Meta-Harness 코어
│   ├── agents/                 # 전담 Brains (Researcher, Implementer, Reviewer, Archivist)
│   └── skills/                 # 전담 Hands (angella-core 인터페이스)
├── config/                     # 하네스 및 모델 설정
│   ├── project-vars.json       # 중앙 집중식 변수 관리 (SSOT)
│   ├── harness-models.yaml     # 모델 성능 점수표
│   └── routing-policies.yaml   # 복잡도 기반 라우팅 정책
├── knowledge/                  # 공유 wiki 및 세션 데이터
│   ├── log.md                  # Session Evidence Store (실행 이력)
│   ├── lessons.md              # Meta-Learning을 통해 추출된 자동 진화 교훈
│   └── sops/                   # 운영 절차 (Scion Swarm, Ratchet Loop 등)
├── mcp-servers/                # 전용 기능 확장 (MCP / Hands)
│   ├── archivist_ops.py        # 지식 정제 및 건강 진단
│   ├── metric_benchmark.py     # 공통 benchmark schema
│   ├── llmwiki_compiler_ops.py # 위키 관리 도구
│   ├── output_compactor.py     # 로그 압축 도구 (SNR 최적화)
│   └── scion_coordination_ops.py # 분산 에이전트 조정 (Redis 지원)
└── scripts/
    ├── sync_project_vars.py    # 변수-에이전트-문서 자동 동기화 툴
    └── ollama_proxy.py         # Ollama 응답 보정 프록시
```

## 4. 핵심 메커니즘
- **Ratchet Pattern (Native)**: 메트릭이 개선된 변경만 Commit하고, 실패는 지식화하여 Revert하는 과정을 Implementer와 Reviewer가 협업하여 수행합니다.
- **Search-First Memory**: 모든 행동 전 Researcher가 `llmwiki`를 조회하여 과거의 실수를 반복하지 않습니다.
- **Meta-Learning**: Archivist가 주기적으로 로그를 분석하여 `lessons.md`를 갱신하고, 시스템의 '기본 규칙'을 스스로 진화시킵니다.
- **Swarm Coordination**: Scion Hub를 통해 다중 에이전트 간 파일 경합을 방지하고 상태를 공유합니다.

## 5. CI/CD & 하네스 안정성 (Hardening)
- **Environment Parity**: `scripts/run-docker-tests.sh`를 통해 로컬에서도 GitHub Actions와 동일한 Ubuntu 24.04 환경의 검증이 가능합니다.
- **Sync-on-Commit**: `.githooks/pre-commit`이 `sync_project_vars.py`를 강제 실행하여 설정값과 에이전트 지침/문서 간의 불일치를 사전에 차단합니다.
- **Fail-Fast & Traceability**: CI 실패 시 상세 환경 덤프와 `set -x` 트레이스를 통해 즉각적인 디버깅 정보를 제공합니다.
