-- @name: behavior_distribution
-- @title: 行为类型分布
-- @desc: 四种行为的次数与占比，是漏斗的上游明细。原脚本只打印后未做占比。

SELECT
    behavior_type,
    COUNT(*)                                                   AS events,
    ROUND(COUNT(*)::DOUBLE / SUM(COUNT(*)) OVER (), 4)          AS share
FROM events
GROUP BY behavior_type
ORDER BY events DESC;
