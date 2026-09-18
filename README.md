# garden

폴더 구조에 목표와 개념을 적어 두는 형식입니다.
에이전트는 파일을 열 때 **이 폴더가 왜 있는지, 어떤 목표를 섬기는지, 무엇이 먼저 있어야 하는지**를 함께 받습니다.
사람은 폴더 트리만 보고 무엇이 중요하고 무엇부터 할지 압니다.

에이전트가 하나든 여럿이든 같은 파일을 읽습니다. 검증 강도, 담당 배분, 완료 기준은 garden이 정하지 않고, 프로젝트의 에이전트가 정합니다.

## 형식

```
SEED.md                     최상위 목표 (위에 있을수록 중요)
backend/NODE.md             폴더 카드
backend/booking/NODE.md     하위 카드 — 가장 가까운 상위 카드가 부모
backend/db/NODE.md
frontend/seatmap/NODE.md
```

```markdown
---
purpose: 좌석 예약의 중복을 막는다        # 이 폴더가 있는 이유
why: 예약 판단을 한곳에 모아 화면이 규칙을 몰라도 되게 한다   # 따로 나눈 이유
serves: [G1]                             # 섬기는 SEED 목표
priority: 1                              # 형제 폴더 중 중요도 (1이 가장 중요)
needs: [backend/db]                      # 먼저 있어야 하는 폴더 (작업 순서)
provides: 좌석 상태 목록 (id, zone, status)   # 다른 폴더에 내주는 것
---
본문은 자유. 이 폴더에서 지킬 것, 메모.
```

`priority`는 중요도, `needs`는 작업 순서입니다. 위 예시에서 booking은 db보다 중요하지만, db가 먼저 있어야 합니다.

전체 규칙은 [docs/FORMAT.md](docs/FORMAT.md)에, 예시는 [examples/basic](examples/basic)에 있습니다.

## 에이전트가 받는 것

`backend/booking/service.py`를 열면 다음 블록이 대화에 들어갑니다.

```
[garden] backend/booking — 좌석 예약의 중복을 막는다
goal: G1 이중 예약이 없다
lineage: SEED > backend(예약 규칙과 저장을 맡는다) > backend/booking
why: 예약 판단을 한곳에 모아 화면이 규칙을 몰라도 되게 한다
siblings: backend 아래 중요도 순 — backend/booking(1) > backend/db(2) (이 폴더: 1번째)
needs: backend/db — 예약 데이터를 저장하고 꺼낸다 · 주는 것: 예약 저장·조회 함수
provides: 좌석 상태 목록 (id, zone, status)
needed by: frontend/seatmap — 빈 좌석을 3초 안에 찾게 한다
needed by: reports/weekly — 한 주 이용 흐름을 보여 준다
notes:
  ## 메모
  - 확정 예약은 좌석·시간마다 하나
  - 취소된 예약은 좌석을 점유하지 않는다
more: `garden context backend/booking --detail full` · 전체 구조 `garden map --why`
```

- 같은 세션에서 같은 블록은 한 번만 들어갑니다. 에이전트마다 따로 셉니다.
- 관련 폴더를 얼마나 보여줄지는 `garden.yaml`의 `context`로 정합니다: `none`(이름만) · `concept`(목적·주는 것, 기본) · `full`(이유와 카드 본문까지).
- 카드의 purpose·why·provides가 바뀌면, 그 폴더를 `needs`로 가진 폴더에 확인 알림이 갑니다. 영향을 확인한 뒤 `garden ack`로 처리합니다.

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
작업 순서 (needs 기준 — 같은 단계는 서로 기다리지 않음)
1. backend/db(G1)
2. backend/booking(G1)
3. frontend/seatmap(G2), reports/weekly(G3)

순서 연결 없음: backend, frontend, reports
```

각 줄은 `폴더/  목표  #중요도  목적  ← 먼저 있어야 하는 폴더`입니다. `garden map --why`는 폴더를 나눈 이유까지, `--mermaid`는 그래프를 보여 줍니다.

## 설치 (Claude Code 플러그인)

필요한 것:
- Claude Code (2.1.274에서 확인)
- Python 3.11 이상 + PyYAML, 또는 [uv](https://docs.astral.sh/uv/)
- Windows는 [Git for Windows](https://git-scm.com/download/win) (플러그인 훅이 Git Bash로 실행됨)

Claude Code 입력창에서:

```
/plugin marketplace add beit06davi/plant
/plugin install garden@garden-plugins
```

설치한 뒤 Claude Code를 다시 엽니다. Claude에게 "`garden --version` 실행해 줘"라고 해서 `garden 0.4.1`이 나오면 됩니다.

<details>
<summary>Python 준비</summary>

- **Windows**: [python.org](https://www.python.org/downloads/)에서 설치할 때 "Add python.exe to PATH"를 체크합니다. 설정 → 앱 → 고급 앱 설정 → 앱 실행 별칭에서 `python.exe`, `python3.exe`를 끕니다(켜 두면 Microsoft Store가 열립니다). 그다음 `python -m pip install pyyaml`.
- **macOS**: `brew install python@3.13` 후 `python3 -m pip install --user --break-system-packages pyyaml`, 또는 uv를 씁니다.
- **Linux**: `sudo apt install python3 python3-yaml` (3.11 미만이면 uv).
- **uv만 쓰기**: uv가 있으면 Python과 PyYAML을 알아서 받아 실행합니다.

플러그인은 `python3` → `python` → `py` → `uv` 순서로 쓸 수 있는 것을 찾고, 찾은 결과를 플러그인 데이터 폴더(없으면 `~/.cache/garden`)에 기억합니다. 특정 Python을 쓰려면 환경 변수 `GARDEN_PYTHON`에 경로를 넣습니다.

</details>

<details>
<summary>플러그인 없이 쓰기</summary>

```bash
python -m pip install git+https://github.com/beit06davi/plant
cd <프로젝트 폴더>
python -m garden init --standalone
```

훅과 스킬(`/garden-guide` 등)이 프로젝트의 `.claude/`에 설치됩니다. 이 방식은 설치한 Python의 경로를 `.claude/settings.json`에 적으므로, 여러 컴퓨터에서 같이 쓰는 저장소라면 플러그인 방식을 쓰세요. macOS·Linux에서는 `python3`를 쓰고, 시스템 Python이 설치를 막으면 가상환경 안에서 설치합니다.

</details>

## 시작하기

프로젝트 폴더에서 Claude Code를 엽니다. `garden` 명령은 Claude에게 "…실행해 줘"라고 부탁하면 Claude가 실행합니다.

1. **`garden init`** — `SEED.md`, `garden.yaml`, `CLAUDE.md`, `.garden/`을 만듭니다. 이미 있는 파일은 건드리지 않고, 기존 `CLAUDE.md`에는 garden 안내 블록만 덧붙입니다.
2. **Claude Code를 다시 엽니다.** `CLAUDE.md`는 세션을 시작할 때 읽힙니다.
3. **`/garden:plant`** — Claude가 SEED의 목표를 함께 정하고, 폴더마다 카드를 씁니다.
4. **`garden check`** — 형식을 검사합니다. 목표 칸에 틀(`<…>`)이 남아 있으면 오류가 납니다.
5. **`garden lock`** — 현재 개념을 기록합니다. 이후 변경 알림의 기준입니다.

그다음은 평소처럼 일을 시키면 됩니다. 에이전트용 설명은 `/garden:guide`에 있습니다.

### 이전 버전에서 올라올 때

```bash
claude plugin marketplace update garden-plugins
claude plugin update garden@garden-plugins
```

업데이트한 뒤 Claude Code를 다시 엽니다.

0.3을 쓰던 프로젝트에서 `garden init`을 다시 실행하면, `CLAUDE.md`에 남은 예전 안내(`garden route`, `sprout`, `ring` 등)와 예전 에이전트·스킬 파일이 보이면 알려 줍니다. 읽어 보고 0.3 안내면 지웁니다. `garden check`는 예전 설정(`garden.yaml`의 `zones`, `roles` 등)과 카드 칸(`zone`, `uses`, `name`)을 경고로 알려 줍니다. `uses`에 적었던 연결은 `needs`에 폴더 경로로 옮깁니다.

## 명령

경로는 모두 프로젝트 최상위 기준입니다(예: `backend/booking`).

| 명령 | 하는 일 |
|---|---|
| `garden init` | 프로젝트 파일 만들기 (있는 파일은 유지) |
| `garden add <폴더> --purpose … [--serves G1] [--why …] [--priority N] [--needs 폴더] [--provides …] [--create]` | 카드 쓰기. `--serves`를 빼면 상위 카드의 목표를 따르고, 폴더가 없으면 오류(`--create`로 생성) |
| `garden check [--json]` | 형식 검사 (0 정상, 1 경고·확인 필요, 2 오류) |
| `garden map [--why \| --order \| --mermaid]` | 구조 보기 |
| `garden trace <폴더>` | SEED부터 그 폴더까지 |
| `garden context <폴더> [--detail none\|concept\|full] [--budget N] [--json]` | 주입 블록 출력 (훅이 없는 에이전트용) |
| `garden lock [--missing \| --force]` | 개념 기록. `--missing`은 새 연결만, `--force`는 확인 대기나 깨진 기록까지 새로 씀 |
| `garden ack <폴더> --from <폴더> \| --all [--note …]` | 변경 확인 처리 |
| `garden log <폴더> "<변경>" [--why …] [--evidence …]` | 폴더 `HISTORY.md`에 기록 |
| `garden resume [폴더]` | 이어받기 요약 |

스킬: `/garden:guide` · `/garden:plant` · `/garden:map` · `/garden:resume`

## 다른 에이전트에서

형식은 마크다운과 YAML뿐이라 어떤 에이전트든 파일을 직접 읽을 수 있습니다. 자동 주입은 Claude Code 훅으로만 동작합니다. 다른 환경에서는 `garden context <폴더> --json` 출력을 프롬프트에 넣으세요.

## 한계

- 이 형식이 작업 결과를 얼마나 개선하는지는 측정하지 않았습니다.
- 변경 알림은 카드의 purpose·why·provides만 봅니다. 코드만 바뀐 경우는 감지하지 않습니다.
- 세션은 `garden.yaml`이 있는 폴더(또는 그 하위)에서 열어야 합니다.
- `.garden/concept.lock`이 병합 충돌 등으로 깨지면 `garden check`가 알려 줍니다. `garden lock --force`로 다시 기록합니다.

## 개발

```bash
uv sync
uv run pytest -q
python scripts/build_plugin.py --check   # 템플릿과 skills/가 같은지
```

## 라이선스

MIT
