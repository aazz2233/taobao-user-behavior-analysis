/*
按用户的行为汇总表 user_count
------------------------------------------------------------
一次全表扫描得到每个用户的 pv / fav / cart / buy，
后续的漏斗、复购率、购买率榜单、RFM 都复用它，
避免在每条分析里重复 GROUP BY 1 亿行。
*/

CREATE OR REPLACE TABLE user_count AS
SELECT
    user_id,
    SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
    SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
    SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy
FROM events
GROUP BY user_id;
