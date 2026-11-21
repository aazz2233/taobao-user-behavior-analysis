-- @name: daily_traffic
-- @title: 日均访问量 / 日均用户量
-- @desc: 按自然日统计 PV、UV、购买次数，用于观察 12·12 预热期的流量走势。

SELECT
    CAST(event_time AS DATE)                             AS day,
    SUM(CASE WHEN behavior_type = 'pv'  THEN 1 ELSE 0 END) AS pv,
    COUNT(DISTINCT user_id)                              AS uv,
    SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS buy,
    ROUND(
        SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END)::DOUBLE
        / NULLIF(COUNT(DISTINCT user_id), 0), 2
    )                                                    AS pv_per_uv
FROM events
GROUP BY 1
ORDER BY 1;
