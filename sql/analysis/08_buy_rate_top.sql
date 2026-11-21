-- @name: buy_rate_top
-- @title: 购买率最高的用户 Top 10
-- @desc: 仅统计 buy > 0 且 pv ≥ 10 的用户。
--        原口径不设浏览下限，会让「只看了 1 次却买了 262 次」的异常用户
--        （疑似批发/爬虫账号）以 buy_rate=262 占据榜首，榜单失去解释力。

SELECT
    user_id, pv, fav, cart, buy,
    ROUND(buy::DOUBLE / NULLIF(pv, 0), 4) AS buy_rate
FROM user_count
WHERE buy > 0
  AND pv >= 10
ORDER BY buy_rate DESC, buy DESC, user_id
LIMIT 10;
