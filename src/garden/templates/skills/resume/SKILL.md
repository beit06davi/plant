---
description: garden 프로젝트에서 이전 작업을 이어받는다. 세션을 새로 열었거나 컨텍스트가 압축된 뒤, 폴더별 목적·최근 이력·확인할 변경을 요약해 다음 할 일을 정할 때 쓴다.
allowed-tools:
  - Bash({{garden}} *)
  - Read
---
garden 명령은 Bash 도구에서 실행한다.

요청: $ARGUMENTS

1. 요청에 특정 폴더가 있으면 `{{garden}} resume <폴더>`, 없으면 `{{garden}} resume`을 실행한다. 폴더 경로는 프로젝트 최상위 기준이다.
2. 결과를 바탕으로 짧게 정리한다.
   - 최근에 바뀐 것
   - 확인 필요 항목 (`A ← B`)
   - check 경고·오류
   - 다음에 할 일 후보. SEED 목표 순서와 `{{garden}} map --order`의 작업 순서를 참고한다
