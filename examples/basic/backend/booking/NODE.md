---
purpose: 좌석 예약의 중복을 막는다
why: 예약 판단을 한곳에 모아 화면이 규칙을 몰라도 되게 한다
serves:
- G1
priority: 1
needs:
- backend/db
provides: 좌석 상태 목록 (id, zone, status)
---
## 메모
- 확정 예약은 좌석·시간마다 하나
- 취소된 예약은 좌석을 점유하지 않는다
