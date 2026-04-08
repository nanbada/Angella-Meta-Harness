# Promotion Content Quality

승격되는 SOP/skill draft는 아래 기준을 만족해야 합니다.

## SOP quality

- failure class와 objective component가 첫 화면에서 보인다
- accepted evidence summary는 한두 문장으로 압축된다
- 재사용 가능한 response pattern이 operator action으로 적힌다
- binary acceptance checks 또는 equivalent validation이 들어간다
- reuse boundary / escalation boundary가 들어간다

## Skill quality

- 어떤 component나 상황에서 쓰는지 먼저 보인다
- resolved provider/model이 기록된다
- execution pattern은 반복 가능한 작업 순서로 적힌다
- avoid/non-goal 조건이 함께 적힌다
- validation 항목이 반드시 포함된다

## Dedupe rule

- 같은 run fingerprint면 addendum을 다시 붙이지 않는다
- 기존 list item과 동일한 bullet은 새 addendum에 중복 기록하지 않는다
- 단순 summary 반복보다 새 signal, check, boundary가 생겼을 때만 addendum이 커지게 한다

## Verification-only report quality

- `runs/<run_id>/report.md` 는 사람이 바로 읽을 수 있는 markdown 형식이어야 한다
- run id, objective component, benchmark command, metric, summary가 모두 보인다
- finalize skip reason이 명시된다
- export / knowledge promotion이 실행되지 않았다는 점이 분명히 드러난다

## Accepted proof PR rule

- accepted meta-loop export PR 첫 문단에는 `Reference proof only. Not intended for merge.` 가 들어간다
- proof PR 본문에는 primary structure PR 링크가 들어간다
- proof PR은 merge 대상이 아니라 accepted-run artifact 보존용이라는 점이 명확해야 한다
