"""命令行入口：``taobao-analysis <build|analyse|charts|all>``。"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from . import analysis, charts, db


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default=str(db.DEFAULT_DB), help="DuckDB 数据库路径")
    parser.add_argument("--threads", type=int, default=8, help="DuckDB 线程数")
    parser.add_argument("--memory", default=None, help="内存上限，如 8GB（默认按 DuckDB 自动）")


def _results_dir(args: argparse.Namespace) -> Path:
    return Path(args.out) if getattr(args, "out", None) else db.REPO_ROOT / "results"


def cmd_build(args: argparse.Namespace) -> int:
    csv_path = db.find_csv(args.csv)
    print(f"[build] CSV   : {csv_path}")
    print(f"[build] DB    : {args.db}")

    con = db.connect(args.db, threads=args.threads, memory_limit=args.memory)
    try:
        result = db.build_events(con, csv_path, force=args.force)
        if result["skipped"]:
            print(f"[build] events 表已存在（{result['rows']:,} 行），跳过。用 --force 重建。")
        else:
            print(f"[build] events 建成：{result['rows']:,} 行，耗时 {result['seconds']:.1f}s")

        started = time.perf_counter()
        users = db.prepare_user_count(con)
        print(f"[build] user_count：{users:,} 个用户，耗时 {time.perf_counter() - started:.1f}s")
    finally:
        con.close()
    return 0


def cmd_analyse(args: argparse.Namespace) -> int:
    out_dir = _results_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    con = db.connect(args.db, read_only=args.read_only, threads=args.threads, memory_limit=args.memory)
    try:
        if not db.table_exists(con, "events"):
            print("[analyse] 还没有 events 表，请先运行 build。", file=sys.stderr)
            return 2
        if not db.table_exists(con, "user_count"):
            print("[analyse] 正在生成 user_count ...")
            db.prepare_user_count(con)

        queries = analysis.load_queries()
        results: dict = {}
        total = time.perf_counter()
        for item in queries:
            started = time.perf_counter()
            frame = analysis.run_query(con, item)
            frame.to_csv(out_dir / f"{item.name}.csv", index=False, encoding="utf-8-sig")
            results[item.name] = frame
            print(f"[analyse] {item.name:<24} {len(frame):>5} 行  {time.perf_counter() - started:>6.2f}s")

        summary = analysis.write_summary(queries, results, out_dir / "SUMMARY.md")
        print(f"[analyse] 共 {len(queries)} 条查询，耗时 {time.perf_counter() - total:.1f}s")
        print(f"[analyse] 结果目录 {out_dir}")
        print(f"[analyse] 总览     {summary}")
    finally:
        con.close()
    return 0


def cmd_charts(args: argparse.Namespace) -> int:
    out_dir = _results_dir(args)
    figures = Path(args.figures) if args.figures else out_dir / "figures"
    produced = charts.build_all(out_dir, figures)
    if not produced:
        print("[charts] 没有可用的结果 CSV，请先运行 analyse。", file=sys.stderr)
        return 2
    for path in produced:
        print(f"[charts] {path}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    con = db.connect(args.db, read_only=True, threads=args.threads, memory_limit=args.memory)
    try:
        tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
        if not tables:
            print("(空数据库)")
            return 0
        for table in tables:
            rows = db.count_rows(con, table)
            columns = [row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()]
            print(f"{table:<20} {rows:>14,} 行  {columns}")

        if db.table_exists(con, "events"):
            span = con.execute("SELECT min(event_time), max(event_time) FROM events").fetchone()
            print(f"\n时间范围：{span[0]}  ~  {span[1]}")
    finally:
        con.close()
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    code = cmd_build(args)
    if code:
        return code
    code = cmd_analyse(args)
    if code:
        return code
    return cmd_charts(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="taobao-analysis",
        description="淘宝用户行为数据分析（DuckDB）：PV/UV、转化漏斗、RFM、商品维度",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_build = sub.add_parser("build", help="从 CSV 建表并清洗（一次性扫描）")
    p_build.add_argument("--csv", default=None, help="原始 CSV 路径（默认 data/UserBehavior.csv）")
    p_build.add_argument("--force", action="store_true", help="即使 events 已存在也重建")
    _common(p_build)
    p_build.set_defaults(func=cmd_build)

    p_analyse = sub.add_parser("analyse", help="执行全部分析并导出 CSV / SUMMARY.md")
    p_analyse.add_argument("--out", default=None, help="结果目录（默认 results/）")
    p_analyse.add_argument("--read-only", action="store_true", help="以只读方式打开数据库")
    _common(p_analyse)
    p_analyse.set_defaults(func=cmd_analyse)

    p_charts = sub.add_parser("charts", help="由结果 CSV 生成图表")
    p_charts.add_argument("--out", default=None, help="结果目录（默认 results/）")
    p_charts.add_argument("--figures", default=None, help="图片目录（默认 results/figures/）")
    _common(p_charts)
    p_charts.set_defaults(func=cmd_charts)

    p_info = sub.add_parser("info", help="查看数据库中的表与行数")
    _common(p_info)
    p_info.set_defaults(func=cmd_info)

    p_all = sub.add_parser("all", help="build → analyse → charts 全流程")
    p_all.add_argument("--csv", default=None)
    p_all.add_argument("--force", action="store_true")
    p_all.add_argument("--out", default=None)
    p_all.add_argument("--figures", default=None)
    p_all.add_argument("--read-only", action="store_true")
    _common(p_all)
    p_all.set_defaults(func=cmd_all)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    if not hasattr(args, "out"):
        args.out = None
    if not hasattr(args, "figures"):
        args.figures = None
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
