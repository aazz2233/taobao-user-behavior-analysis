"""验证清洗逻辑：一次扫描同时完成「去重 + 时间过滤 + 时区转换」。"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from taobao_analysis import db

IN_RANGE_1 = 1511799230  # 2017-11-28 00:13:50 (北京时间)
IN_RANGE_2 = 1512057600  # 2017-12-01 00:00:00
TOO_EARLY = 1511000000   # 2017-11-18
BOUNDARY_END = 1512316800  # 2017-12-04 00:00:00 —— 右开区间，应被排除


def test_to_epoch_uses_beijing_time():
    """2017-11-25 00:00 北京时间 == 2017-11-24 16:00 UTC。"""
    assert db.to_epoch("2017-11-25") == 1511539200
    assert db.to_epoch("2017-12-04") == 1512316800


def test_sql_literal_escapes_quotes():
    assert db._sql_literal("a'b") == "'a''b'"
    assert db._sql_literal(8) == "8"


def test_render_sql_replaces_placeholders(tmp_path: Path):
    template = tmp_path / "t.sql"
    template.write_text("SELECT * FROM read_csv({{csv}}) WHERE ts >= {{start}}", encoding="utf-8")

    rendered = db.render_sql(template, csv="C:/it's.csv", start=123)
    assert "read_csv('C:/it''s.csv')" in rendered
    assert "ts >= 123" in rendered


def test_build_events_dedupes_and_filters(tmp_path: Path, monkeypatch):
    csv_path = tmp_path / "UserBehavior.csv"
    csv_path.write_text(
        "\n".join(
            [
                f"1,100,10,pv,{IN_RANGE_1}",
                f"1,100,10,pv,{IN_RANGE_1}",   # 完全重复
                f"2,200,20,buy,{IN_RANGE_2}",
                f"3,300,30,pv,{TOO_EARLY}",     # 早于起始日期
                f"4,400,40,pv,{BOUNDARY_END}",  # 恰好在右边界，需排除
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    try:
        con.execute(f"SET TimeZone = '{db.TIMEZONE}'")
        result = db.build_events(con, csv_path, force=True)
        assert result["rows"] == 2, "1 条重复 + 2 条越界应被清洗掉"

        types = {row[0]: row[1] for row in con.execute("DESCRIBE events").fetchall()}
        assert types["event_time"] == "TIMESTAMP"

        rows = con.execute("SELECT user_id, event_time FROM events ORDER BY user_id").fetchall()
        assert rows[0][0] == 1
        assert str(rows[0][1]) == "2017-11-28 00:13:50"
        assert str(rows[1][1]) == "2017-12-01 00:00:00"
    finally:
        con.close()


def test_build_events_skips_when_table_exists(tmp_path: Path):
    csv_path = tmp_path / "UserBehavior.csv"
    csv_path.write_text(f"1,100,10,pv,{IN_RANGE_1}\n", encoding="utf-8")

    con = duckdb.connect(str(tmp_path / "t.duckdb"))
    try:
        first = db.build_events(con, csv_path, force=True)
        second = db.build_events(con, csv_path)
        assert first["skipped"] is False
        assert second["skipped"] is True
        assert second["rows"] == first["rows"] == 1
    finally:
        con.close()


def test_find_csv_reports_what_it_tried(tmp_path: Path, monkeypatch):
    """找不到数据时要报出尝试过的路径，而不是抛一个空异常。"""
    monkeypatch.setattr(db, "REPO_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError) as excinfo:
        db.find_csv(tmp_path / "missing.csv")
    assert "UserBehavior.csv" in str(excinfo.value)


def test_find_csv_prefers_explicit_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(db, "REPO_ROOT", tmp_path)
    explicit = tmp_path / "somewhere" / "mine.csv"
    explicit.parent.mkdir(parents=True)
    explicit.write_text("1,100,10,pv,1511799230\n", encoding="utf-8")

    assert db.find_csv(explicit) == explicit

    # 未显式指定时回退到 data/UserBehavior.csv
    default_dir = tmp_path / "data"
    default_dir.mkdir()
    default = default_dir / db.CSV_NAME
    default.write_text("1,100,10,pv,1511799230\n", encoding="utf-8")
    assert db.find_csv() == default
