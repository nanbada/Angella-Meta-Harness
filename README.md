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
- **Local LLM:** `Gemma 4 26B` (MLX/Ollama 기반 로컬 및 프라이버시 작업)

## 📊 Data Segregation
- **[`knowledge/wiki/`](knowledge/wiki/)**: 프로젝트의 정제된 지식 및 SOP 저장소.
- **[`knowledge/research/`](knowledge/research/)**: 외부 연구 자료 및 성능 개선 데이터.
- **[`telemetry/`](telemetry/)**: 실행 로그(`logs/`) 및 에러 패턴(`errors/`)을 지식 베이스와 분리하여 관리.

## 🧠 Brains (.gemini/agents)
Angella v3는 작업 성격에 따라 특화된 4종의 에이전트를 보유하고 있습니다.
- **Researcher**: 전략 수립 및 과거 지식 기반 가설 생성
- **Implementer**: 고품질 코드 수정 (Atomic Surgery)
- **Reviewer**: 벤치마크 검증 및 Keep/Revert 결정
- **Archivist**: 실행 로그 분석 및 장기 교훈 추출

## 🛠️ Key Hands (MCP Servers)
- `metric-benchmark`: 성능 측정 및 결과 반환
- `llmwiki_compiler_ops`: 위키 기반 영구 기억 장치 관리
- `archivist_ops`: 지식 증류 및 연구 자료 관리
- `meta_loop_ops`: 자율 개선 루프 및 지식 승격(Optional Promotion) 제어

---
프로젝트 구조 및 상세 내용은 **[`docs/arch-snapshot.md`](docs/arch-snapshot.md)**를 참조하세요.
