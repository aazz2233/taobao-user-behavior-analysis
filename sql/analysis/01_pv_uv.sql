-- @name: pv_uv
-- @title: 总访问量 PV / 总用户量 UV
-- @desc: 清洗后全部有效行为的点击量与独立用户数，附带数据天数用于换算日均。

SELECT
    SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) AS pv,
    COUNT(DISTINCT user_id)                              AS uv,
    COUNT(*)                                             AS total_events,
    COUNT(DISTINCT CAST(event_time AS DATE))              AS active_days
FROM events;
