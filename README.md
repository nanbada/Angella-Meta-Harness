# Angella (v3) - Meta-Harness

**Meta-Harness Architecture**를 적용한 차세대 Personal Agent Harness입니다. Gemini-Native 및 Brain/Hand 분리 철학을 통해 무한히 진화하는 에이전트 환경을 제공합니다.

## 🚀 Quick Start

```bash
# 1. 환경 점검 및 설치 (Meta-Harness v3 최적화)
bash setup.sh --check
bash setup.sh --yes

# 2. M3 MLX 최적화 환경 로드
source .env.mlx

# 3. 에이전트 실행 (Meta-Harness v3)
# 별도의 Recipe 파일 없이 Gemini 네이티브 세션에서 지시를 내립니다.
gemini "[Task Instruction]"
```

## 🧠 AI Strategy (Gemini-Centric)
- **Lead/Planner:** `Gemini 3.1 Pro` (최고의 추론 및 전략 수립)
- **Worker:** `Gemini 3 Flash` (초고속 코드 수정 및 도구 실행)
- **Local LLM:** `Gemma 4 31B` (Ollama/MLX 기반 로컬 주권 및 프라이버시 작업)

## 📊 Data Segregation & Performance
- **[`knowledge/wiki/`](knowledge/wiki/)**: 프로젝트의 정제된 지식 및 SOP 저장소.
- **[`telemetry/`](telemetry/)**: 실행 로그 및 성능 메트릭 격리 관리.
- **SQLite Backbone**: 코드 그래프, 지식 인덱스, 스웜 조정을 SQLite 기반의 고성능 원자적 트랜잭션으로 통합.

## 🧠 Brains (.gemini/agents)
Angella v3.1은 Boris Cherny의 'Relentless Optimization' 철학이 내재화된 4종의 에이전트를 보유합니다.
- **Researcher**: 전략 수립 및 SQLite 기반 Blast Radius 분석을 통한 정밀 컨텍스트 추출.
- **Implementer**: 테스트 100% 통과 시까지 스스로 채찍질하는 자율 수정 루프 (Boris Protocol).
- **Reviewer**: 성능 수치를 데이터로 증명(Conclusively Proven)해야만 승인하는 엄격한 검증자.
- **Archivist**: 실행 결과 분석 및 하네스 자체의 성능 회고(Performance Retrospective).

## 🛠️ Key Hands (MCP Servers)
- `code_graph_ops`: SQLite 기반 코드 의존성 및 영향 범위 분석.
- `knowledge_index`: 30,000배 빠른 SQLite FTS5 기반 지식 검색.
- `scion_coordination_ops`: SQLite 기반의 원자적 다중 에이전트 파일 점유 및 조정.
- `output_compactor`: SNR 최적화 및 Zero-Overhead 인라인 컨텍스트 주입.

---
프로젝트 구조 및 상세 내용은 **[`docs/arch-snapshot.md`](docs/arch-snapshot.md)**를 참조하세요.
