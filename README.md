# Angella (v2)

MacBook Pro M3 36GB 기반 **Frontier-First Personal Agent Harness**입니다.

## 🚀 Quick Start

```bash
# 1. 환경 점검 및 설치
bash setup.sh --check
bash setup.sh --yes

# 선택: Gemma 4 + MLX local worker를 쓰려면
cp .env.mlx.example .env.mlx

# 2. API Key 설정
bash scripts/setup-vault.sh

# 3. 루프 실행
goose run --recipe ~/.config/goose/recipes/autoresearch-loop.yaml -s
```

## 📖 Documentation Map

AI 에이전트와 사용자는 목적에 따라 아래 문서를 참조하세요.

### 1. 지침 및 규격 (Reference & Specs)
- **[Harness Philosophy](knowledge/sops/harness-philosophy.md)**: Angella의 핵심 운영 철학 (Harness-First, Ratchet).
- **[Technical Specs](docs/spec-contracts.md)**: Intent/Benchmark Contract 및 Git 운영 규칙 명세.
- **[Harness Profiles](config/harness-profiles.yaml)**: 모델 선택 및 라우팅 정책 정의.

### 2. 설치 및 환경 (Setup)
- **[Gemma 4 & MLX Guide](docs/setup-gemma4-mlx.md)**: OpenAI-compatible local endpoint 기준의 Gemma 4 MLX worker 설정 가이드.
- **[Architecture Snapshot](docs/arch-snapshot.md)**: 현재 구현된 기술 스택 및 모듈 구조.

### 3. 프로젝트 관리 (Meta)
- **[Project Plan](plan.md)**: v2 비전 및 단계별 로드맵.
- **[Parity Status](docs/PARITY.md)**: 현재 구현된 기능 검증 리스트.

## 🛠️ Key Extensions (MCP)
- `metric-benchmark`: 성능 측정
- `llm-wiki-compiler`: 지식 구조화
- `output-compactor`: 토큰 효율화 (로그 압축)
- `scion-coordination`: Google Scion 기반 병렬 협업

---
프로젝트 구조 및 상세 내용은 **[`docs/arch-snapshot.md`](docs/arch-snapshot.md)**를 참조하세요.
