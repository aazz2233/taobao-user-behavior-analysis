"""执行 sql/analysis 下的查询，导出 CSV 并汇总成 Markdown。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

import duckdb
import pandas as pd

from . import db

META_RE = re.compile(r"^--\s*@(name|title|desc):\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Query:
    """一条分析查询。"""

    path: Path
    name: str
    title: str
    description: str
    sql: str
    order: int = 0


def _parse_meta(text: str) -> dict[str, str]:
    return {key: value for key, value in META_RE.findall(text)}


def load_queries(directory: Path | None = None) -> list[Query]:
    """读取所有分析 SQL，按文件名排序，解析 ``-- @name/@title/@desc`` 元信息。"""
    directory = directory or (db.SQL_DIR / "analysis")
    queries: list[Query] = []

    for index, path in enumerate(sorted(directory.glob("*.sql")), start=1):
        text = path.read_text(encoding="utf-8")
        meta = _parse_meta(text)
        queries.append(
            Query(
                path=path,
                name=meta.get("name", path.stem),
                title=meta.get("title", path.stem),
                description=meta.get("desc", ""),
                sql=text,
                order=index,
            )
        )
    return queries


def query_params() -> dict[str, Any]:
    """所有分析查询共享的模板参数。"""
    return {
        "start": db.DATE_START,
        "end_exclusive": db.DATE_END_EXCLUSIVE,
        "week_start": db.WEEK_START,
        "week_end": db.WEEK_END,
    }


def run_query(con: duckdb.DuckDBPyConnection, query: Query, params: dict[str, Any] | None = None) -> pd.DataFrame:
    sql = _render(query.sql, params or query_params())
    return con.execute(sql).fetchdf()


def _render(template: str, params: dict[str, Any]) -> str:
    text = template
    for key, value in params.items():
        text = text.replace("{{" + key + "}}", db._sql_literal(value))
    return text


def run_all(
    con: duckdb.DuckDBPyConnection,
    out_dir: str | Path = "results",
    queries: Iterable[Query] | None = None,
) -> dict[str, pd.DataFrame]:
    """执行全部分析，结果写入 ``out_dir/<name>.csv``。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    params = query_params()

    results: dict[str, pd.DataFrame] = {}
    for query in queries or load_queries():
        frame = run_query(con, query, params)
        frame.to_csv(out_dir / f"{query.name}.csv", index=False, encoding="utf-8-sig")
        results[query.name] = frame
    return results


def write_summary(
    queries: Iterable[Query],
    results: dict[str, pd.DataFrame],
    path: str | Path = "results/SUMMARY.md",
    max_rows: int = 12,
) -> Path:
    """把每条查询的结果渲染成 Markdown 表格，生成结果总览。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# 分析结果总览",
        "",
        "> 由 `taobao-analysis analyse` 自动生成，数字来自对清洗后全量数据的实际查询。",
        "",
    ]
    for query in queries:
        frame = results.get(query.name)
        if frame is None or frame.empty:
            continue
        lines += [f"## {query.title}", ""]
        if query.description:
            lines += [f"> {query.description}", ""]
        lines.append(_to_markdown(frame.head(max_rows)))
        if len(frame) > max_rows:
            lines += ["", f"（共 {len(frame)} 行，完整数据见 `{query.name}.csv`）"]
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _to_markdown(frame: pd.DataFrame) -> str:
    columns = [str(c) for c in frame.columns]
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| " + " | ".join(_fmt(value) for value in record) + " |"
        for record in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, divider, *rows])


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)
