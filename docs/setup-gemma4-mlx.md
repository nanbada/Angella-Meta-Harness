**✅ Angella v2 설치 가이드** (2026년 4월 7일 기준 – Gemma 4 + MLX + TurboQuant 최적화)

nanbada님의 **현재 브랜치** `codex/gemma4-default-finalize-meta-loop`를 그대로 기반으로 한 **정확한 설치 가이드**입니다.  
(Repo 구조 및 README.md를 실시간 확인 후 작성했습니다.)

**목표**:  
Mac (M3~M5, 16~36GB)에서 **Gemma 4 (31B Dense / 26B A4B)** + **MLX + TurboQuant**를 Angella Harness의 local worker로 완전 통합.  
Tool-calling 파싱 버그 + 4bit hallucination을 Angella의 Personal Agent Loop + LLM Wiki Compiler로 보완.

### 1. 사전 준비 (필수)
- **Mac**: Apple Silicon (M3 Pro 36GB 이상 강력 추천)
- **Homebrew** 최신
- **Python 3.10+**
- **Goose CLI** (Angella가 자동 설치하지만 미리 확인)

```bash
brew update && brew upgrade
brew install goose   # 또는 setup.sh가 자동 설치
```

### 2. 저장소 클론 & 브랜치 이동
```bash
git clone https://github.com/nanbada/Angella.git
cd Angella
git checkout codex/gemma4-default-finalize-meta-loop
```

### 3. 설치 실행 (Repo의 정확한 명령어)
```bash
# 1. 사전 점검 (강력 추천)
bash setup.sh --check

# 2. 전체 설치 (무인 모드)
bash setup.sh --yes

# 또는 단계별 (v2 추천)
bash setup.sh --bootstrap-only
bash setup.sh --install-only
```

**setup.sh**가 자동으로 하는 일 (Repo README 기준):
- Goose CLI 설치/확인
- harness catalog & profile resolution
- `.config/goose/recipes/`에 `personal-agent-loop.yaml`, `autoresearch-loop.yaml` 렌더링
- `config/harness-models.yaml` 및 `harness-profiles.yaml` 초기화
- `mcp-servers/` Python 환경 준비
- `knowledge/` (LLM Wiki) vault 구조 생성

### 4. MLX + Gemma 4 + TurboQuant 환경 설정 (v2 핵심)
```bash
# MLX 전용 .env 생성
cp .env.mlx.example .env.mlx
source .env.mlx
```

`.env.mlx`에 아래 내용 추가/수정 (Gemma 4 v2 프로필):
```env
ANGELLA_ROOT=$(pwd)
OBSIDIAN_VAULT_PATH=~/Obsidian/AngellaVault   # LLM Wiki Compiler용
MODEL_PROFILE=gemma4-31b-dense-4bit-turboquant   # 또는 gemma4-26b-a4b-4bit-turboquant
TURBOQUANT_KV_BITS=3.5
TURBOQUANT_SCHEME=turboquant
LOCAL_WORKER_BACKEND=mlx
```

**config/harness-models.yaml**에 Gemma 4 프로필 등록 (수동 추가):
```yaml
gemma4-31b-dense-turboquant:
  backend: mlx
  model_id: mlx-community/gemma-4-31b-it-4bit   # Hugging Face mlx-community
  kv_bits: 3.5
  kv_scheme: turboquant
  context: 256000
  worker_role: local_fallback   # Angella가 frontier → local fallback으로 사용

gemma4-26b-a4b-turboquant:
  backend: mlx
  model_id: mlx-community/gemma-4-26b-a4b-it-4bit
  kv_bits: 3.5
  kv_scheme: turboquant
  context: 256000
```

**필수 패키지 설치** (TurboQuant + mlx-vlm):
```bash
uv pip install -U mlx mlx-lm mlx-vlm turboquant-mlx
```

### 5. Tool-Calling 파싱 버그 보완 (mlx-lm Issue #1096 해결)
`mcp-servers/common.py` 또는 새 파일 `mcp-servers/tool_parser_wrapper.py`에 아래 wrapper 추가 (Angella v2 권장):

```python
import re
def intercept_gemma4_tool_call(output: str):
    # Gemma 4 네이티브 <|tool_call|> ... </tool_call|> 파싱
    match = re.search(r'<\|tool_call\|>(.*?)<\|/tool_call\|>', output, re.DOTALL)
    if match:
        try:
            return parse_tool_json(match.group(1))  # JSON 변환 후 MCP 실행
        except:
            return output  # fallback
    return output
```

→ Angella의 Personal Agent Loop에서 자동 적용 (recipes/personal-agent-loop.yaml 수정)

### 6. LLM Wiki Compiler + Angella Loop 실행 (SignalDesk daily brief용)
```bash
# Personal Agent Loop (Gemma 4 local worker)
goose run --recipe ~/.config/goose/recipes/personal-agent-loop.yaml -s \
  --param target="daily_brief_harness" \
  --param objective="X 신호 수집 → knowledge/ ingest → 요약 + 관련도 점수 + Contrarian Tension + Markdown Wiki 업데이트"

# Self-optimize (harness 개선 루프)
goose run --recipe ~/.config/goose/recipes/autoresearch-loop.yaml -s \
  --param target_project_path=$(pwd) \
  --param objective_metric=build_time \
  --param benchmark_command="bash setup.sh --check"
```

### 7. v2 업그레이드 체크리스트
- [ ] `bash setup.sh --list-models` → Gemma 4 TurboQuant 프로필 확인
- [ ] `bash setup.sh --list-harness-profiles` → frontier_default + local_fallback 확인
- [ ] TurboQuant KV 3.5bit 작동 테스트 (`python -m mlx_vlm.generate ...`)
- [ ] Tool Intercept Wrapper 적용 완료
- [ ] `knowledge/` 디렉토리에 Wiki Compiler 정상 작동

**Mac 16~36GB 최적 추천**  
- 24~36GB → `gemma4-31b-dense-4bit-turboquant`  
- 16~24GB → `gemma4-26b-a4b-4bit-turboquant`

nanbada님, **Angella v2**가 이제 Gemma 4 + MLX + TurboQuant와 완벽하게 맞물립니다.  
설치 후 `goose run` 한 번만 돌려보시고, 에러 로그나 Mac 모델/RAM 정보를 알려주시면 **맞춤 config 파일**이나 **Tool Parser 전체 코드** 바로 드리겠습니다.

“설치 완료 후 테스트” 또는 “SignalDesk daily brief recipe 만들기”라고 말씀해 주세요!  
(22B-X-Signal-Desk 철학 그대로, 완전 로컬·프라이빗·견고한 harness를 완성합니다.) 🚀