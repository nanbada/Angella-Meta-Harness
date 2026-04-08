# Angella Architecture Snapshot (v2)

이 문서는 Angella 하네스의 현재 기술적 구현 상태와 구조를 정의하는 단일 진실 공급원(SSOT)입니다.

## 1. 아키텍처 패러다임 전환
- **Personal Agent & LLM-Wiki**: 정형화된 테스트 기반의 Meta-Loop에서 탈피하여, 에이전트가 스스로 지식(Wiki)을 관리하고 OS 컨텍스트와 연동되는 유연한 체제로 전환되었습니다.
- **Token Efficiency**: 160KB 이상의 레거시 코드를 제거하고 `output_compactor`를 도입하여 컨텍스트 효율을 극대화했습니다.

## 2. 하드웨어 및 모델 정책 (Gemma 4 + MLX)
- **대상 하드웨어**: MacBook Pro M3 Pro (36GB RAM 권장)
- **워커 모델**: `mlx-community/gemma-4-31b-it-4bit` (TurboQuant 최적화)
- **Tool-calling 보정**: Gemma 4의 네이티브 태그 파싱 오류를 하네스 단(`tool_parser_wrapper.py`)에서 가로채어 보정합니다.

## 3. 프로젝트 구조 (Directory Map)
```text
Angella/
├── setup.sh                    # 통합 설치 및 점검 스크립트
├── plan.md                     # 제품 로드맵 및 비전
├── config/                     # 하네스 및 모델 설정
│   ├── harness-models.yaml     # 모델 성능 점수표
│   └── harness-profiles.yaml   # 역할별 라우팅 정책
├── knowledge/                  # LLM-Wiki (Long-term Memory)
│   ├── sources/                # 수집된 원천 자료
│   └── wiki/                   # 구조화된 지식 페이지
├── recipes/                    # 에이전트 워크플로우 (Goose Recipes)
│   ├── autoresearch-loop.yaml  # 코드 최적화 (Ratchet Loop)
│   └── personal-agent-loop.yaml# 개인 비서 및 OS 제어
├── mcp-servers/                # 전용 기능 확장 (MCP)
│   ├── llmwiki_compiler_ops.py # 위키 관리 도구
│   ├── output_compactor.py     # 로그 압축 도구
│   └── personal_context_ops.py # OS 연동 도구
└── logs/                       # 실행 결과 및 투명성 리포트
```

## 4. 로컬 캐시 및 환경 전략
- **Bootstrap Env**: `.cache/angella/bootstrap-venv` (런타임 격리)
- **Cache Paths**: `.cache/angella/uv`, `.cache/angella/pip`
- **Secrets**: `.env.agents` (Git 추적 제외, 다중 API Key 관리)

## 5. 핵심 모듈 상세
- **llm-wiki-compiler**: legacy RAG를 대체하는 현대적 마크다운 기반 지식 파이프라인.
- **output-compactor**: 긴 터미널 출력에서 핵심 에러/결과만 추출하여 토큰 소모 40% 이상 절감.
- **scion-coordination**: Google Scion 환경에서의 다중 에이전트 협업 레이어.
