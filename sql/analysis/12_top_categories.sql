-- @name: top_categories
-- @title: 销量最高的商品类目 Top 10
-- @desc: 与单品榜同口径，用于判断哪些一级类目贡献了主要成交。

SELECT
    category_id,
    SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
    SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
    SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy,
    ROUND(
        SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END)::DOUBLE
        / NULLIF(SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END), 0), 4
    )                                                       AS buy_rate
FROM events
GROUP BY category_id
ORDER BY buy DESC, pv DESC, category_id
LIMIT 10;
