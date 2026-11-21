-- @name: rfm
-- @title: RFM 模型 —— 找出高价值用户
-- @desc: R = 距最后一次购买的天数（越小越好），F = 购买次数（越大越好）。
--        本数据集没有金额字段，M 无法计算，故只用 R + F 打分。
--        打分方式：先把 R、F 各自 dense_rank，再按排名 ntile(5) 分 5 档，
--        最近/最频繁的一档得 5 分，总分 = R_score + F_score（满分 10）。
--        原脚本把基准日硬编码为 DATE '2017-12-04'，这里改为由数据自身推导
--        （max(event_time) 的次日），换数据集也不会错。

WITH bounds AS (
    SELECT CAST(max(event_time) AS DATE) + INTERVAL 1 DAY AS as_of
    FROM events
),
buys AS (
    SELECT
        user_id,
        CAST(max(event_time) AS DATE) AS last_buy_date,
        COUNT(*)                      AS f
    FROM events
    WHERE behavior_type = 'buy'
    GROUP BY user_id
),
rf AS (
    SELECT
        b.user_id,
        CAST(date_diff('day', b.last_buy_date, CAST(p.as_of AS DATE)) AS BIGINT) AS r,
        b.f,
        DENSE_RANK() OVER (
            ORDER BY date_diff('day', b.last_buy_date, CAST(p.as_of AS DATE)) ASC
        ) AS r_rank,
        DENSE_RANK() OVER (ORDER BY b.f DESC) AS f_rank
    FROM buys b
    CROSS JOIN bounds p
),
scored AS (
    SELECT
        *,
        CASE NTILE(5) OVER (ORDER BY r_rank ASC)
            WHEN 1 THEN 5 WHEN 2 THEN 4 WHEN 3 THEN 3 WHEN 4 THEN 2 ELSE 1 END AS r_score,
        CASE NTILE(5) OVER (ORDER BY f_rank ASC)
            WHEN 1 THEN 5 WHEN 2 THEN 4 WHEN 3 THEN 3 WHEN 4 THEN 2 ELSE 1 END AS f_score
    FROM rf
)
SELECT
    user_id, r, r_rank, r_score, f, f_rank, f_score,
    r_score + f_score AS score
FROM scored
ORDER BY score DESC, r ASC, f DESC, user_id
LIMIT 20;
