from pathlib import Path

import pytest
import yaml

SEED = """---
project: demo
---
# SEED

## 존재 이유
테스트용 좌석 예약.

## 목표 (위에 있을수록 우선)
- G1: 이중 예약 없는 예약 — 측정 기준: 동시 예약 테스트 통과
- G2: 3초 안에 빈 좌석 파악
- G3: 운영자용 주간 보고서

## 구조 원칙
- 데이터를 만드는 폴더가 먼저, 보여주는 폴더가 나중

## 비목표
- 결제
"""


def card(body: str = "", **meta) -> str:
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    return f"---\n{front}---\n{body}"


def base_files() -> dict[str, str]:
    return {
        "SEED.md": SEED,
        "garden.yaml": "project: demo\n",
        "backend/NODE.md": card(
            purpose="예약 도메인과 저장소", why="예약 규칙이 모든 화면의 바탕이라 가장 먼저 둔다",
            serves=["G1"], priority=1,
        ),
        "backend/booking/NODE.md": card(
            "## 규칙\n- 확정 예약은 좌석·시간마다 하나\n",
            purpose="좌석 예약의 중복을 막는다", why="예약 판단을 한곳에 모아 화면이 규칙을 모르게 한다",
            serves=["G1"], priority=1, needs=["backend/db"], provides="좌석 상태 목록 (id, zone, status)",
        ),
        "backend/booking/service.py": "x = 1\n",
        "backend/db/NODE.md": card(
            purpose="예약 데이터를 저장한다", why="저장 방식이 바뀌어도 예약 규칙이 흔들리지 않게 분리",
            serves=["G1"], priority=2, provides="예약 저장·조회 함수",
        ),
        "backend/db/store.py": "y = 1\n",
        "frontend/NODE.md": card(
            purpose="이용자 화면", why="보여주는 일은 데이터 다음 단계", serves=["G2"], priority=2,
        ),
        "frontend/seatmap/NODE.md": card(
            "## 메모\n- 모바일 우선\n",
            purpose="빈 좌석을 3초 안에 파악하게 한다", why="첫 화면에서 바로 판단하게 따로 둔다",
            serves=["G2"], needs=["backend/booking"],
        ),
        "frontend/seatmap/index.html": "<html></html>\n",
        "reports/weekly/NODE.md": card(
            purpose="운영자가 한 주 흐름을 본다", why="운영용이라 이용자 화면과 분리", serves=["G3"], needs=["backend/booking"],
        ),
        "docs/notes.md": "메모\n",
    }


def write_tree(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def tree(tmp_path) -> Path:
    return write_tree(tmp_path / "proj", base_files())
