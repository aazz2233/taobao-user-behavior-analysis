-- @name: top_items
-- @title: 销量最高的商品 Top 10
-- @desc: 按购买次数排序，同时给出曝光（pv）、收藏、加购，便于看单品转化。

SELECT
    item_id,
    SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
    SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
    SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy,
    ROUND(
        SUM(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END)::DOUBLE
        / NULLIF(SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END), 0), 4
    )                                                       AS buy_rate
FROM events
GROUP BY item_id
ORDER BY buy DESC, pv DESC, item_id
LIMIT 10;
