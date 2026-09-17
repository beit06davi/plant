---
description: garden 구조를 심는다. SEED.md가 비어 있으면 사용자와 목표를 정하고, SEED를 보고 폴더마다 NODE.md 카드를 쓴다. 새 프로젝트를 시작하거나 기존 폴더에 garden을 적용할 때 쓴다.
allowed-tools:
  - Bash({{garden}} *)
  - Read
  - Grep
  - Glob
  - Write
  - Edit
---
garden 명령은 Bash 도구에서 `{{garden}} <명령>`으로 실행한다. 형식이 처음이면 `{{guide}}`를 먼저 읽는다.

참고 요청: $ARGUMENTS

## 1. SEED

1. `SEED.md`가 없으면 `{{garden}} init`을 실행한다.
2. SEED.md가 틀(`<…>`)만 있으면 사용자에게 한 번에 한두 개씩 묻는다.
   - 이 프로젝트가 왜 있나
   - 목표를 중요한 순서로 (G1이 가장 중요). 각 목표를 어떻게 확인하나
   - 폴더를 어떤 기준으로 나누고 싶나
   - 하지 않을 것
3. 답을 SEED.md에 쓰고 보여 준다. 목표 순서는 사용자가 정한다.

## 2. 카드

1. `{{garden}} map`으로 지금 구조를 본다. 필요하면 폴더 안의 파일을 훑어 무엇이 있는지 확인한다.
2. 카드를 쓸 폴더와 칸(purpose, why, serves, priority, needs, provides)을 트리로 정리한다.
3. 사용자가 함께 있으면 트리를 먼저 보여 주고 확인받는다.
4. 상위 폴더부터 `{{garden}} add`로 쓴다. needs 대상 카드가 먼저 있어야 한다.
5. `{{garden}} check`가 0이 될 때까지 고친다. 경고는 이유가 있으면 남겨도 된다.
6. `{{garden}} lock`으로 개념을 기록한다.
7. `{{garden}} map --why`와 `{{garden}} map --order`를 보여 주고 끝낸다.

기존 파일은 옮기거나 지우지 않는다. 폴더 구조를 바꿔야 할 것 같으면 제안만 한다.
