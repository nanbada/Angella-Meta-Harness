# Angella Architecture Snapshot (v2)

이 문서는 Angella 하네스의 현재 기술적 구현 상태와 구조를 정의하는 단일 진실 공급원(SSOT)입니다.

## 1. 아키텍처 패러다임 전환
- **Personal Agent & LLM-Wiki**: 정형화된 테스트 기반의 Meta-Loop에서 탈피하여, 에이전트가 스스로 지식(Wiki)을 관리하고 OS 컨텍스트와 연동되는 유연한 체제로 전환되었습니다.
- **Token Efficiency**: 160KB 이상의 레거시 코드를 제거하고 `output_compactor`를 도입하여 컨텍스트 효율을 극대화했습니다.
- **SSOT Variables**: `config/project-vars.json`을 통해 모든 모델명과 설정을 중앙 관리합니다.

## 2. 하드웨어 및 모델 정책 (Gemma 4 + Ollama)
- **대상 하드웨어**: MacBook Pro M3 Pro (36GB RAM 권장)
- **워커 모델**: `<!--VAR:OLLAMA_MODEL_NAME-->gemma-4-26B-A4B-it-GGUF<!--/VAR-->` (Ollama 기반)
- **Local LLM 역할 분리**: 로컬 구현/수정/다단계 reasoning worker는 Gemma 4 Ollama를 우선 사용합니다.
- **Tool-calling 및 Thinking 보정**: Gemma 4의 네이티브 태그 파싱 오류 및 Ollama의 `thinking` 필드 간섭을 하네스 단(`scripts/ollama_proxy.py` 및 `tool_parser_wrapper.py`)에서 가로채어 보정합니다.
- **Dynamic Routing**: 작업 복잡도에 따라 Local(Gemma 4)과 Frontier(GPT-5.2)를 자동으로 오가는 지능형 라우팅을 지원합니다.

## 3. 프로젝트 구조 (Directory Map)
```text
Angella/
├── setup.sh                    # 통합 설치 및 점검 스크립트
├── GEMINI.md                   # 에이전트 행동 강령 및 토큰 효율화 지침
├── config/                     # 하네스 및 모델 설정
│   ├── project-vars.json       # 중앙 집중식 변수 관리 (SSOT)
│   ├── harness-models.yaml     # 모델 성능 점수표
│   └── routing-policies.yaml   # 복잡도 기반 라우팅 정책
├── knowledge/                  # 공유 wiki 저장소
│   ├── lessons.md              # 실행 로그에서 추출된 자동 진화 교훈
│   ├── sources/                # 수집 및 증류된 원천 자료
│   └── sops/                   # 운영 절차 (Scion, Compounding 등)
├── recipes/                    # 에이전트 워크플로우 (Goose Recipes)
│   ├── autoresearch-loop.yaml  # 코드 최적화 (Ratchet Loop)
│   └── archivist-loop.yaml     # 지식 정제 및 메타 러닝 루프
├── mcp-servers/                # 전용 기능 확장 (MCP)
│   ├── archivist_ops.py        # 지식 정제 및 건강 진단
│   ├── metric_benchmark.py     # 공통 benchmark schema
│   ├── llmwiki_compiler_ops.py # 위키 관리 도구
│   ├── output_compactor.py     # 로그 압축 도구 (SNR 최적화)
│   └── scion_coordination_ops.py # 분산 에이전트 조정 (Redis 지원)
└── scripts/
    ├── sync_project_vars.py    # 변수-문서 자동 동기화 툴
    └── ollama_proxy.py         # Ollama 응답 보정 프록시
```

## 4. 핵심 메커니즘
- **Ratchet Pattern**: 메트릭이 개선된 변경만 Commit하고, 실패는 지식화하여 Revert합니다.
- **Search-First Memory**: 모든 행동 전 `llmwiki`를 조회하여 과거의 실수를 반복하지 않습니다.
- **Meta-Learning**: `archivist_ops`가 주기적으로 로그를 분석하여 시스템의 '기본 규칙'을 스스로 갱신합니다.
- **Swarm Coordination**: Scion Hub를 통해 다중 에이전트 간 파일 경합을 방지하고 상태를 공유합니다.
