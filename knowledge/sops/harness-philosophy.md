# SOP: Angella Harness Philosophy (Anatomy of the Harness)

Angella의 모든 에이전트 활동은 이 하네스 철학을 최우선으로 준수해야 합니다.

## 1. Harness-First
- 모델은 언제든 교체 가능한 부품입니다.
- 제품의 본질은 **측정(Benchmark)**, **기억(Wiki)**, **복구(Revert)**를 관리하는 하네스 계층에 있습니다.

## 2. Search-First Memory
- 모든 실행(Act) 전에 `llmwiki_query`를 통해 과거의 동일 기술 스택 실패 사례나 성공한 SOP를 먼저 확인합니다.
- 중복된 시행착오를 줄여 토큰 효율을 극대화합니다.

## 3. Ratchet (역행 방지)
- 메트릭이 확실히 개선된 결과만 `keep` 합니다.
- 개선되지 않은 시도는 `revert` 하되, 시도했던 가설과 실패 원인은 `llmwiki`에 저장하여 지식화합니다.

## 4. Token Efficiency (Context Control)
- 긴 로그나 원문 파일 전체를 읽는 것을 지양합니다.
- `output_compactor`를 사용하여 핵심 요약 정보만 컨텍스트에 담아 LLM의 집중도를 높입니다.

## 5. Swarm Coordination (Isolation)
- 다중 에이전트 실행 시 **Google Scion**의 원칙에 따라 독립된 Worktree에서 동작합니다.
- 대규모 수정 전 동료 에이전트와의 충돌 여부를 `scion_query_peers`로 확인합니다.
