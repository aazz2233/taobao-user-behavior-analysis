"""DuckDB 连接、建表与数据清洗。

与原脚本相比的关键变化
--------------------
1. **一次扫描建表**：原脚本对 1 亿行做了 3 次 ``CREATE OR REPLACE TABLE``
   （全列 GROUP BY 去重 → 重写 datetime → 按日期过滤），每次都全表重写。
   这里把类型转换、去重、时间过滤合并成一条语句，只写一次。
2. **原生时间类型**：``event_time`` 直接存 ``TIMESTAMP``，不再存 19 字节的
   字符串再于每条查询里 ``CAST(datetime AS TIMESTAMP)``。
3. **时区显式化**：原始时间戳按 ``Asia/Shanghai`` 解释，不再依赖运行机器的
   本地时区（原脚本在 UTC 机器上会整体偏移 8 小时）。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb

#: 中国标准时间（无夏令时），用于把日期换算成 Unix 秒下推到 CSV 扫描。
CST = timezone(timedelta(hours=8))

#: 数据集时间戳按北京时间解释（与原 Hive 集群 ``from_unixtime`` 一致）。
TIMEZONE = "Asia/Shanghai"

#: 保留的数据日期区间：2017-11-25 00:00:00 ≤ t < 2017-12-04 00:00:00。
DATE_START = "2017-11-25"
DATE_END_EXCLUSIVE = "2017-12-04"

#: 完整自然周（周一至周日），用于「一周活跃分布」。
WEEK_START = "2017-11-27"
WEEK_END = "2017-12-03"

REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = REPO_ROOT / "sql"
DEFAULT_DB = REPO_ROOT / "data" / "taobao.duckdb"
CSV_NAME = "UserBehavior.csv"


# --------------------------------------------------------------------------- #
# SQL 模板渲染
# --------------------------------------------------------------------------- #
def _sql_literal(value: Any) -> str:
    """把 Python 值渲染成安全的 SQL 字面量。"""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def render_sql(path: Path, **params: Any) -> str:
    """读取 .sql 模板并把 ``{{name}}`` 占位符替换为 SQL 字面量。"""
    text = path.read_text(encoding="utf-8")
    for key, value in params.items():
        text = text.replace("{{" + key + "}}", _sql_literal(value))
    return text


# --------------------------------------------------------------------------- #
# 连接
# --------------------------------------------------------------------------- #
def connect(
    db_path: str | Path = DEFAULT_DB,
    *,
    read_only: bool = False,
    threads: int | None = 8,
    memory_limit: str | None = None,
) -> duckdb.DuckDBPyConnection:
    """打开数据库连接并设置会话参数。"""
    db_path = Path(db_path)
    if not read_only:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path), read_only=read_only)
    con.execute(f"SET TimeZone = '{TIMEZONE}'")
    if threads:
        con.execute(f"SET threads TO {int(threads)}")
    if memory_limit:
        con.execute(f"SET memory_limit = {_sql_literal(memory_limit)}")
    return con


def table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    return (
        con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [name],
        ).fetchone()[0]
        > 0
    )


def count_rows(con: duckdb.DuckDBPyConnection, table: str) -> int:
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def find_csv(explicit: str | Path | None = None) -> Path:
    """定位原始 CSV：显式路径 > data/UserBehavior.csv > 仓库根目录。"""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    candidates += [REPO_ROOT / "data" / CSV_NAME, REPO_ROOT / CSV_NAME]

    for path in candidates:
        if path.is_file():
            return path
    tried = "\n  ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        f"找不到原始数据 {CSV_NAME}，已尝试：\n  {tried}\n"
        "请用 --csv 指定路径，下载地址见 README。"
    )


# --------------------------------------------------------------------------- #
# 建表与清洗
# --------------------------------------------------------------------------- #
def to_epoch(date_str: str) -> int:
    """把 ``YYYY-MM-DD`` 按北京时间换算成 Unix 秒。"""
    return int(datetime.fromisoformat(date_str).replace(tzinfo=CST).timestamp())


def build_events(
    con: duckdb.DuckDBPyConnection,
    csv_path: str | Path,
    *,
    force: bool = False,
    start: str = DATE_START,
    end_exclusive: str = DATE_END_EXCLUSIVE,
) -> dict[str, Any]:
    """读取 CSV 并一步完成清洗，建成 ``events`` 表。

    返回 ``{"skipped", "rows", "seconds"}``。
    """
    if table_exists(con, "events") and not force:
        return {"skipped": True, "rows": count_rows(con, "events"), "seconds": 0.0}

    sql = render_sql(
        SQL_DIR / "build.sql",
        csv=str(csv_path),
        ts_start=to_epoch(start),
        ts_end=to_epoch(end_exclusive),
    )
    # 有序写入在大批量 CTAS 上只是额外开销，关掉可显著加快落表。
    try:
        con.execute("SET preserve_insertion_order = false")
    except duckdb.Error:  # pragma: no cover - 取决于 DuckDB 版本
        pass

    started = time.perf_counter()
    con.execute(sql)
    elapsed = time.perf_counter() - started
    return {"skipped": False, "rows": count_rows(con, "events"), "seconds": elapsed}


def prepare_user_count(con: duckdb.DuckDBPyConnection) -> int:
    """按用户聚合 pv/fav/cart/buy，生成 ``user_count`` 表（漏斗、复购、RFM 复用）。"""
    con.execute(render_sql(SQL_DIR / "prepare.sql"))
    return count_rows(con, "user_count")


def ensure_week_window(con: duckdb.DuckDBPyConnection) -> tuple[str, str]:
    """返回用于「一周活跃分布」的完整自然周区间。"""
    return WEEK_START, WEEK_END
