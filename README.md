# 🦆 Angella — M3 Autoresearch Self-Optimize Loop

MacBook Pro M3 36GB에서 [Goose](https://github.com/block/goose)를 활용한 **Karpathy Autoresearch 스타일 Self-Optimize Loop** 시스템입니다.

코드 수정 → 벤치마크 → baseline 대비 개선되면 keep(commit), 아니면 revert.  
이것을 자동으로 최대 15회 반복합니다.

Angella의 핵심은 모델 자체보다 **좋은 최적화 루프와 스캐폴딩**입니다. 현재 기본 경로는 Goose + Ollama + MCP이며, `apfel` 같은 네이티브 provider 통합은 후속 확장 대상으로 유지합니다.

## 🏗 아키텍처

```
┌──────────────────────────────────────────┐
│             Goose Agent                   │
│  Lead: Gemini 2.5 Pro (Intent/Plan)      │
│  Worker: Qwen 2.5 Coder 32B (Code/MLX)  │
├──────────────────────────────────────────┤
│                                          │
│  ┌─────────────┐    ┌─────────────────┐  │
│  │  Developer   │    │ Metric Benchmark│  │
│  │  Extension   │    │  MCP Server     │  │
│  │  (builtin)   │    │  (stdio)        │  │
│  └─────────────┘    └─────────────────┘  │
│                                          │
│  ┌─────────────────────────────────────┐ │
│  │    Obsidian Auto-Log MCP Server     │ │
│  │    (Transparency / Logging)         │ │
│  └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

## ⚡️ 빠른 시작

### 1. 환경 셋업
```bash
bash setup.sh
```

이 스크립트가 자동으로:
- Goose CLI 설치 (없으면)
- Ollama 모델 풀 (qwen2.5-coder:32b, gemma4:26b)
- MCP 실행에 사용할 Python 인터프리터 탐지 및 의존성 설치
- Goose config와 렌더된 recipe 설치
- 로그 디렉토리 생성

### 2. Gemini API Key 설정
```bash
export GOOGLE_API_KEY=your_api_key_here
# 또는 쉘 프로필에 미리 등록
# 또는
goose configure  # → Configure Providers → Google Gemini
```

### 3. Autoresearch Loop 실행
```bash
# MLX 환경변수 적용
source .env.mlx

# Ollama 서버 실행 (이미 실행 중이 아니면)
ollama serve &

# setup.sh가 생성한 렌더된 recipe로 Goose 세션 시작
goose session --recipe ~/.config/goose/recipes/autoresearch-loop.yaml
```

파라미터 입력:
- `target_project_path`: 최적화할 프로젝트 경로
- `objective_metric`: build_time / tokens_per_second / latency_ms / bundle_size
- `benchmark_command`: 벤치마크 명령어 (예: `npm run build`)

## 🎯 설계 원칙

- 요청을 바로 수정하지 않고 먼저 최적화 의도와 metric을 정리합니다.
- 각 iteration은 하나의 가설만 구현하고 metric으로 판정합니다.
- 개선되지 않으면 revert하고, 개선 근거와 diff를 로그로 남깁니다.
- 현재 지원 기능과 미래 확장 기능을 문서에서 분리합니다.

## ✅ 현재 지원 범위

- Goose를 orchestration layer로 사용
- Ollama 기반 `qwen2.5-coder:32b`, `gemma4:26b` 설치 및 실행
- benchmark MCP와 compare_metrics 기반 ratchet loop
- iteration 로그 및 final report 저장
- setup 기반 로컬 설치와 렌더된 Goose config/recipe 배포

## 🧪 후속 확장 후보

- `apfel` 기반 native provider 통합
- 역할별 provider routing
- intent clarification 강화
- transparency 로그 구조 고도화
- benchmark parser 정밀도 개선

## 📁 프로젝트 구조

```
Angella/
├── setup.sh                        # 원클릭 셋업
├── .env.mlx                        # MLX 환경변수
├── .goosehints                     # Goose 프로젝트 힌트
│
├── config/
│   ├── goose-config.yaml           # Goose config 템플릿
│   └── init-config.yaml            # Custom distro config
│
├── recipes/
│   ├── autoresearch-loop.yaml      # 메인 Autoresearch recipe
│   └── sub/
│       ├── code-optimize.yaml      # 코드 최적화 서브레시피
│       └── evaluate-metric.yaml    # 메트릭 평가 서브레시피
│
├── mcp-servers/
│   ├── metric_benchmark.py         # 범용 벤치마크 MCP
│   ├── metric_benchmark_nextjs.py  # Next.js 전용
│   ├── metric_benchmark_python.py  # Python 전용
│   ├── metric_benchmark_swift.py   # Swift 전용
│   ├── obsidian_auto_log.py        # 로그 자동 저장 MCP
│   └── requirements.txt            # Python 의존성
│
└── logs/                           # 자동 생성되는 로그 디렉토리
```

## 🔧 프로젝트별 벤치마크 MCP

특정 프로젝트 유형에 맞는 MCP 서버를 사용하려면 recipe의 extensions에서 변경하세요:

| 프로젝트 | MCP Server | Metric Key |
|----------|-----------|------------|
| Next.js | `metric_benchmark_nextjs.py` | `build_time`, `bundle_size` |
| Python/MLX | `metric_benchmark_python.py` | `tokens_per_second`, `latency_ms` |
| Swift/SwiftUI | `metric_benchmark_swift.py` | `build_time`, `latency_ms` |
| 범용 | `metric_benchmark.py` | 모든 메트릭 |

## 🔍 Intent Contract

루프를 시작하기 전에 아래 4가지는 반드시 고정하는 것이 좋습니다.

- 무엇을 최적화할지: 빌드 시간, latency, tokens/s, 번들 크기
- 어떤 명령으로 측정할지: `benchmark_command`
- 어느 수준부터 개선으로 볼지: `improvement_threshold`
- 무엇을 희생하면 안 되는지: 기능 회귀, 테스트 실패, 불필요한 리팩토링

## 🖥 M3 36GB 실전 체크리스트

- [ ] `source .env.mlx` 적용 확인
- [ ] Ollama MLX 로그에 `metal` 표시 확인
- [ ] Activity Monitor에서 unified memory **28GB 이하** 유지
- [ ] 첫 루프 전 baseline 직접 확인
- [ ] Overnight loop 추천 (15회 기준 2~4시간 소요 예상)

## 📝 로그 & Transparency

매 iteration마다 자동으로 로그가 생성됩니다:
- 위치: `./logs/Goose Logs/` (또는 Obsidian vault)
- 형식: Markdown
- 내용: iteration 번호, 메트릭, keep/revert 판정, git diff, 요약, 선택한 가설

최종 보고서는 `*-FINAL.md` 파일로 저장됩니다.

## 📄 라이선스

이 프로젝트는 개인 사용 목적입니다. Goose는 [Apache 2.0](https://github.com/block/goose/blob/main/LICENSE) 라이선스입니다.
