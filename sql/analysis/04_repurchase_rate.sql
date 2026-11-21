-- @name: repurchase_rate
-- @title: 复购率
-- @desc: 购买次数 ≥ 2 的用户占全部购买用户的比例。

SELECT
    SUM(CASE WHEN buy > 1 THEN 1 ELSE 0 END) AS repeat_buyers,
    SUM(CASE WHEN buy > 0 THEN 1 ELSE 0 END) AS buyers,
    ROUND(
        SUM(CASE WHEN buy > 1 THEN 1 ELSE 0 END)::DOUBLE
        / NULLIF(SUM(CASE WHEN buy > 0 THEN 1 ELSE 0 END), 0), 4
    )                                        AS repurchase_rate
FROM user_count;
