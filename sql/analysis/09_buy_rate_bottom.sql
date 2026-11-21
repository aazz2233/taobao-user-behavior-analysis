-- @name: buy_rate_bottom
-- @title: 购买率最低的用户（有购买行为）Top 10
-- @desc: 频繁浏览却几乎不下单的用户，通常是价格敏感或处于比价阶段。

SELECT
    user_id, pv, fav, cart, buy,
    ROUND(buy::DOUBLE / NULLIF(pv, 0), 4) AS buy_rate
FROM user_count
WHERE buy > 0 AND pv > 0
ORDER BY buy_rate ASC, pv DESC, user_id
LIMIT 10;
