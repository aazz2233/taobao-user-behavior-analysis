"""
淘宝用户行为数据分析 - DuckDB 执行脚本
将原 HQL 适配为 DuckDB SQL，在 Windows 本地运行
数据: UserBehavior.csv (3.67 GB, 100M+ 条记录)
"""
import duckdb
import time
import os

CSV_PATH = r"D:\一亿条用户行为数据分析\UserBehavior.csv"
DB_PATH  = r"D:\一亿条用户行为数据分析\user_behavior.db"

# 如果已有数据库文件，直接复用；否则重新创建
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
con = duckdb.connect(DB_PATH)

con.execute("SET threads TO 8")
con.execute("SET memory_limit = '8GB'")

print("=" * 70)
print("DuckDB 淘宝用户行为数据分析")
print(f"数据源: {CSV_PATH}")
print(f"数据库: {DB_PATH}")
print("=" * 70)

# ============================================================
# 1. 建表 & 加载数据
# ============================================================
print("\n[1/9] 加载 CSV 数据...")
t0 = time.time()

# 如果表已存在则跳过加载
table_exists = con.execute(
    "SELECT count(*) FROM information_schema.tables WHERE table_name = 'user_behavior'"
).fetchone()[0]

if table_exists == 0:
    con.execute(f"""
        CREATE TABLE user_behavior AS
        SELECT
            column0 AS user_id,
            column1 AS item_id,
            column2 AS category_id,
            column3 AS behavior_type,
            column4::BIGINT AS timestamp,
            strftime(to_timestamp(column4::BIGINT), '%Y-%m-%d %H:%M:%S') AS datetime
        FROM read_csv('{CSV_PATH}',
            header=false,
            columns={{'column0': 'VARCHAR', 'column1': 'VARCHAR', 'column2': 'VARCHAR',
                      'column3': 'VARCHAR', 'column4': 'BIGINT'}},
            auto_detect=false
        )
    """)
    print(f"   加载完成，耗时 {time.time() - t0:.1f}s")
else:
    print(f"   表已存在，跳过加载。")

# 查看数据样例
print("   数据样例:")
result = con.execute("SELECT * FROM user_behavior LIMIT 5").fetchall()
for row in result:
    print(f"   {row}")

# ============================================================
# 2. 查看总记录数
# ============================================================
print("\n[2/9] 总记录数:")
cnt = con.execute("SELECT count(1) FROM user_behavior").fetchone()[0]
print(f"   {cnt:,} 条")

# ============================================================
# 3. 数据清洗 - 去重
# ============================================================
print("\n[3/9] 数据清洗 - 去重...")
t0 = time.time()
# DuckDB: 用 CREATE OR REPLACE 模拟 insert overwrite
con.execute("""
    CREATE OR REPLACE TABLE user_behavior AS
    SELECT user_id, item_id, category_id, behavior_type, timestamp, datetime
    FROM user_behavior
    GROUP BY user_id, item_id, category_id, behavior_type, timestamp, datetime
""")
cnt_after = con.execute("SELECT count(1) FROM user_behavior").fetchone()[0]
print(f"   去重后: {cnt_after:,} 条，耗时 {time.time() - t0:.1f}s")

# ============================================================
# 4. 时间戳格式化 (数据加载时已完成，此处确保 datetime 正确)
# ============================================================
print("\n[4/9] 确保 datetime 列正确...")
con.execute("""
    CREATE OR REPLACE TABLE user_behavior AS
    SELECT user_id, item_id, category_id, behavior_type, timestamp,
           strftime(to_timestamp(timestamp), '%Y-%m-%d %H:%M:%S') AS datetime
    FROM user_behavior
""")

# ============================================================
# 5. 查看时间范围
# ============================================================
print("\n[5/9] 数据日期范围:")
days = con.execute("""
    SELECT CAST(datetime AS DATE) AS day
    FROM user_behavior
    GROUP BY CAST(datetime AS DATE)
    ORDER BY day
""").fetchall()
for d in days:
    print(f"   {d[0]}")

# ============================================================
# 6. 数据清洗 - 过滤异常时间
# ============================================================
print("\n[6/9] 数据清洗 - 过滤时间异常数据（保留 2017-11-25 ~ 2017-12-03）...")
t0 = time.time()
con.execute("""
    CREATE OR REPLACE TABLE user_behavior AS
    SELECT *
    FROM user_behavior
    WHERE CAST(datetime AS DATE) BETWEEN '2017-11-25' AND '2017-12-03'
""")
cnt_after2 = con.execute("SELECT count(1) FROM user_behavior").fetchone()[0]
print(f"   过滤后: {cnt_after2:,} 条，耗时 {time.time() - t0:.1f}s")

# ============================================================
# 7. 查看 behavior_type 分布
# ============================================================
print("\n[7/9] behavior_type 分布:")
types = con.execute("""
    SELECT behavior_type, count(1) AS cnt
    FROM user_behavior
    GROUP BY behavior_type
    ORDER BY cnt DESC
""").fetchall()
for t in types:
    print(f"   {t[0]}: {t[1]:,}")

# ============================================================
# 8. 最终数据量
# ============================================================
print("\n[8/9] 清洗后最终数据量:")
final_cnt = con.execute("SELECT count(1) FROM user_behavior").fetchone()[0]
print(f"   {final_cnt:,} 条")

# ============================================================
# 9. 分析查询
# ============================================================
print("\n" + "=" * 70)
print("[9/9] 分析查询")
print("=" * 70)

# --- 一、用户流量及购物情况 ---
print("\n--- 一、用户流量及购物情况 ---")

# 总访问量 PV，总用户量 UV
print("\n[1] 总访问量 PV / 总用户量 UV:")
r = con.execute("""
    SELECT
        SUM(CASE WHEN behavior_type = 'pv'  THEN 1 ELSE 0 END) AS pv,
        COUNT(DISTINCT user_id) AS uv
    FROM user_behavior
""").fetchone()
print(f"   PV: {r[0]:,}")
print(f"   UV: {r[1]:,}")

# 日均访问量，日均用户量
print("\n[2] 日均访问量 / 日均用户量:")
daily = con.execute("""
    SELECT CAST(datetime AS DATE) AS day,
           SUM(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) AS pv,
           COUNT(DISTINCT user_id) AS uv
    FROM user_behavior
    GROUP BY CAST(datetime AS DATE)
    ORDER BY day
""").fetchall()
for d in daily:
    print(f"   {d[0]}  PV={d[1]:,}  UV={d[2]:,}")

# 用户购物行为汇总
print("\n[3] 用户购物行为汇总表 (user_behavior_count):")
con.execute("DROP TABLE IF EXISTS user_behavior_count")
con.execute("""
    CREATE TABLE user_behavior_count AS
    SELECT user_id,
           SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
           SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
           SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
           SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy
    FROM user_behavior
    GROUP BY user_id
""")
cnt_ubc = con.execute("SELECT count(1) FROM user_behavior_count").fetchone()[0]
print(f"   用户数: {cnt_ubc:,}")

# Top 10 点击用户
print("\n[4] 点击数最多的用户 Top 10:")
top_pv = con.execute("""
    SELECT * FROM user_behavior_count ORDER BY pv DESC LIMIT 10
""").fetchall()
for r in top_pv:
    print(f"   user_id={r[0]}  pv={r[1]:,}  fav={r[2]}  cart={r[3]}  buy={r[4]}")

# 复购率
print("\n[5] 复购率:")
repurchase = con.execute("""
    SELECT
        SUM(CASE WHEN buy > 1 THEN 1 ELSE 0 END) AS repeat_buyers,
        SUM(CASE WHEN buy > 0 THEN 1 ELSE 0 END) AS total_buyers,
        ROUND(CAST(SUM(CASE WHEN buy > 1 THEN 1 ELSE 0 END) AS DOUBLE) /
              NULLIF(SUM(CASE WHEN buy > 0 THEN 1 ELSE 0 END), 0), 4) AS repurchase_rate
    FROM user_behavior_count
""").fetchone()
print(f"   复购用户: {repurchase[0]:,}  购买用户: {repurchase[1]:,}  复购率: {repurchase[2]}")

# --- 二、用户行为转化漏斗 ---
print("\n--- 二、用户行为转化漏斗 ---")
print("\n[6] 转化漏斗:")
funnel = con.execute("""
    SELECT a.pv, a.fav, a.cart, a.fav + a.cart AS fav_cart, a.buy,
           ROUND(CAST(a.fav + a.cart AS DOUBLE) / NULLIF(a.pv, 0), 4) AS pv2favcart,
           ROUND(CAST(a.buy AS DOUBLE) / NULLIF(a.fav + a.cart, 0), 4) AS favcart2buy,
           ROUND(CAST(a.buy AS DOUBLE) / NULLIF(a.pv, 0), 4) AS pv2buy
    FROM (
        SELECT SUM(pv) AS pv, SUM(fav) AS fav,
               SUM(cart) AS cart, SUM(buy) AS buy
        FROM user_behavior_count
    ) AS a
""").fetchone()
print(f"   点击(PV):     {funnel[0]:,}")
print(f"   收藏(Fav):    {funnel[1]:,}")
print(f"   加购(Cart):   {funnel[2]:,}")
print(f"   收藏+加购:    {funnel[3]:,}")
print(f"   购买(Buy):    {funnel[4]:,}")
print(f"   PV→(Fav+Cart): {funnel[5]}")
print(f"   (Fav+Cart)→Buy: {funnel[6]}")
print(f"   PV→Buy:        {funnel[7]}")

# --- 三、用户行为习惯与人群特征 ---
print("\n--- 三、用户行为习惯与人群特征 ---")

# 一天活跃时段分布
print("\n[7] 一天活跃时段分布:")
hourly = con.execute("""
    SELECT EXTRACT(HOUR FROM CAST(datetime AS TIMESTAMP)) AS hour,
           SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
           SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
           SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
           SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy
    FROM user_behavior
    GROUP BY EXTRACT(HOUR FROM CAST(datetime AS TIMESTAMP))
    ORDER BY hour
""").fetchall()
print(f"   {'Hour':>5}  {'PV':>12}  {'Fav':>8}  {'Cart':>8}  {'Buy':>8}")
for r in hourly:
    print(f"   {r[0]:>5}  {r[1]:>12,}  {r[2]:>8,}  {r[3]:>8,}  {r[4]:>8,}")

# 一周活跃分布
print("\n[8] 一周活跃分布 (0=Mon, 6=Sun):")
weekly = con.execute("""
    SELECT MOD(DATEDIFF('day', DATE '1920-01-01', CAST(datetime AS DATE)) - 3, 7) AS weekday,
           SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
           SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
           SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
           SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy
    FROM user_behavior
    WHERE CAST(datetime AS DATE) BETWEEN '2017-11-27' AND '2017-12-03'
    GROUP BY MOD(DATEDIFF('day', DATE '1920-01-01', CAST(datetime AS DATE)) - 3, 7)
    ORDER BY weekday
""").fetchall()
weekday_names = {0: '周一', 1: '周二', 2: '周三', 3: '周四', 4: '周五', 5: '周六', 6: '周日'}
print(f"   {'Weekday':>6}  {'PV':>12}  {'Fav':>8}  {'Cart':>8}  {'Buy':>8}")
for r in weekly:
    print(f"   {weekday_names.get(r[0], str(r[0])):>6}  {r[1]:>12,}  {r[2]:>8,}  {r[3]:>8,}  {r[4]:>8,}")

# 购买率最高的用户
print("\n[9] 购买率最高的用户 Top 10:")
buy_high = con.execute("""
    SELECT *, CAST(buy AS DOUBLE) / NULLIF(pv, 0) AS buy_rate
    FROM user_behavior_count
    WHERE buy > 0 AND pv > 0
    ORDER BY buy_rate DESC
    LIMIT 10
""").fetchall()
for r in buy_high:
    print(f"   user_id={r[0]}  pv={r[1]}  buy={r[4]}  buy_rate={r[5]:.4f}")

# 购买率最低的用户
print("\n[10] 购买率最低的用户 Top 10:")
buy_low = con.execute("""
    SELECT *, CAST(buy AS DOUBLE) / NULLIF(pv, 0) AS buy_rate
    FROM user_behavior_count
    WHERE buy > 0 AND pv > 0
    ORDER BY buy_rate
    LIMIT 10
""").fetchall()
for r in buy_low:
    print(f"   user_id={r[0]}  pv={r[1]}  buy={r[4]}  buy_rate={r[5]:.4f}")

# --- 四、RFM 模型 ---
print("\n--- 四、基于 RFM 模型找出有价值的用户 ---")

print("\n[11] R-Recency（最近一次购买时间）Top 10:")
r_score = con.execute("""
    SELECT user_id,
           DATEDIFF('day', CAST(max(datetime) AS DATE), DATE '2017-12-04') AS R,
           DENSE_RANK() OVER(ORDER BY DATEDIFF('day', CAST(max(datetime) AS DATE), DATE '2017-12-04')) AS R_rank
    FROM user_behavior
    WHERE behavior_type = 'buy'
    GROUP BY user_id
    LIMIT 10
""").fetchall()
for r in r_score:
    print(f"   user_id={r[0]}  R={r[1]}  R_rank={r[2]}")

print("\n[12] F-Frequency（消费频率）Top 10:")
f_score = con.execute("""
    SELECT user_id,
           count(1) AS F,
           DENSE_RANK() OVER(ORDER BY count(1) DESC) AS F_rank
    FROM user_behavior
    WHERE behavior_type = 'buy'
    GROUP BY user_id
    LIMIT 10
""").fetchall()
for r in f_score:
    print(f"   user_id={r[0]}  F={r[1]}  F_rank={r[2]}")

print("\n[13] RFM 综合评分 Top 20:")
rfm = con.execute("""
    WITH cte AS (
        SELECT user_id,
               DATEDIFF('day', CAST(max(datetime) AS DATE), DATE '2017-12-04') AS R,
               DENSE_RANK() OVER(ORDER BY DATEDIFF('day', CAST(max(datetime) AS DATE), DATE '2017-12-04')) AS R_rank,
               count(1) AS F,
               DENSE_RANK() OVER(ORDER BY count(1) DESC) AS F_rank
        FROM user_behavior
        WHERE behavior_type = 'buy'
        GROUP BY user_id
    )
    SELECT user_id, R, R_rank, R_score, F, F_rank, F_score, R_score + F_score AS score
    FROM (
        SELECT *,
               CASE NTILE(5) OVER(ORDER BY R_rank)
                   WHEN 1 THEN 5 WHEN 2 THEN 4 WHEN 3 THEN 3 WHEN 4 THEN 2 WHEN 5 THEN 1
               END AS R_score,
               CASE NTILE(5) OVER(ORDER BY F_rank)
                   WHEN 1 THEN 5 WHEN 2 THEN 4 WHEN 3 THEN 3 WHEN 4 THEN 2 WHEN 5 THEN 1
               END AS F_score
        FROM cte
    ) AS a
    ORDER BY score DESC
    LIMIT 20
""").fetchall()
print(f"   {'user_id':<15} {'R':>4} {'R_rank':>8} {'R_score':>8} {'F':>5} {'F_rank':>8} {'F_score':>8} {'Score':>6}")
for r in rfm:
    print(f"   {r[0]:<15} {r[1]:>4} {r[2]:>8} {r[3]:>8} {r[4]:>5} {r[5]:>8} {r[6]:>8} {r[7]:>6}")

# --- 五、商品维度分析 ---
print("\n--- 五、商品维度的分析 ---")

print("\n[14] 销量最高的商品 Top 10:")
top_items = con.execute("""
    SELECT item_id,
           SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
           SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
           SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
           SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy
    FROM user_behavior
    GROUP BY item_id
    ORDER BY buy DESC
    LIMIT 10
""").fetchall()
print(f"   {'item_id':<15} {'PV':>10} {'Fav':>8} {'Cart':>8} {'Buy':>8}")
for r in top_items:
    print(f"   {r[0]:<15} {r[1]:>10,} {r[2]:>8,} {r[3]:>8,} {r[4]:>8,}")

print("\n[15] 销量最高的商品类目 Top 10:")
top_cats = con.execute("""
    SELECT category_id,
           SUM(CASE WHEN behavior_type = 'pv'   THEN 1 ELSE 0 END) AS pv,
           SUM(CASE WHEN behavior_type = 'fav'  THEN 1 ELSE 0 END) AS fav,
           SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart,
           SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy
    FROM user_behavior
    GROUP BY category_id
    ORDER BY buy DESC
    LIMIT 10
""").fetchall()
print(f"   {'category_id':<15} {'PV':>10} {'Fav':>8} {'Cart':>8} {'Buy':>8}")
for r in top_cats:
    print(f"   {r[0]:<15} {r[1]:>10,} {r[2]:>8,} {r[3]:>8,} {r[4]:>8,}")

# ============================================================
# 完成
# ============================================================
print("\n" + "=" * 70)
print("分析完成！")
print(f"数据库文件: {DB_PATH}")
print("=" * 70)

con.close()
