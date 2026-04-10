# Angella Strategic Roadmap (v3)

## 1. 제품 비전: Anatomy of the Harness
Angella는 모델 독립적인 **지능형 하네스(Harness)**를 통해 에이전트의 안정성과 지속적 성장을 보장합니다.
- **Peak Performance**: Gemini 3.1 Pro 기반의 전략적 의사결정.
- **Token Efficiency**: 컨텍스트 압축 및 Gemini-Native 최적화.
- **Persistent Memory**: 모든 경험의 자산화 (LLM-Wiki).
- **Autonomous Swarm**: Google Scion 기반의 다중 에이전트 협업.

## 2. 핵심 설계 원칙
- **Harness-First**: 인프라와 루프가 제품의 본질이다.
- **Search-First Memory**: 행동 전 과거 지식 조회를 의무화한다.
- **Ratchet Pattern**: 개선된 상태만 확정(Commit)하고 실패는 지식화한다.
- **Data Segregation**: 지식(Wiki)과 운영 데이터(Telemetry)를 엄격히 분리한다.

## 3. 단계별 실행 계획 (Roadmap)

### Phase 1~7 (완료) - 기반 및 Swarm 협업 구축
- `setup.sh` 자동화, Ratchet Loop, Local Gemma 4 최적화.
- Google Scion 기반의 Swarm 조정 레이어 구현.

### Phase 8 (완료) - Meta-Harness v3 최적화 및 지식 분리
- **Gemini-Centric Strategy**: Lead(3.1 Pro) / Worker(3 Flash) 위계 확립.
- **Telemetry Separation**: 실행 로그 및 에러 데이터를 `telemetry/`로 격리.
- **Research Archive**: `knowledge/research/`를 통한 외부 연구 자료 관리.
- **Optional Promotion**: 지식의 SOP/Skill 승격을 선택적으로 제어하여 지식 밀도 유지.
- **Legacy Purge**: Goose/Apfel 기반의 낡은 유산과 중복 설정 제거.

### Phase 9 (진행 중) - 오케스트레이션 고도화 및 확장
- **Distributed Scion Hub**: Redis/Postgres 기반 전역 조정 서버 전환.
- **Dynamic Worker Routing**: 작업 난이도별 로컬/프론티어 자동 라우팅 정교화.
- **Self-Evolving Knowledge**: Archivist 루프를 통한 자동 지식 합성 및 요약 고도화.

## 4. 성공 지표
- **Repeatability**: 동일 환경 clone 후 5분 내 실행 성공.
- **Token Economy**: Gemini-Native 최적화로 세션당 비용 50% 절감.
- **Knowledge Density**: 운영 데이터 분리로 정제된 지식의 가독성 및 검색 정확도 향상.

---
상세 기술 명세 및 규격은 **[`docs/spec-contracts.md`](docs/spec-contracts.md)**를 참조하세요.
