# Angella Architecture Snapshot (v3) - Meta-Harness

이 문서는 Angella 하네스의 현재 기술적 구현 상태와 구조를 정의하는 단일 진실 공급원(SSOT)입니다. v3부터는 Goose 기반의 Recipe 체제를 완전히 탈피하여 Gemini Native의 Meta-Harness 구조로 전환되었습니다.

## 1. 아키텍처 패러다임 전환 (Meta-Harness)
- **Brain/Hand Decoupling**: Anthropic의 Meta-Harness 철학을 계승하여, 추론을 담당하는 **Brains**(.gemini/agents)와 실행을 담당하는 **Hands**(.gemini/skills + mcp-servers)를 완전히 분리했습니다.
- **Supervisor Orchestration**: 메인 Gemini 세션(Supervisor)이 복잡한 작업을 연구(Researcher), 구현(Implementer), 검증(Reviewer), 기록(Archivist) 에이전트에게 전략적으로 위임합니다.
- **Session Evidence Store**: `telemetry/logs/harness_activity.md`를 단순한 텍스트 로그가 아닌, 복구 가능한 실행 이력(Append-only Event Stream)으로 취급합니다.

## 2. 하드웨어 및 모델 정책 (Gemini 3.1 & Gemma 4)
- **대상 하드웨어**: MacBook Pro M3 Pro (36GB RAM 권장)
- **워커 모델**: `<!--VAR:OLLAMA_MODEL_NAME-->gemma-4-26B-A4B-it-GGUF<!--/VAR-->` (Ollama 기반)
- **Performance Proxy**: `scripts/ollama_proxy.py`에서 Gemma 4의 Tool-call을 실시간 인터셉트하여 파싱 오버헤드 및 `thinking` 필드 노이즈를 제거합니다.
- **Native Context Management**: `output_compactor.py`가 200자 미만 tiny payload에 대한 Zero-Overhead 경로를 제공하며, 정규식 최적화를 통해 기존 대비 40% 빠른 속도로 로그를 압축합니다.

## 3. 프로젝트 구조 (Directory Map)
```text
Angella/
├── GEMINI.md                   # Relentless Success Loop 및 Surgical Context 프로토콜
├── .gemini/                    # Meta-Harness v3.1 코어
│   ├── agents/                 # Boris Protocol이 내재화된 Brains
├── knowledge/                  # 공유 wiki 및 SQLite FTS5 인덱스
├── mcp-servers/                # SQLite 기반의 고성능 Hands
│   ├── code_graph_ops.py       # AST 기반 코드 의존성 그래프 (SQLite)
│   ├── knowledge_index.py      # 지식 검색 가속기 (SQLite FTS5)
│   ├── scion_coordination_ops.py # 원자적 스웜 조정 (SQLite)
│   └── utils/                  # 공통 유틸리티 격리 (common.py 등)
└── scripts/
    ├── graph_watchdog.py       # 백그라운드 실시간 인덱싱 (Pre-computing)
    └── ollama_proxy.py         # 실시간 응답 보정 및 Tool-call 추출
```

## 4. 핵심 메커니즘
- **Relentless Success Loop**: `Implementer`가 테스트 100% 통과 시까지 자율적으로 수정/재시도를 반복하며, `Reviewer`는 성능 수치(Latency/Memory)를 데이터로 증명해야 승인합니다.
- **Surgical Context (Blast Radius)**: `code_graph_ops`를 통해 수정 영향 범위 내의 파일만 'File Suggestion'으로 AI에게 제공하여 토큰 효율을 극대화합니다.
- **Pre-computing Upfront**: `graph_watchdog.py`가 파일 변경을 감지하여 백그라운드에서 SQLite 인덱스를 즉시 갱신, 추론 시 지연 시간을 최소화합니다.

## 5. CI/CD & 하네스 안정성 (Hardening)
- **Environment Parity**: `scripts/run-docker-tests.sh`를 통해 로컬에서도 GitHub Actions와 동일한 Ubuntu 24.04 환경의 검증이 가능합니다.
- **Sync-on-Commit**: `.githooks/pre-commit`이 `sync_project_vars.py`를 강제 실행하여 설정값과 에이전트 지침/문서 간의 불일치를 사전에 차단합니다.
- **Fail-Fast & Traceability**: CI 실패 시 상세 환경 덤프와 `set -x` 트레이스를 통해 즉각적인 디버깅 정보를 제공합니다.
