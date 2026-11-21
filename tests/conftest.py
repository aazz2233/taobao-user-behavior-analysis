"""测试夹具：在内存/临时库里造一份极小的合成 events 表。

真实数据有 1 亿行，不适合放进 CI；这里用几十行覆盖全部行为类型、
覆盖 2017-11-27 ~ 2017-12-03 的完整自然周，以及 0~23 点的时间分布，
从而让每条分析 SQL 都能被真实执行一遍。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import duckdb
import pytest

from taobao_analysis import db

# 数据集覆盖的完整自然周
WEEK_DAYS = [datetime(2017, 11, 27) + timedelta(days=offset) for offset in range(7)]


def _synthetic_rows() -> list[tuple[int, int, int, str, datetime]]:
    rows: list[tuple[int, int, int, str, datetime]] = []

    # 用户 1：高频点击 + 2 次购买（复购用户）
    for hour in range(0, 24, 3):
        rows.append((1, 1000, 500, "pv", WEEK_DAYS[0] + timedelta(hours=hour)))
    rows.append((1, 1001, 500, "buy", WEEK_DAYS[2] + timedelta(hours=10)))
    rows.append((1, 1001, 500, "buy", WEEK_DAYS[5] + timedelta(hours=21)))

    # 用户 2：点击很多但只买 1 次（低购买率）
    for hour in range(8, 20):
        rows.append((2, 1002, 501, "pv", WEEK_DAYS[3] + timedelta(hours=hour)))
    rows.append((2, 1002, 501, "buy", WEEK_DAYS[3] + timedelta(hours=19)))

    # 用户 3：只看不买
    for offset in range(6):
        rows.append((3, 1003, 502, "pv", WEEK_DAYS[offset] + timedelta(hours=12)))

    # 用户 4：收藏 + 加购 + 购买，标准正漏斗
    rows.append((4, 1004, 503, "pv", WEEK_DAYS[1] + timedelta(hours=9)))
    rows.append((4, 1004, 503, "fav", WEEK_DAYS[1] + timedelta(hours=9)))
    rows.append((4, 1004, 503, "cart", WEEK_DAYS[1] + timedelta(hours=10)))
    rows.append((4, 1004, 503, "buy", WEEK_DAYS[1] + timedelta(hours=11)))

    # 用户 5：3 次购买，最近一次就在最后一天（RFM 双高）
    for offset in (4, 5, 6):
        rows.append((5, 1005, 504, "pv", WEEK_DAYS[offset] + timedelta(hours=20)))
        rows.append((5, 1005, 504, "buy", WEEK_DAYS[offset] + timedelta(hours=20)))

    return rows


@pytest.fixture()
def con(tmp_path):
    """返回一个装了合成 events 表的连接（user_count 也已生成）。"""
    connection = duckdb.connect(str(tmp_path / "test.duckdb"))
    connection.execute(f"SET TimeZone = '{db.TIMEZONE}'")
    connection.execute(
        """
        CREATE TABLE events (
            user_id       BIGINT,
            item_id       BIGINT,
            category_id   BIGINT,
            behavior_type VARCHAR,
            event_time    TIMESTAMP
        )
        """
    )
    connection.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?)", _synthetic_rows())
    db.prepare_user_count(connection)
    yield connection
    connection.close()
