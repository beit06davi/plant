from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from garden import __version__
from garden.initcmd import InitError
from garden.lock import LockError
from garden.model import DETAILS, find_root
from garden.tree import Garden


class CliError(Exception):
    pass


def _utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def _garden(args) -> Garden:
    root = Path(args.root) if args.root else find_root(Path.cwd())
    if root is None or not root.is_dir():
        raise CliError("garden 프로젝트를 찾지 못했습니다 (garden.yaml이나 SEED.md가 있는 폴더에서 실행하거나 -C로 지정)")
    return Garden.load(root)


def _node(g: Garden, ref: str):
    node = g.get(ref)
    if node is None:
        raise CliError(f"카드를 찾지 못했습니다: {ref}")
    return node


def _split(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for v in values or []:
        out += [x.strip() for x in v.split(",") if x.strip()]
    return out


def _pending_lines(g: Garden, node_id: str) -> list[str]:
    from garden import lock

    return [lock.pending_line(p.a, p.b) for p in lock.safe_pending(g) if p.a == node_id]


def cmd_init(args) -> int:
    from garden.initcmd import init

    root = Path(args.root or args.path or ".")
    plugin = args.plugin if args.plugin is not None else os.environ.get("GARDEN_PLUGIN") == "1"
    result = init(root, project=args.project, dry_run=args.dry_run, plugin=plugin)
    prefix = "(dry-run) " if args.dry_run else ""
    for label, rels in (("생성", result.created), ("갱신", result.updated), ("유지", result.skipped)):
        for rel in rels:
            print(f"{prefix}{label}: {rel}")
    if result.settings_diff and ".claude/settings.json" in result.updated:
        print(result.settings_diff.rstrip())
    for note in result.notes:
        print(f"주의: {note}")
    plant = "/garden:plant" if plugin else "/garden-plant"
    if not args.dry_run and "CLAUDE.md" in result.created + result.updated:
        print("CLAUDE.md는 세션을 시작할 때 읽히므로 Claude Code를 다시 연다.")
    print(f"다음: SEED.md에 목표를 쓰고 폴더마다 카드를 만든다 ({plant} 또는 garden add) → garden check → garden lock")
    return 0


def cmd_add(args) -> int:
    from garden.initcmd import add

    g = _garden(args)
    path = add(
        g, args.folder, purpose=args.purpose, serves=_split(args.serves), why=args.why or "",
        priority=args.priority, needs=_split(args.needs), provides=args.provides or "", create=args.create,
    )
    print(f"생성: {g.rel(path)}")
    return 0


def cmd_check(args) -> int:
    from garden.validate import check

    report = check(_garden(args))
    if args.json:
        print(report.to_json())
        return report.exit_code
    labels = {"error": "오류", "warning": "경고", "review": "확인 필요"}
    for level in ("error", "warning", "review"):
        for f in report.of(level):
            print(f"[{labels[level]}] {f.where}: {f.msg} ({f.code})")
    if report.exit_code == 0:
        print("이상 없음")
    return report.exit_code


def cmd_map(args) -> int:
    from garden.report import map_mermaid, map_order, map_tree

    g = _garden(args)
    if args.mermaid:
        print(map_mermaid(g))
    elif args.order:
        print(map_order(g))
    else:
        print(map_tree(g, show_why=args.why))
    return 0


def cmd_trace(args) -> int:
    from garden.lineage import trace_text

    g = _garden(args)
    print(trace_text(g, _node(g, args.ref)))
    return 0


def cmd_context(args) -> int:
    from garden.lineage import context, context_data

    g = _garden(args)
    node = _node(g, args.ref)
    pending = _pending_lines(g, node.id)
    if args.json:
        data = context_data(g, node, detail=args.detail, budget=args.budget, pending=pending)
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(context(g, node, detail=args.detail, budget=args.budget, pending=pending))
    return 0


def cmd_lock(args) -> int:
    from garden import lock

    g = _garden(args)
    if args.missing:
        added = lock.lock_missing(g)
        print(f"새 연결 {len(added)}개 기록" + "".join(f"\n- {a} ← {b}" for a, b in added))
        return 0
    ok, msg = lock.lock_all(g, force=args.force)
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def cmd_ack(args) -> int:
    from garden import lock

    g = _garden(args)
    node = _node(g, args.ref)
    source = _node(g, args.source).id if args.source else None
    done = lock.ack(g, node.id, source=source, all_pending=args.all, note=args.note)
    if done:
        print(f"확인 처리: {node.id} ← {', '.join(done)} (HISTORY.md에 기록)")
    else:
        print("처리할 변경 없음")
    return 0


def cmd_log(args) -> int:
    from garden.history import log

    g = _garden(args)
    node = _node(g, args.ref)
    line = log(g, node, args.change, why=args.why, evidence=args.evidence, serves=_split(args.serves) or None)
    print(f"{node.id}/HISTORY.md: {line}")
    return 0


def cmd_resume(args) -> int:
    from garden.history import resume_text

    g = _garden(args)
    node_id = _node(g, args.ref).id if args.ref else None
    print(resume_text(g, node_id, last=args.last))
    return 0


def cmd_hook(args) -> int:
    from garden.hook import run

    return run(args.kind)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="garden", description="폴더에 목표와 개념을 적는 형식 — SEED.md와 NODE.md")
    p.add_argument("-C", "--root", help="프로젝트 폴더 (기본: 현재 폴더에서 위로 찾음)")
    p.add_argument("--version", action="version", version=f"garden {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="SEED.md·garden.yaml·CLAUDE.md 만들기 (있는 파일은 유지)")
    s.add_argument("path", nargs="?")
    s.add_argument("--project")
    s.add_argument("--dry-run", action="store_true")
    mode = s.add_mutually_exclusive_group()
    mode.add_argument("--plugin", dest="plugin", action="store_const", const=True, default=None,
                      help="플러그인이 훅·스킬을 제공: 프로젝트 파일만 만든다 (플러그인에서 실행하면 기본)")
    mode.add_argument("--standalone", dest="plugin", action="store_const", const=False,
                      help="플러그인 없이: 훅과 스킬을 프로젝트 .claude/에 설치")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("add", help="폴더에 카드(NODE.md) 쓰기")
    s.add_argument("folder", help="카드를 둘 폴더 (프로젝트 최상위 기준 경로)")
    s.add_argument("--purpose", required=True, help="이 폴더가 있는 이유 한 줄")
    s.add_argument("--why", help="이 폴더를 따로 나눈 이유")
    s.add_argument("--serves", action="append", help="섬기는 SEED 목표 (G1 또는 G1,G2). 없으면 상위 카드를 따름")
    s.add_argument("--priority", type=int, help="형제 폴더 중 중요도 (1이 가장 중요)")
    s.add_argument("--needs", action="append", help="먼저 있어야 하는 폴더 = 작업 순서 (최상위 기준 경로, 쉼표로 여러 개)")
    s.add_argument("--provides", help="다른 폴더에 내주는 것")
    s.add_argument("--create", action="store_true", help="폴더가 없으면 새로 만든다 (기본은 오류)")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("check", help="형식 검사 (0 정상, 1 경고·확인 필요, 2 오류)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("map", help="구조 보기")
    view = s.add_mutually_exclusive_group()
    view.add_argument("--why", action="store_true", help="폴더를 나눈 이유와 SEED 구조 원칙까지")
    view.add_argument("--order", action="store_true", help="needs 기준 작업 순서")
    view.add_argument("--mermaid", action="store_true", help="mermaid 그래프")
    s.set_defaults(func=cmd_map)

    s = sub.add_parser("trace", help="SEED부터 그 폴더까지의 계보")
    s.add_argument("ref", help="폴더 (최상위 기준 경로) 또는 그 안의 파일")
    s.set_defaults(func=cmd_trace)

    s = sub.add_parser("context", help="파일을 열 때 주입되는 블록 출력")
    s.add_argument("ref", help="폴더 (최상위 기준 경로) 또는 그 안의 파일")
    s.add_argument("--detail", choices=DETAILS, help="관련 폴더 정보의 양 (기본: garden.yaml의 context)")
    s.add_argument("--budget", type=int, help="최대 글자 수")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_context)

    s = sub.add_parser("lock", help="현재 개념을 기록 (변경 알림의 기준)")
    grp = s.add_mutually_exclusive_group()
    grp.add_argument("--missing", action="store_true", help="새 연결만 추가하고 없어진 연결은 정리")
    grp.add_argument("--force", action="store_true", help="확인 대기 중인 변경까지 덮어씀")
    s.set_defaults(func=cmd_lock)

    s = sub.add_parser("ack", help="바뀐 개념의 영향을 확인했다고 기록")
    s.add_argument("ref", help="확인한 폴더 (A)")
    grp = s.add_mutually_exclusive_group(required=True)
    grp.add_argument("--from", dest="source", help="바뀐 폴더 (B)")
    grp.add_argument("--all", action="store_true", help="A의 확인 대기 전부")
    s.add_argument("--note", help="확인 결과 한 줄")
    s.set_defaults(func=cmd_ack)

    s = sub.add_parser("log", help="폴더 HISTORY.md에 변경 기록")
    s.add_argument("ref", help="폴더 (최상위 기준 경로) 또는 그 안의 파일")
    s.add_argument("change")
    s.add_argument("--why")
    s.add_argument("--evidence")
    s.add_argument("--serves", action="append")
    s.set_defaults(func=cmd_log)

    s = sub.add_parser("resume", help="이어받기 요약: 목적·최근 이력·확인할 변경")
    s.add_argument("ref", nargs="?")
    s.add_argument("--last", type=int, default=5)
    s.set_defaults(func=cmd_resume)

    s = sub.add_parser("hook", help="Claude Code 훅 진입점 (stdin JSON → stdout JSON)")
    s.add_argument("kind", choices=["pre", "post", "compact"])
    s.set_defaults(func=cmd_hook)
    return p


def main(argv: list[str] | None = None) -> int:
    _utf8_streams()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (CliError, InitError, LockError) as e:
        print(f"garden: {e}", file=sys.stderr)
        return 2
