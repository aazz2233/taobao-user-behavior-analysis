-- @name: weekly_activity
-- @title: 一周活跃分布
-- @desc: 0 = 周一 … 6 = 周日。只取完整自然周（2017-11-27 至 2017-12-03），
--        避免 11-25、11-26 两个不完整的工作日/周末拉偏结论。
--        原脚本用 pmod(datediff(...,'1920-01-01') - 3, 7) 推算星期几，依赖取模细节，
--        这里改用 dayofweek() 显式换算，结果自解释。

WITH week_events AS (
    SELECT
        (dayofweek(CAST(event_time AS DATE)) + 6) % 7 AS weekday,  -- 0 = 周一
        behavior_type
    FROM events
    WHERE CAST(event_time AS DATE) BETWEEN DATE {{week_start}} AND DATE {{week_end}}
)
SELECT
    weekday,
    CASE weekday
        WHEN 0 THEN '周一' WHEN 1 THEN '周二' WHEN 2 THEN '周三'
        WHEN 3 THEN '周四' WHEN 4 THEN '周五' WHEN 5 THEN '周六'
        ELSE '周日'
    END                                                    AS weekday_name,
    SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
    SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
    SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy
FROM week_events
GROUP BY weekday
ORDER BY weekday;
