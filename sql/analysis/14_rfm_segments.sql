-- @name: rfm_segments
-- @title: RFM 分层：人群结构（5 × 5）
-- @desc: 10_rfm.sql 沿用教程口径（先 dense_rank 再 ntile），当 R 只有 1~8 个
--        取值时会严重扎堆，导致 Top 榜单全是 10 分、区分度不足。
--        这里改为直接按**用户数**做 ntile(5) 分层：R 越小、F 越大得分越高，
--        输出每个 (R_score, F_score) 分群的人数、占比与平均购买次数，
--        用于判断该先做唤醒还是先做复购。

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
        b.f,
        date_diff('day', b.last_buy_date, CAST(p.as_of AS DATE)) AS r
    FROM buys b
    CROSS JOIN bounds p
),
scored AS (
    SELECT
        user_id,
        f,
        r,
        6 - NTILE(5) OVER (ORDER BY r ASC)  AS r_score,  -- 最近 20% 得 5 分
        6 - NTILE(5) OVER (ORDER BY f DESC) AS f_score   -- 最频繁 20% 得 5 分
    FROM rf
)
SELECT
    r_score,
    f_score,
    COUNT(*)                                            AS users,
    ROUND(COUNT(*)::DOUBLE / SUM(COUNT(*)) OVER (), 4)   AS user_share,
    ROUND(AVG(f), 2)                                     AS avg_frequency,
    ROUND(AVG(r), 2)                                     AS avg_recency_days
FROM scored
GROUP BY r_score, f_score
ORDER BY r_score DESC, f_score DESC;
