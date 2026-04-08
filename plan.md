# Angella Strategic Roadmap (v2)

## 1. 제품 비전: Anatomy of the Harness
Angella는 모델 독립적인 **지능형 하네스(Harness)**를 통해 에이전트의 안정성과 지속적 성장을 보장합니다.
- **Peak Performance**: 최강의 추론 모델을 통한 전략적 의사결정.
- **Token Efficiency**: 컨텍스트 압축을 통한 경제적 자율성.
- **Persistent Memory**: 모든 경험의 자산화 (LLM-Wiki).
- **Autonomous Swarm**: Google Scion 기반의 다중 에이전트 협업.

## 2. 핵심 설계 원칙
- **Harness-First**: 인프라와 루프가 제품의 본질이다.
- **Search-First Memory**: 행동 전 과거 지식 조회를 의무화한다.
- **Ratchet Pattern**: 개선된 상태만 확정(Commit)하고 실패는 지식화한다.
- **Isolation-Enabled**: 병렬 실행 시 환경 충돌을 Scion으로 제어한다.

## 3. 단계별 실행 계획 (Roadmap)

### Phase 1~4 (완료) - 기반 구축
- `setup.sh` 자동화 및 배포 안정화.
- Git 브랜치 기반의 Ratchet Loop 안착.

### Phase 5 (진행 중) - 워커 고도화
- Local Gemma 4 + MLX + TurboQuant 최적화 연동.
- 모델 역량 기반의 지능형 하네스 카탈로그 완성.

### Phase 6 (완료) - 지식 통합
- Python 기반 legacy Meta-Loop를 NPM `llm-wiki-compiler`로 완전 대체.
- Personal Context (Calendar, Note) 연동 MCP 구축.

### Phase 7 (진행 중) - 군집 지능 (Swarm)
- **Google Scion** 개념을 참조하는 file-backed coordination MVP 구현 (`.scion/shared`, `SCION_SHARED_DIR`).
- 에이전트 간 file claim, heartbeat, broadcast, peer query를 통한 충돌 방지 조정 레이어 강화.
- 다음 단계: 실제 hub/backplane 연동과 multi-worktree orchestration 고도화.

## 4. 성공 지표
- **Repeatability**: 동일 환경 clone 후 5분 내 실행 성공.
- **Token Economy**: `token_saver` 활용 시 세션당 비용 40% 절감.
- **Knowledge Density**: 루프 100회 실행 후 생성된 유효 SOP 20개 이상.

---
상세 기술 명세 및 규격은 **[`docs/spec-contracts.md`](docs/spec-contracts.md)**를 참조하세요.
