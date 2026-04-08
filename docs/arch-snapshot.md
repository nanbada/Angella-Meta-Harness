# Angella Architecture Snapshot (v2)

이 문서는 Angella 하네스의 현재 기술적 구현 상태와 구조를 정의하는 단일 진실 공급원(SSOT)입니다.

## 1. 아키텍처 패러다임 전환
- **Personal Agent & LLM-Wiki**: 정형화된 테스트 기반의 Meta-Loop에서 탈피하여, 에이전트가 스스로 지식(Wiki)을 관리하고 OS 컨텍스트와 연동되는 유연한 체제로 전환되었습니다.
- **Token Efficiency**: 160KB 이상의 레거시 코드를 제거하고 `output_compactor`를 도입하여 컨텍스트 효율을 극대화했습니다.
- **Retired Surface Cleanup**: `meta_loop_ops.py`, `control_plane_admin.py`, `recipes/harness-self-optimize.yaml`는 2026-04-07 이후 더 이상 라이브 표면이 아닙니다.

## 2. 하드웨어 및 모델 정책 (Gemma 4 + MLX)
- **대상 하드웨어**: MacBook Pro M3 Pro (36GB RAM 권장)
- **워커 모델**: `mlx-community/gemma-4-31b-it-4bit` (TurboQuant 최적화)
- **Local Worker Contract**: MLX 경로는 `ANGELLA_LOCAL_WORKER_BACKEND=mlx`, `ANGELLA_MLX_BASE_URL`, `ANGELLA_MLX_MODEL`을 사용하는 OpenAI-compatible local endpoint topology를 canonical path로 삼습니다.
- **Tool-calling 보정**: Gemma 4의 네이티브 태그 파싱 오류를 하네스 단(`tool_parser_wrapper.py`)에서 가로채어 보정합니다.
- **Swarm Coordination Stance**: Scion은 현재 실서비스 백플레인이 아니라 Angella가 참조하는 pilot/mock coordination layer입니다.

## 3. 프로젝트 구조 (Directory Map)
```text
Angella/
├── setup.sh                    # 통합 설치 및 점검 스크립트
├── plan.md                     # 제품 로드맵 및 비전
├── config/                     # 하네스 및 모델 설정
│   ├── harness-models.yaml     # 모델 성능 점수표
│   └── harness-profiles.yaml   # 역할별 라우팅 정책
├── knowledge/                  # 공유 wiki 저장소 (현재 repo 내부 디렉터리)
│   ├── sources/                # 수집된 원천 자료
│   └── wiki/                   # 구조화된 지식 페이지
├── recipes/                    # 에이전트 워크플로우 (Goose Recipes)
│   ├── autoresearch-loop.yaml  # 코드 최적화 (Ratchet Loop)
│   └── personal-agent-loop.yaml# 개인 비서 및 OS 제어
├── mcp-servers/                # 전용 기능 확장 (MCP)
│   ├── metric_benchmark.py     # 공통 benchmark schema
│   ├── llmwiki_compiler_ops.py # 위키 관리 도구
│   ├── output_compactor.py     # 로그 압축 도구
│   ├── personal_context_ops.py # OS 연동 도구
│   ├── scion_coordination_ops.py # Scion pilot/mock coordination
│   └── tool_parser_wrapper.py  # Gemma 4 tool-call 보정
└── logs/                       # 실행 결과 및 투명성 리포트
```

## 4. 로컬 캐시 및 환경 전략
- **Shared Knowledge Path**: 현재 워크스페이스는 `knowledge/`를 repo 내부 디렉터리로 유지합니다. 핵심 요구사항은 경로 자체가 아니라 다른 프로젝트와 외부 채널(예: Telegram)에서도 접근 가능한 공유 가능성입니다. 필요하면 다시 외부 경로 symlink로 바꿀 수 있으며, 반대로 다른 소비자도 이 repo 내부 경로를 직접 참조할 수 있습니다.
- **MLX Runtime Inputs**: `setup.sh`는 `.env.mlx` 또는 `.env.mlx.example`를 bootstrap/check/install 단계에서 읽고, MLX worker 선택 시 Goose custom provider `angella_mlx_local`을 자동 렌더링합니다.
- **Bootstrap Env**: `.cache/angella/bootstrap-venv` (런타임 격리)
- **Cache Paths**: `.cache/angella/uv`, `.cache/angella/pip`
- **Secrets**: `.env.agents` (Git 추적 제외, 다중 API Key 관리)

## 5. 핵심 모듈 상세
- **llm-wiki-compiler**: legacy RAG를 대체하는 현대적 마크다운 기반 지식 파이프라인.
- **output-compactor**: 긴 터미널 출력에서 핵심 에러/결과만 추출하여 토큰 소모 40% 이상 절감.
- **personal-context**: clipboard/calendar/reminders와 raw source ingest를 통해 OS 컨텍스트를 Angella 쪽으로 가져옵니다.
- **scion-coordination**: Google Scion 개념을 참조하는 pilot/mock 협업 레이어입니다. 현재 레시피와 문서에서 참조되지만 구현은 stub 기반입니다.
- **tool-parser-wrapper**: Gemma 4의 native tool-call tag를 MCP 친화적 문자열로 정규화합니다.
