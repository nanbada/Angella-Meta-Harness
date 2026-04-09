# Spec: Distributed Scion Hub (v1)

## 1. 개요
현재 Scion coordination은 파일 시스템 (`.scion/shared`)을 기반으로 동작합니다. 이는 단일 머신 내 병렬 실행에는 적합하나, 다중 머신(Distributed Swarm)이나 대규모 경합 상황에서는 파일 시스템 락(Lock) 지연 및 원자성 확보의 한계가 있습니다. 이를 해결하기 위해 Redis 기반의 **Distributed Scion Hub**를 도입합니다.

## 2. 데이터 구조 (Redis Mapping)

### 2.1 Agent State
- **Key**: `scion:agent:{agent_id}`
- **Type**: Hash or JSON
- **Fields**: `status`, `intent`, `message`, `claimed_files`, `worktree`, `updated_at`, `expires_at`
- **TTL**: Redis `EXPIRE` 명령어로 자동 관리.

### 2.2 File Claims (Exclusive/Authoritative)
- **Key**: `scion:claim:{path}`
- **Type**: Hash
- **Fields**: `agent_id`, `mode`, `intent`, `message`, `exclusions`, `claimed_at`, `expires_at`
- **TTL**: 에이전트 Heartbeat와 동기화.

### 2.3 Worktree Reservations
- **Key**: `scion:worktree:{branch}`
- **Type**: Hash
- **Fields**: `agent_id`, `path`, `repo_root`, `base_branch`, `head_sha`, `clean`

### 2.4 Events & Broadcasts
- **Key**: `scion:events`
- **Type**: Stream (`XADD`)
- **Usage**: 에이전트 간 비동기 알림 및 실시간 로그.

## 3. 핵심 프로토콜 (Atomic Operations)

### 3.1 Claim Acquisition (Exclusive)
- Lua Script를 사용하여 `GET` -> `COMPARE` -> `SET` 과정을 원자적으로 수행.
- 이미 점유된 경우 즉시 에러 반환 (Hard Conflict).

### 3.2 Takeover (Hand-off)
- 소유자가 일치할 때만 Exclusion 추가 및 새 Claim 생성을 단일 트랜잭션(`MULTI`)으로 처리.

### 3.3 Heartbeat & Pruning
- Redis `EXPIRE`를 활용하여 `scion_prune_stale` 의존도를 낮춤.
- 만료된 키는 `EXPIRED` 이벤트를 구독하여 후속 처리 가능.

## 4. 하이브리드 지원 및 구현 상태
- `SCION_BACKEND=file` (기본값) vs `SCION_BACKEND=redis` 환경 변수로 전환 가능.
- `mcp-servers/scion_coordination_ops.py` 내부에 `ScionProvider` 인터페이스와 `FileScionProvider`, `RedisScionProvider` 구현 완료.
- Redis 사용 시 `REDIS_HOST` (기본 localhost), `REDIS_PORT` (기본 6379) 설정 필요.

## 5. 실행 계획 및 다음 과제
1. **Redis 환경 검증**: 실제 Redis 서버가 기동된 환경에서 `SCION_BACKEND=redis` 설정 후 Pilot 테스트(`scripts/test_scion_concurrency_pilot.py`) 수행.
2. **Atomic Takeover 강화**: 현재의 단순 키 삭제/생성 방식을 Lua 스크립트를 이용한 원자적 `takeover` 로직으로 고도화.
3. **Event Stream 가시화**: Redis Stream(`scion:events`)에 쌓이는 이벤트를 실시간으로 모니터링하는 경량 CLI 툴 개발.
