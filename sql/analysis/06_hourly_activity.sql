-- @name: hourly_activity
-- @title: 一天内的活跃时段分布
-- @desc: 按小时统计各行为的次数，定位用户活跃高峰（北京时间）。

SELECT
    EXTRACT(hour FROM event_time)                          AS hour,
    SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
    SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
    SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy
FROM events
GROUP BY 1
ORDER BY 1;
