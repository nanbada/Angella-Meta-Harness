# SOP: Knowledge Compounding and Maintenance

본 문서는 Angella 하네스의 지능형 성장을 위해 외부 인사이트(Spisak/Karpathy)를 반영한 지식 복리 성장 및 관리 절차를 정의합니다.

## 1. 지식 계층 (The Hierarchy of Truth)
모든 지식은 아래 계층을 따르며, 상위 계층은 하위 계층을 근거로 삼아야 합니다.
1. **Raw Layer (`raw/`)**: 불변의 진실. 원문 데이터, 로그 원본, 벤치마크 결과.
2. **Processed Layer (`processed/`)**: 정제된 데이터. Chunking 및 메타데이터 태깅 완료 상태.
3. **Wiki Layer (`wiki/`, `sops/`)**: 파생된 지식. AI가 분석하고 요약한 실행 가능한 가이드.

## 2. 복리 성장 루프 (Compounding Loop)
매 턴 또는 세션 종료 시 아래 과정을 통해 지식을 강화합니다.
- **Capture**: 에이전트의 추론 결과나 새로운 발견을 `outputs/` 또는 `logs/`에 저장합니다.
- **Distill**: 저장된 결과에서 영속적 가치가 있는 패턴(성공/실패)을 추출합니다.
- **Merge**: 추출된 패턴을 기존 `wiki/` 또는 `sops/`에 병합합니다. (전체 재생성 금지, Incremental Diff 사용)

## 3. 아키비스트(Archivist)의 직무
'아키비스트' 루프는 주기적으로 지식 저장소의 건강 상태를 점검합니다.
- **Contradiction Detection**: 서로 모순되는 가이드나 지식을 식별하고 플래그를 세웁니다.
- **Source Validation**: 근거(`raw`)가 없는 주장을 식별하여 보완을 요청합니다.
- **Orphan Node Cleanup**: 연결되지 않은 고립된 지식 노드를 적절한 주제에 링크합니다.
- **Density Control**: 중복되거나 정보 밀도가 낮은 문서를 병합하여 토큰 효율을 높입니다.

## 4. 운영 원칙
- **Human-in-the-loop**: 중요한 SOP 변경이나 모순 해결은 최종적으로 인간의 검토를 거칩니다.
- **Search-First**: 새로운 시도 전 반드시 기존 지식을 조회하여 중복 작업을 방지합니다.
- **Evidence-Only**: 모든 지식 기술 시 반드시 `Evidence: path/to/source` 형식을 통해 출처를 명시합니다.
