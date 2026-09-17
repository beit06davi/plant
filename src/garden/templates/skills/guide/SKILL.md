---
description: garden 형식(SEED.md·NODE.md·[garden] 블록)이 있는 프로젝트에서 작업을 시작할 때, SEED를 보고 폴더 카드를 쓸 때, 다른 에이전트에게 일을 넘기기 전에 읽는다. 형식, 위계 읽는 법, 카드 쓰는 법, 명령을 담는다.
allowed-tools:
  - Bash({{garden}} *)
  - Read
  - Grep
  - Glob
---
# garden 형식 안내

garden은 폴더 구조에 목표와 개념을 적어 두는 형식이다. 에이전트가 하나든 여럿이든 같은 파일을 읽는다.
명령은 Bash 도구에서 `{{garden}} <명령>`으로 실행한다.

## 구조

```
SEED.md                 최상위 목표. 목표는 위에 있을수록 우선
<폴더>/NODE.md          그 폴더의 카드
<폴더>/<하위>/NODE.md   하위 카드. 가장 가까운 상위 카드가 부모
<폴더>/HISTORY.md       변경 이력 (garden log가 쓴다)
```

- 카드 id는 폴더 경로다 (예: `backend/booking`).
- 카드가 없는 하위 폴더의 파일은 가장 가까운 상위 카드에 속한다.

## 카드

```markdown
---
purpose: 좌석 예약의 중복을 막는다
why: 예약 판단을 한곳에 모아 화면이 규칙을 모르게 한다
serves: [G1]
priority: 1
needs: [backend/db]
provides: 좌석 상태 목록 (id, zone, status)
---
본문은 자유롭게 쓴다. 이 폴더에서 지킬 것, 끝났다고 볼 기준, 메모 등.
```

| 칸 | 뜻 | 필수 |
|---|---|---|
| purpose | 이 폴더가 있는 이유 한 줄 | 예 |
| why | 왜 따로 나눴는지 | 권장 (없으면 check 경고) |
| serves | 섬기는 SEED 목표 id | 예 |
| priority | 같은 부모 아래 형제 중 순서. 1이 먼저·더 중요 | |
| needs | 먼저 있어야 하는 폴더. 작업 순서가 된다 | |
| provides | 다른 폴더에 내주는 것 (형식·결과물 요약) | |

다른 칸을 더해도 된다. garden은 모르는 칸을 무시한다.

## 위계 읽는 법

- **세로**: SEED > 상위 폴더 > 하위 폴더. 하위 폴더는 상위 폴더의 목적을 나눠 맡는다.
- **형제**: priority가 작을수록 먼저, 더 중요하다. 같은 부모 아래에서만 비교한다.
- **순서**: A needs B면 B가 먼저다. `{{garden}} map --order`가 단계별로 보여준다.
- **충돌**: 목표가 부딪히면 SEED에서 위에 있는 목표를 따른다.

## SEED를 보고 카드 쓰기

1. `SEED.md`를 읽는다. 목표 순서, 구조 원칙, 비목표를 확인한다.
2. `{{garden}} map`으로 현재 카드와 카드 없는 최상위 폴더를 본다.
3. 최상위 폴더부터 카드를 쓴다. 한 폴더가 여러 목적을 섞고 있으면 하위 폴더로 나눌지 정한다.
4. 카드마다:
   - purpose는 "무엇이 들어 있나"보다 "왜 있나"를 쓴다.
   - why는 나눈 이유다. SEED의 구조 원칙과 이어지게 쓴다.
   - serves는 그 폴더가 직접 돕는 목표만 적는다.
   - 형제끼리 priority를 매긴다. 더 중요한 목표를 섬기거나 다른 형제가 기다리는 폴더가 앞이다.
   - 다른 폴더의 결과가 있어야 하면 needs, 다른 폴더가 쓰는 결과를 만들면 provides를 적는다.
5. `{{garden}} add <폴더> --purpose "…" --why "…" --serves G1 [--priority 1] [--needs 폴더] [--provides "…"]`로 쓰거나 NODE.md를 직접 쓴다.
6. `{{garden}} check`로 형식을 확인하고 `{{garden}} lock`으로 현재 개념을 기록한다. 이 기록이 이후 변경 알림의 기준이다.
7. 사람이 함께 있으면 `{{garden}} map --why`를 보여 주고 구조가 의도와 맞는지 묻는다.

비목표에 해당하는 폴더에는 카드를 만들지 않는다. 카드는 짧게 쓴다 (기본 60줄 이하).

## 작업 중

- 파일을 열면 그 폴더의 `[garden]` 블록이 주입된다.
  - `goal` / `higher`: 섬기는 목표와 그보다 앞선 목표
  - `lineage` / `why`: SEED부터 이 폴더까지, 이 폴더를 나눈 이유
  - `order`: 형제 중 위치
  - `needs` / `provides` / `needed by`: 먼저 필요한 것, 내주는 것, 이 폴더를 기다리는 곳
  - `notes`: 카드 본문 · `check`: 확인할 변경
- 이 블록이 이 위치에서 일하는 이유다. 요청이 블록의 목적이나 목표와 어긋나면 먼저 묻는다.
- 더 필요하면 `{{garden}} context <폴더> --detail full`, 전체 구조는 `{{garden}} map --why`.
- 카드의 purpose·why·provides를 바꾸면, 그 폴더를 needs로 가진 폴더에 알림이 간다.
- `[garden] 확인 필요`의 `A ← B`는 A가 필요로 하는 B의 개념이 바뀌었다는 뜻이다. A에 영향이 있는지 보고, 필요하면 고친 뒤 `{{garden}} ack A --from B --note "…"`.
- 의미 있는 변경은 `{{garden}} log <폴더> "<변경>" --why "<이유>"`로 남긴다.
- 세션을 이어받으면 `{{garden}} resume`부터 본다.

## 이 형식이 정하지 않는 것

검증을 얼마나 엄격히 할지, 어느 에이전트가 어느 폴더를 맡을지, 무엇을 완료로 볼지는 이 프로젝트의 에이전트가 정한다. 정했다면 해당 카드 본문에 적어 다음 에이전트도 읽게 한다.

다른 에이전트에게 일을 넘길 때는 폴더 경로를 알려 준다. 그 에이전트도 파일을 열면 같은 블록을 받는다. 훅이 없는 환경이면 `{{garden}} context <폴더>` 출력을 프롬프트에 붙인다.

## 명령

| 명령 | 하는 일 |
|---|---|
| `init` | SEED.md, garden.yaml, CLAUDE.md 만들기 (있는 파일은 두고 빠진 것만) |
| `add <폴더> --purpose … --serves G1 [--why --priority --needs --provides]` | 카드 쓰기 |
| `check [--json]` | 형식 검사 (0 정상, 1 경고·확인 필요, 2 오류) |
| `map [--why \| --order \| --mermaid]` | 구조 보기 |
| `trace <폴더>` | SEED부터 그 폴더까지의 계보 |
| `context <폴더> [--detail none\|concept\|full] [--budget N] [--json]` | 주입 블록을 직접 출력 |
| `lock [--missing] [--force]` | 현재 개념 기록 |
| `ack <폴더> --from <폴더> \| --all [--note …]` | 변경 확인 처리 |
| `log <폴더> "<변경>" [--why … --evidence …]` | 이력 남기기 |
| `resume [폴더]` | 이어받기 요약 |
