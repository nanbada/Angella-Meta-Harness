# Angella Architecture Review: April 2026 Update

## 1. 개요 (Overview)
Angella는 단순한 AI 에이전트를 넘어, 고성능 추론과 로컬 자원(M3 MacBook) 최적화를 결합한 **"지능형 하네스(Harness)"** 시스템으로 진화했습니다. 2026년 4월 현재, 인프라의 유연성과 지식의 자가 진화 능력을 확보하는 데 집중했습니다.

## 2. 주요 아키텍처 성과 (Key Milestones)

### A. 단일 진실 공급원 (Project-Vars SSOT)
- **변화**: 하드코딩된 모델명과 설정값들을 `config/project-vars.json`으로 중앙 집중화했습니다.
- **효과**: 모델 교체 시 단 한 곳의 수정으로 모든 문서, 환경 변수 예시, 테스트 코드가 동기화(`scripts/sync_project_vars.py`)됩니다.

### B. 지능형 동적 라우팅 (Dynamic Worker Routing)
- **변화**: 작업 복잡도(`complexity: low/medium/high`) 기반의 라우팅 레이어를 구축했습니다.
- **효과**: 단순 작업은 로컬 모델(Gemma 4)로, 고난도 설계는 프론티어 모델(GPT-5.2)로 자동 배분하여 토큰 비용을 획기적으로 절감합니다.

### C. 아키비스트 2.0 및 메타 러닝 (Self-Evolving Knowledge)
- **변화**: 지식 정제(`distill`), 건강 진단(`health_check`), 할루시네이션 검증(`reconciliation`), 교훈 추출(`distill_lessons`) 도구를 통합했습니다.
- **효과**: 실행 로그에서 성공/실패 패턴을 스스로 학습하여 `lessons.md`를 진화시키고, 이를 에이전트 프로토콜(`GEMINI.md`)에 강제 적용했습니다.

### D. 확장 가능한 코디네이션 (Distributed Scion Hub)
- **변화**: `ScionProvider` 추상화를 통해 파일 기반에서 Redis 기반으로 백엔드 교체가 가능한 구조를 완성했습니다.
- **효과**: 다중 에이전트 환경에서 원자적(Atomic) 락과 실시간 이벤트 스트리밍이 가능한 분산 Swarm의 토대를 마련했습니다.

## 3. 현시점의 강점 및 약점 (SWOT)

| 강점 (Strengths) | 약점 (Weaknesses) |
| :--- | :--- |
| MCP 기반의 완벽한 기능 모듈화 | 복잡한 Bash 테스트의 유지보수 난이도 |
| `output_compactor`를 통한 높은 SNR | Redis 백엔드의 실전 부하 테스트 미비 |
| 자가 진화하는 `lessons.md` 기반 메타 러닝 | 정적 난이도 평가 로직의 한계 |

## 4. 다음 세션 권장 과제 (Next Actions)

1.  **[품질] 테스트 프레임워크 현대화**: `test_setup_flows.sh` 등 Bash 기반 테스트를 `pytest`로 마이그레이션하여 CI 안정성 강화.
2.  **[성능] Redis 실전 연동**: `SCION_BACKEND=redis` 환경에서 다중 에이전트 경합 시나리오 검증 및 Lua 스크립트 기반 원자성 고도화.
3.  **[지능] 의미론적 메모리 검색**: `lessons.md`의 내용을 Vector DB화하여, 작업 문맥에 맞는 최적의 교훈만 검색하여 주입하는 로직 구현.

---
**Last Updated**: 2026-04-09
**Status**: Stable, Ready for Scaling.
