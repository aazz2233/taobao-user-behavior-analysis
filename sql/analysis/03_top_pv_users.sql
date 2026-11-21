-- @name: top_pv_users
-- @title: 点击量最多的用户 Top 10
-- @desc: 依据 user_count 取 pv 最高的用户，并给出其购买转化率。

SELECT
    user_id,
    pv,
    fav,
    cart,
    buy,
    ROUND(buy::DOUBLE / NULLIF(pv, 0), 4) AS buy_rate
FROM user_count
ORDER BY pv DESC, user_id
LIMIT 10;
