-- @name: funnel
-- @title: 用户行为转化漏斗
-- @desc: 点击 → (收藏 + 加购) → 购买 各环节的转化率。
--        注：收藏与加购按行为次数相加，同一用户两种行为都做会重复计数，
--        因此这里的漏斗是「行为级」而非「用户级」。

SELECT
    SUM(pv)  AS pv,
    SUM(fav) AS fav,
    SUM(cart) AS cart,
    SUM(fav) + SUM(cart) AS fav_cart,
    SUM(buy) AS buy,
    ROUND((SUM(fav) + SUM(cart))::DOUBLE / NULLIF(SUM(pv), 0), 4)          AS pv_to_favcart,
    ROUND(SUM(buy)::DOUBLE / NULLIF(SUM(fav) + SUM(cart), 0), 4)           AS favcart_to_buy,
    ROUND(SUM(buy)::DOUBLE / NULLIF(SUM(pv), 0), 4)                        AS pv_to_buy
FROM user_count;
