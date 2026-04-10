# Angella (v3) - Meta-Harness

MacBook Pro M3 36GB 기반 **Meta-Harness Architecture**를 적용한 차세대 Personal Agent Harness입니다. Anthropic의 Brain/Hand 분리 철학을 통해 무한히 진화하는 에이전트 환경을 제공합니다.

## 🚀 Quick Start

```bash
# 1. 환경 점검 및 설치 (Meta-Harness 최적화)
bash setup.sh --check
bash setup.sh --yes

# 2. 선택: Gemma 4 + Ollama local worker를 쓰려면
cp .env.mlx.example .env.mlx
# Ollama proxy 실행 (Ollama의 'thinking' 필드 간섭 방지)
python3 scripts/ollama_proxy.py &

# 3. 에이전트 위임 (Meta-Harness 실행)
# 별도의 Recipe 파일 없이 Gemini 네이티브 세션에서 지시를 내립니다.
gemini "[Task Instruction]"
```

기본 knowledge source root는 repo 내부 [`knowledge/sources/`](knowledge/sources)입니다. 모든 실행 이력은 [`knowledge/log.md`](knowledge/log.md)에 이벤트 스트림으로 기록됩니다.

## 🧠 Brains (.gemini/agents)
Angella v3는 작업 성격에 따라 특화된 4종의 에이전트(Brains)를 보유하고 있습니다.
- **Researcher**: 전략 수립 및 과거 지식 기반 가설 생성
- **Implementer**: 고품질 코드 수정 (Atomic Surgery)
- **Reviewer**: 벤치마크 검증 및 Keep/Revert 결정
- **Archivist**: 실행 로그 분석 및 장기 교훈 추출

## 📖 Documentation Map

### 1. 지침 및 규격 (Reference & Specs)
- **[GEMINI.md](GEMINI.md)**: Supervisor 운영 프로토콜 및 에이전트 행동 강령 (필독).
- **[Harness Philosophy](knowledge/sops/harness-philosophy.md)**: Angella의 핵심 운영 철학 (Harness-First, Ratchet).
- **[Technical Specs](docs/spec-contracts.md)**: Intent/Benchmark Contract 명세.

### 2. 설치 및 환경 (Setup)
- **[Architecture Snapshot](docs/arch-snapshot.md)**: Meta-Harness 모듈 구조 및 Brain/Hand 분리 설계.
- **[Gemma 4 & Ollama Guide](docs/setup-gemma4-ollama.md)**: 로컬 워커 설정 가이드.

## 🛠️ Key Hands (MCP Servers)
- `metric-benchmark`: 성능 측정 및 결과 반환
- `llm-wiki-compiler`: 위키 기반 영구 기억 장치
- `output-compactor`: 컨텍스트 SNR 최적화 (로그 요약)
- `scion-coordination`: Swarm 협업 및 리소스 경합 방지

---
프로젝트 구조 및 상세 내용은 **[`docs/arch-snapshot.md`](docs/arch-snapshot.md)**를 참조하세요.
