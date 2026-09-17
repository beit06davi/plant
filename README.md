# garden

폴더 구조에 목표와 개념을 적어 두는 형식입니다.
에이전트는 파일을 열 때 **이 폴더가 왜 있는지, 어떤 목표를 섬기는지, 무엇이 먼저인지**를 함께 받습니다.
사람은 폴더 트리만 보고 무엇이 중요한지 압니다.

에이전트가 하나든 여럿이든 같은 파일을 읽습니다. 검증 강도, 담당 배분, 완료 기준은 garden이 정하지 않고, 프로젝트의 에이전트가 정합니다.

## 형식

```
SEED.md                     최상위 목표 (위에 있을수록 우선)
backend/NODE.md             폴더 카드
backend/booking/NODE.md     하위 카드 — 가장 가까운 상위 카드가 부모
backend/db/NODE.md
frontend/seatmap/NODE.md
```

```markdown
---
purpose: 좌석 예약의 중복을 막는다                     # 이 폴더가 있는 이유
why: 예약 판단을 한곳에 모아 화면이 규칙을 몰라도 되게 한다   # 따로 나눈 이유
serves: [G1]                                          # 섬기는 SEED 목표
priority: 1                                           # 형제 중 순서
needs: [backend/db]                                   # 먼저 있어야 하는 폴더
provides: 좌석 상태 목록 (id, zone, status)            # 다른 폴더에 내주는 것
---
본문은 자유. 이 폴더에서 지킬 것, 메모.
```

전체 규칙은 [docs/FORMAT.md](docs/FORMAT.md)에 있습니다. 예시는 [examples/basic](examples/basic)입니다.

## 에이전트가 받는 것

`backend/booking/service.py`를 열면 다음 블록이 대화에 들어갑니다.

```
[garden] backend/booking — 좌석 예약의 중복을 막는다
goal: G1 이중 예약이 없다
lineage: SEED > backend(예약 규칙과 저장을 맡는다) > backend/booking
why: 예약 판단을 한곳에 모아 화면이 규칙을 몰라도 되게 한다
order: backend 아래 1번째 — backend/booking(1) > backend/db(2)
needs: backend/db — 예약 데이터를 저장하고 꺼낸다 · 주는 것: 예약 저장·조회 함수
provides: 좌석 상태 목록 (id, zone, status)
needed by: frontend/seatmap — 빈 좌석을 3초 안에 찾게 한다
needed by: reports/weekly — 한 주 이용 흐름을 보여 준다
notes:
  ## 메모
  - 확정 예약은 좌석·시간마다 하나
```

- 같은 세션에서 같은 블록은 한 번만 들어갑니다. 에이전트마다 따로 셉니다.
- 관련 폴더를 얼마나 보여줄지는 `garden.yaml`의 `context`로 정합니다: `none`(이름만) · `concept`(목적·주는 것, 기본) · `full`(카드 본문까지).
- 카드의 purpose·why·provides가 바뀌면, 그 폴더를 `needs`로 가진 폴더에 확인 알림이 갑니다. 확인한 뒤 `garden ack`로 처리합니다.

## 사람이 보는 것

```
$ garden map
studycafe   G1 이중 예약이 없다 > G2 이용자가 3초 안에 빈 좌석을 찾는다 > G3 운영자가 한 주 이용 흐름을 본다
├─ backend/     G1  #1  예약 규칙과 저장을 맡는다
│  ├─ booking/  G1  #1  좌석 예약의 중복을 막는다   ← backend/db
│  └─ db/       G1  #2  예약 데이터를 저장하고 꺼낸다
├─ frontend/    G2  #2  이용자가 보는 화면
│  └─ seatmap/  G2      빈 좌석을 3초 안에 찾게 한다   ← backend/booking
└─ reports/     G3  #3  운영자용 보고서
   └─ weekly/   G3      한 주 이용 흐름을 보여 준다   ← backend/booking

$ garden map --order
1. backend/db(G1)
2. backend/booking(G1)
3. frontend/seatmap(G2), reports/weekly(G3)
```

`garden map --why`는 폴더를 나눈 이유까지, `--mermaid`는 그래프를 보여 줍니다.

## 설치 (Claude Code 플러그인)

필요한 것: Claude Code 2.1 이상, Python 3.11 이상 + PyYAML(또는 [uv](https://docs.astral.sh/uv/)), Windows는 [Git for Windows](https://git-scm.com/download/win).

```
/plugin marketplace add beit06davi/plant
/plugin install garden@garden-plugins
```

Claude Code에서 Bash로 `garden --version`을 실행해 확인합니다.

<details>
<summary>Python 준비</summary>

- **Windows**: [python.org](https://www.python.org/downloads/)에서 설치할 때 "Add python.exe to PATH"를 체크합니다. 설정 → 앱 → 고급 앱 설정 → 앱 실행 별칭에서 `python.exe`, `python3.exe`를 끕니다(켜 두면 Microsoft Store가 열립니다). 그다음 `python -m pip install pyyaml`.
- **macOS**: `brew install python@3.13` 후 `python3 -m pip install --user --break-system-packages pyyaml`, 또는 uv를 씁니다.
- **Linux**: `sudo apt install python3 python3-yaml` (3.11 미만이면 uv).
- **uv만 쓰기**: uv가 있으면 Python과 PyYAML을 알아서 받아 실행합니다.

플러그인은 `python3` → `python` → `py` → `uv` 순서로 쓸 수 있는 것을 찾아 `~/.cache/garden/python`에 기억합니다. 특정 Python을 쓰려면 환경 변수 `GARDEN_PYTHON`에 경로를 넣습니다.

</details>

플러그인 없이 쓰려면 `pip install git+https://github.com/beit06davi/plant` 후 프로젝트 폴더에서 `python -m garden init --standalone`을 실행합니다. 훅과 스킬(`/garden-guide` 등)이 프로젝트의 `.claude/`에 설치됩니다.

## 시작하기

프로젝트 폴더에서 Claude Code를 엽니다.

1. `garden init` — `SEED.md`, `garden.yaml`, `CLAUDE.md`, `.garden/`을 만듭니다. 이미 있는 파일은 건드리지 않고, 기존 `CLAUDE.md`에는 garden 안내 블록만 덧붙입니다.
2. `/garden:plant` — 에이전트가 SEED의 목표를 함께 정하고, 폴더마다 카드를 씁니다.
3. `garden check` — 형식을 검사합니다.
4. `garden lock` — 현재 개념을 기록합니다. 이후 변경 알림의 기준입니다.

그다음은 평소처럼 일을 시키면 됩니다. 에이전트용 설명은 `/garden:guide`에 있습니다.

## 명령

| 명령 | 하는 일 |
|---|---|
| `garden init` | 프로젝트 파일 만들기 |
| `garden add <폴더> --purpose … --serves G1 [--why --priority --needs --provides]` | 카드 쓰기 |
| `garden check [--json]` | 형식 검사 (0 정상, 1 경고, 2 오류) |
| `garden map [--why \| --order \| --mermaid]` | 구조 보기 |
| `garden trace <폴더>` | SEED부터 그 폴더까지 |
| `garden context <폴더> [--detail …] [--json]` | 주입 블록 출력 (훅이 없는 에이전트용) |
| `garden lock [--missing]` | 개념 기록 |
| `garden ack <폴더> --from <폴더>` | 변경 확인 처리 |
| `garden log <폴더> "<변경>" --why "<이유>"` | 폴더 `HISTORY.md`에 기록 |
| `garden resume [폴더]` | 이어받기 요약 |

스킬: `/garden:guide` · `/garden:plant` · `/garden:map` · `/garden:resume`

## 다른 에이전트에서

형식은 마크다운과 YAML뿐이라 어떤 에이전트든 파일을 직접 읽을 수 있습니다. 자동 주입은 Claude Code 훅으로만 동작합니다. 다른 환경에서는 `garden context <폴더> --json` 출력을 프롬프트에 넣으세요.

## 한계

- 이 형식이 작업 결과를 얼마나 개선하는지는 측정하지 않았습니다.
- 변경 알림은 카드의 purpose·why·provides만 봅니다. 코드만 바뀐 경우는 감지하지 않습니다.
- 세션은 `garden.yaml`이 있는 폴더(또는 그 하위)에서 열어야 합니다.
- Windows에서는 플러그인 훅이 Git Bash로 실행됩니다.

## 개발

```bash
uv sync
uv run pytest -q
python scripts/build_plugin.py --check   # 템플릿과 skills/가 같은지
```

## 라이선스

MIT
