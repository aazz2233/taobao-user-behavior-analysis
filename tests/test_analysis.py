"""验证每条分析 SQL 都能在真实 schema 上跑通，且关键指标自洽。"""

from __future__ import annotations

import pytest

from taobao_analysis import analysis, db

QUERIES = analysis.load_queries()
QUERY_IDS = [query.name for query in QUERIES]


def test_queries_discovered():
    """sql/analysis 下的每个文件都要能被解析出元信息。"""
    assert len(QUERIES) >= 13
    for query in QUERIES:
        assert query.title and query.title != query.path.stem, f"{query.path.name} 缺少 @title"
        assert query.description, f"{query.path.name} 缺少 @desc"


@pytest.mark.parametrize("query", QUERIES, ids=QUERY_IDS)
def test_query_runs_and_returns_rows(con, query):
    frame = analysis.run_query(con, query)
    assert not frame.empty, f"{query.name} 没有返回任何行"
    assert not frame.isnull().all().any(), f"{query.name} 返回了整列为空的结果"


def test_pv_uv_totals(con):
    frame = analysis.run_query(con, _by_name("pv_uv"))
    row = frame.iloc[0]
    total = con.execute("SELECT count(*) FROM events").fetchone()[0]
    assert row["total_events"] == total
    assert row["uv"] == con.execute("SELECT count(DISTINCT user_id) FROM events").fetchone()[0]


def test_funnel_totals_match_user_count(con):
    """漏斗聚合值必须与 user_count 的逐项求和完全一致。

    注意：这是「行为级」漏斗，收藏次数 + 加购次数可能少于购买次数
    （用户可能直接下单而不收藏/加购），所以不能断言各级必然单调递减。
    """
    row = analysis.run_query(con, _by_name("funnel")).iloc[0]
    expected = con.execute(
        "SELECT SUM(pv), SUM(fav), SUM(cart), SUM(buy) FROM user_count"
    ).fetchone()

    assert row["pv"] == expected[0]
    assert row["fav"] == expected[1]
    assert row["cart"] == expected[2]
    assert row["fav_cart"] == expected[1] + expected[2]
    assert row["buy"] == expected[3]

    # 三个转化率都要等于对应的除法结果
    assert row["pv_to_favcart"] == pytest.approx((expected[1] + expected[2]) / expected[0], rel=1e-3)
    assert row["favcart_to_buy"] == pytest.approx(expected[3] / (expected[1] + expected[2]), rel=1e-3)
    assert row["pv_to_buy"] == pytest.approx(expected[3] / expected[0], rel=1e-3)


def test_repurchase_rate_matches_manual_count(con):
    row = analysis.run_query(con, _by_name("repurchase_rate")).iloc[0]
    buyers = con.execute("SELECT count(*) FROM user_count WHERE buy > 0").fetchone()[0]
    repeat = con.execute("SELECT count(*) FROM user_count WHERE buy > 1").fetchone()[0]
    assert row["buyers"] == buyers
    assert row["repeat_buyers"] == repeat
    assert row["repurchase_rate"] == pytest.approx(repeat / buyers, rel=1e-3)


def test_weekly_covers_all_seven_days_in_order(con):
    frame = analysis.run_query(con, _by_name("weekly_activity"))
    assert list(frame["weekday"]) == list(range(7)), "应恰好覆盖 0~6 且按顺序排列"
    names = list(frame["weekday_name"])
    assert names == ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    # 周一对应 2017-11-27
    assert names[0] == "周一"


def test_hourly_buckets_are_valid_and_ordered(con):
    frame = analysis.run_query(con, _by_name("hourly_activity"))
    hours = list(frame["hour"])
    assert hours == sorted(hours), "小时分布应按时间排序"
    assert set(hours) <= set(range(24)), "小时必须落在 0~23"
    expected = con.execute(
        "SELECT count(DISTINCT EXTRACT(hour FROM event_time)) FROM events"
    ).fetchone()[0]
    assert len(frame) == expected, "每个出现过的小时都要有且仅有一行"


def test_rfm_scores_in_range(con):
    frame = analysis.run_query(con, _by_name("rfm"))
    assert frame["score"].between(2, 10).all()
    assert frame["r_score"].between(1, 5).all()
    assert frame["f_score"].between(1, 5).all()
    # 分数应单调不增
    scores = list(frame["score"])
    assert scores == sorted(scores, reverse=True)


def test_top_items_and_categories_limited_to_ten(con):
    for name in ("top_items", "top_categories", "top_pv_users", "buy_rate_top", "buy_rate_bottom"):
        frame = analysis.run_query(con, _by_name(name))
        assert len(frame) <= 10


def test_buy_rate_top_is_sorted(con):
    frame = analysis.run_query(con, _by_name("buy_rate_top"))
    rates = list(frame["buy_rate"])
    assert rates == sorted(rates, reverse=True)


def _by_name(name: str) -> analysis.Query:
    for query in QUERIES:
        if query.name == name:
            return query
    raise AssertionError(f"未找到查询 {name}")
