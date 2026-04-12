# Spec: Distributed Scion Hub (v1)

## 1. 개요
현재 Scion coordination은 파일 시스템 기반 조정 레이어의 동시성 병목(Lock 지연 및 원자성 부족)을 완벽히 해결하기 위해, 다중 머신 간 병렬 쓰기 처리가 강력한 **SQLite WAL(Write-Ahead Logging)** 기반의 **High-Performance Distributed Scion Hub**로 완전히 전환되었습니다. (초기 구상되었던 Redis 기반 설계는 외부 의존성을 높이므로 폐기 및 대체되었습니다.)

## 2. 데이터 구조 (SQLite Schema)

### 2.1 Agent State (`agents` 테이블)
- **Primary Key**: `agent_id`
- **Fields**: `status`, `intent`, `message`, `claimed_files`, `worktree`, `updated_at`, `expires_at_epoch`
- **관리**: 에이전트 Heartbeat 발생 시 `ON CONFLICT DO UPDATE SET` 방식의 원자적 병합(Upsert) 수행.

### 2.2 File Claims (`claims` 테이블)
- **Primary Key**: `claimed_path`
- **Fields**: `agent_id`, `mode`, `exclusions`, `expires_at_epoch`, `metadata`
- **관리**: Exclusive 및 Takeover 모드에서 배타적 점유 권한 및 Handoff 상태 추적.

### 2.3 Worktree Reservations (`worktrees` 테이블)
- **Primary Key**: `branch`
- **Fields**: `path`, `agent_id`, `expires_at_epoch`, `metadata`

### 2.4 Events & Broadcasts (`events` 테이블)
- **Primary Key**: `id` (Auto-increment)
- **Fields**: `agent_id`, `kind`, `message`, `timestamp`, `payload`
- **관리**: 에이전트 간 비동기 알림 및 실시간 로그/메트릭 기록을 위한 Append-only 이벤트 템포럴 보관 모델.

## 3. 핵심 프로토콜 (Atomic Operations)

### 3.1 Claim Acquisition (Exclusive)
- SQLite 내부 `transaction`과 `UNIQUE` 제약 조건을 바탕으로 배타적 점유 충돌을 방지합니다.

### 3.2 Takeover (Hand-off)
- 소유자가 일치할 때 권한을 이양하는 Exclusion 추가/삭제 과정의 정합성을 한 트랜잭션(`conn.commit()`) 내부에서 보장합니다.

### 3.3 Heartbeat & Pruning (`scion_prune_stale`)
- 시간 만료(expires_at_epoch)를 확인하는 전용 `DELETE FROM ... WHERE` 쿼리를 배치 실행하여 즉시 락 없이 클리어합니다.

## 4. 하이브리드 지원 및 구현 상태
- `SCION_BACKEND=file` (개발/단일 테스트용) 및 `SCION_BACKEND=sqlite` (프로덕션/하네스 전용 기본값) 환경 변수로 호환 전환이 가능합니다.
- `mcp-servers/scion_coordination_ops.py` 내부 인터페이스를 통해 동일한 기능을 수행합니다.
- 동시성 극대화를 위해 `_init_db` 실행 시 초기 연결 타임아웃 방어막과 `PRAGMA journal_mode=WAL;` 설정을 인젝트합니다.

## 5. 실행 계획 및 반영 현황
1. **SQLite 호환성 및 테스트 범용성**: `scripts/test_scion_coordination.py` 로직이 두 백엔드를 루프로 순회하며 호환성을 검증하도록 구축 완료되었습니다. **(완료)**
2. **Archivist 성능 회고 지원**: 이벤트 로그(`telemetry/logs/harness_activity.md`)에서 메트릭을 도출하여 성능 회고(`lessons.md`)를 수행하게 통합 완료되었습니다. **(완료)**
