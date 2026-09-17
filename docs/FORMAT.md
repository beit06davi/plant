# garden 형식

garden 0.4 기준입니다. 도구 없이 이 문서만 보고도 파일을 쓰고 읽을 수 있게 적었습니다.

## 1. 파일

| 파일 | 위치 | 누가 쓰나 | 커밋 |
|---|---|---|---|
| `SEED.md` | 프로젝트 최상위 | 사람 (에이전트가 도움) | O |
| `garden.yaml` | 프로젝트 최상위 | 사람 | O |
| `NODE.md` | 카드를 둘 폴더 | 에이전트·사람 | O |
| `HISTORY.md` | 카드가 있는 폴더 | `garden log`, `garden ack` | O |
| `.garden/concept.lock` | 최상위 | `garden lock`, `garden ack` | O |
| `.garden/cache/` | 최상위 | 훅 | X |

프로젝트 루트는 `garden.yaml`이 있는 가장 가까운 상위 폴더입니다(없으면 `SEED.md`).

## 2. SEED.md

```markdown
---
project: studycafe            # 선택
---
# SEED

## 존재 이유
…

## 목표 (위에 있을수록 우선)
- G1: 이중 예약이 없다 — 측정 기준: 동시 예약 테스트 통과
- G2: 이용자가 3초 안에 빈 좌석을 찾는다

## 구조 원칙 (폴더를 이렇게 나누는 이유)
- 예약 규칙은 한곳에 두고, 화면은 그 결과만 받아 쓴다

## 비목표
- 결제 기능 직접 구현
```

- **목표**: `- G<숫자>: <내용>` 줄. 적힌 순서가 우선순위입니다. `— 측정 기준:` 뒤는 확인 방법입니다.
- 목표가 하나 이상 있어야 합니다.
- `## 구조 원칙` 절의 항목은 `garden map --why`에 나옵니다.
- 나머지 절은 자유입니다.

## 3. NODE.md (카드)

```markdown
---
purpose: 좌석 예약의 중복을 막는다
why: 예약 판단을 한곳에 모아 화면이 규칙을 몰라도 되게 한다
serves: [G1]
priority: 1
needs: [backend/db]
provides: 좌석 상태 목록 (id, zone, status)
---
본문 (자유)
```

| 칸 | 형식 | 규칙 |
|---|---|---|
| `purpose` | 문자열 | 필수. 한 문장 (120자 넘으면 경고) |
| `why` | 문자열 | 없으면 경고. 이 폴더를 따로 나눈 이유 |
| `serves` | 목표 id 목록 | 필수. SEED에 있는 id여야 함 |
| `priority` | 1 이상의 정수 | 선택. 같은 부모 아래에서 작을수록 먼저. 겹치면 경고 |
| `needs` | 폴더 경로 목록 | 선택. 카드가 있는 폴더여야 함. 자기 자신·순환 금지 |
| `provides` | 문자열 | 선택. 다른 폴더가 쓰는 결과의 요약 |

- 그 밖의 칸은 garden이 읽지 않고 그대로 둡니다.
- 본문은 자유입니다. 이 폴더의 규칙, 완료 기준, 메모 등 프로젝트가 정한 내용을 적습니다.
- 카드 길이 기준은 60줄입니다(`garden.yaml`에서 변경).

### id와 위계

- 카드 id는 프로젝트 루트 기준 폴더 경로입니다: `backend/booking`.
- 부모는 가장 가까운 상위 폴더의 카드입니다. 없으면 SEED입니다.
- 카드가 없는 폴더의 파일은 가장 가까운 상위 카드에 속합니다.
- 프로젝트 최상위에는 `NODE.md`를 두지 않습니다(SEED가 그 역할).
- 폴더를 옮기면 id가 바뀝니다. 그 폴더를 가리키는 `needs`도 고쳐야 합니다.

### 순서

| 관계 | 근거 | 읽는 법 |
|---|---|---|
| 세로 | 폴더 중첩 | 하위 폴더는 상위 폴더의 목적을 나눠 맡는다 |
| 형제 | `priority` | 같은 부모 아래에서 1이 먼저. 없는 카드는 뒤, 그 안에서는 이름순 |
| 작업 순서 | `needs` | A needs B → B가 먼저. `garden map --order`가 단계로 묶는다 |
| 목표 | `serves` + SEED 순서 | 목표가 부딪히면 SEED에서 위에 있는 목표를 따른다 |

## 4. 주입 블록

`garden context <폴더>`가 출력하고, Claude Code 훅이 파일을 열 때 넣는 텍스트입니다.

| 줄 | 내용 | 없을 때 |
|---|---|---|
| `[garden] <id> — <purpose>` | 머리 | |
| `goal:` | serves 목표와 내용 | |
| `higher:` | 그보다 앞선 SEED 목표 | G1만 섬기면 생략 |
| `lineage:` | SEED부터 이 폴더까지, 상위 카드의 purpose | |
| `why:` | 이 폴더를 나눈 이유 | why가 없으면 생략 |
| `order:` | 형제 중 위치 | 형제가 없으면 생략 |
| `needs:` | 먼저 필요한 폴더 | |
| `provides:` | 이 폴더가 내주는 것 | |
| `needed by:` | 이 폴더를 needs로 가진 폴더 | |
| `notes:` | 카드 본문 (600자까지) | |
| `check:` | 확인 대기 중인 변경 | |
| `more:` | 더 볼 명령 | |

관련 폴더(`needs`, `needed by`)의 정보량은 `context` 설정을 따릅니다.

| 값 | 관련 폴더마다 |
|---|---|
| `none` | 폴더 id만 |
| `concept` (기본) | purpose, 주는 것(provides) |
| `full` | 위에 더해 why와 본문 앞부분 |

글자 수가 `context_budget`(기본 1500, `full`은 두 배)을 넘으면 먼 상위 카드의 purpose → `more` → `needed by` → `higher` → `order` → `notes` 순서로 줄이고, 그래도 넘으면 뒤를 자릅니다.

## 5. 변경 알림

- **개념**: 카드의 purpose, why, provides. 공백과 `**` 강조는 무시합니다. 본문과 priority는 개념이 아닙니다.
- `garden lock`은 `needs` 연결마다 "A가 마지막으로 확인한 B의 개념"을 `.garden/concept.lock`에 적습니다.
- B의 개념이 기록과 달라지면 A에 **확인 필요**가 생깁니다. `check`, 주입 블록의 `check:`, 카드 수정 직후 알림에 나옵니다.
- A 쪽에서 영향을 확인했으면 `garden ack A --from B`. A의 `HISTORY.md`에 한 줄이 남습니다.
- 연결이 새로 생기거나 없어지면 `garden lock --missing`으로 정리합니다. `garden add`는 lock이 있으면 새 연결을 바로 기록합니다.

### HISTORY.md

```markdown
# HISTORY — backend/booking

- 2026-09-20 | 변경: 종료 시각 추가 | 이유: 곧 빌 자리 표시 | 목표: G1 | 근거: service.py
```

## 6. check

종료 코드: 0 정상 · 1 경고나 확인 필요 · 2 오류.

| 수준 | 코드 |
|---|---|
| 오류 | `config` `seed-missing` `seed-parse` `seed-no-goals` `root-card` `card-parse` `purpose-missing` `serves-missing` `serves-invalid` `priority-invalid` `needs-self` `needs-missing` `needs-cycle` `lock-parse` |
| 경고 | `seed-long` `purpose-long` `why-missing` `card-long` `priority-duplicate` `edge-unlocked` `edge-stale` `parent-changed` |
| 확인 필요 | `change-pending` |

## 7. garden.yaml

```yaml
project: studycafe
context: concept               # none | concept | full
context_budget: 1500           # 주입 블록 최대 글자 수
card_max_lines: {node: 60, seed: 80}
ignore: [".git/**", ".garden/**", ".claude/**", "node_modules/**", ".venv/**", "**/__pycache__/**"]
```

`ignore`에 걸리는 폴더의 카드는 읽지 않고, 그 안의 파일에는 주입하지 않습니다.

## 8. Claude Code 훅

| 이벤트 | 대상 도구 | 하는 일 |
|---|---|---|
| PreToolUse | Read, Edit, Write, MultiEdit, NotebookEdit, Grep, Glob | 대상 경로의 카드 블록을 `additionalContext`로 넣는다. 세션·에이전트별로 같은 블록은 한 번만 |
| PostToolUse | Edit, Write, MultiEdit | `NODE.md` 수정 → 그 카드의 오류·경고, 이 카드를 needs로 가진 폴더의 확인 필요. `SEED.md` 수정 → serves 점검 |
| PostCompact | | 주입 기록을 지워 다음에 다시 넣게 한다 |

훅은 도구 호출을 막지 않습니다. 실패해도 종료 코드 0으로 끝납니다.
