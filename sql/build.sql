/*
建表 + 清洗：**一次扫描**完成原脚本的三步
------------------------------------------------------------
原 run_analysis.py 对 1 亿行连续做了三次 CREATE OR REPLACE TABLE：
    ①全列 GROUP BY 去重 → ②重写 datetime 字符串列 → ③按日期过滤
每次都把整张表重写一遍（≈3 × 2 GB 写入）。这里合并成一条语句：

    读取 CSV → 用时间戳整数区间先过滤（谓词下推到 CSV 扫描）
            → 去重 → 转成北京时间 TIMESTAMP → 落表

占位符
------
{{csv}}            原始 CSV 路径
{{ts_start}}       起始 Unix 秒（含），对应 2017-11-25 00:00:00 +08:00
{{ts_end}}         结束 Unix 秒（不含），对应 2017-12-04 00:00:00 +08:00
*/

CREATE OR REPLACE TABLE events AS
WITH raw AS (
    SELECT
        CAST(user_id     AS BIGINT) AS user_id,
        CAST(item_id     AS BIGINT) AS item_id,
        CAST(category_id AS BIGINT) AS category_id,
        behavior_type,
        CAST(ts AS BIGINT)          AS ts
    FROM read_csv({{csv}},
        header = false,
        auto_detect = false,
        columns = {
            'user_id':       'VARCHAR',
            'item_id':       'VARCHAR',
            'category_id':   'VARCHAR',
            'behavior_type': 'VARCHAR',
            'ts':            'BIGINT'
        }
    )
    -- 2017-11-25 00:00:00 至 2017-12-03 23:59:59（北京时间）
    WHERE ts >= {{ts_start}}
      AND ts <  {{ts_end}}
)
SELECT DISTINCT
    user_id,
    item_id,
    category_id,
    behavior_type,
    -- Unix 秒 → 北京时间；显式指定时区，结果不随运行机器变化
    to_timestamp(ts) AT TIME ZONE 'Asia/Shanghai' AS event_time
FROM raw;
