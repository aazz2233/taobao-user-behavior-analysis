/*
用户行为数据分析脚本
依赖：table.sql 已执行完毕，user_behavior 表已就绪
*/

-- ============================================
-- Hive 运行参数配置
-- ============================================
set hive.exec.parallel=true;
set hive.exec.parallel.thread.number=8;
set hive.mapred.mode=nonstrict;
-- 若需使用 Spark/Tez 引擎，取消下面注释：
-- set hive.execution.engine=spark;


-- ============================================
-- 一、用户流量及购物情况
-- ============================================

-- 1.1 总访问量 PV，总用户量 UV
select sum(case when behavior_type = 'pv' then 1 else 0 end) as pv,
       count(distinct user_id) as uv
from user_behavior;

-- 1.2 日均访问量，日均用户量
select to_date(datetime) as day,
       sum(case when behavior_type = 'pv' then 1 else 0 end) as pv,
       count(distinct user_id) as uv
from user_behavior
group by to_date(datetime)
order by day;

-- 1.3 每个用户的购物行为汇总
drop table if exists user_behavior_count;
create table user_behavior_count as
select user_id,
       sum(case when behavior_type = 'pv'   then 1 else 0 end) as pv,    -- 点击数
       sum(case when behavior_type = 'fav'  then 1 else 0 end) as fav,   -- 收藏数
       sum(case when behavior_type = 'cart' then 1 else 0 end) as cart,  -- 加购物车数
       sum(case when behavior_type = 'buy'  then 1 else 0 end) as buy    -- 购买数
from user_behavior
group by user_id;

-- 1.4 点击数最多的用户 Top 10
select * from user_behavior_count order by pv desc limit 10;

-- 1.5 复购率：产生两次或两次以上购买的用户占购买用户的比例
select sum(case when buy > 1 then 1 else 0 end) / sum(case when buy > 0 then 1 else 0 end) as repurchase_rate
from user_behavior_count;


-- ============================================
-- 二、用户行为转化漏斗
-- ============================================

-- 点击 → (加购物车 + 收藏) → 购买，各环节转化率
select a.pv,
       a.fav,
       a.cart,
       a.fav + a.cart as `fav_cart`,           -- Hive 中避免使用 + 号别名
       a.buy,
       round((a.fav + a.cart) / a.pv, 4)       as pv2favcart,
       round(a.buy / (a.fav + a.cart), 4)      as favcart2buy,
       round(a.buy / a.pv, 4)                  as pv2buy
from (
    select sum(pv)   as pv,     -- 点击数
           sum(fav)  as fav,    -- 收藏数
           sum(cart) as cart,   -- 加购物车数
           sum(buy)  as buy     -- 购买数
    from user_behavior_count
) as a;


-- ============================================
-- 三、用户行为习惯与人群特征
-- ============================================

-- 3.1 一天的活跃时段分布
select hour(datetime) as hour,
       sum(case when behavior_type = 'pv'   then 1 else 0 end) as pv,    -- 点击数
       sum(case when behavior_type = 'fav'  then 1 else 0 end) as fav,   -- 收藏数
       sum(case when behavior_type = 'cart' then 1 else 0 end) as cart,  -- 加购物车数
       sum(case when behavior_type = 'buy'  then 1 else 0 end) as buy    -- 购买数
from user_behavior
group by hour(datetime)
order by hour;

-- 3.2 一周用户的活跃分布
-- 使用 pmod 公式计算星期几：0 = 周一, 1 = 周二, ..., 6 = 周日
select pmod(datediff(datetime, '1920-01-01') - 3, 7) as weekday,
       sum(case when behavior_type = 'pv'   then 1 else 0 end) as pv,    -- 点击数
       sum(case when behavior_type = 'fav'  then 1 else 0 end) as fav,   -- 收藏数
       sum(case when behavior_type = 'cart' then 1 else 0 end) as cart,  -- 加购物车数
       sum(case when behavior_type = 'buy'  then 1 else 0 end) as buy    -- 购买数
from user_behavior
where to_date(datetime) between '2017-11-27' and '2017-12-03'
group by pmod(datediff(datetime, '1920-01-01') - 3, 7)
order by weekday;

-- 3.3 购买率最高的用户 Top 10
select *, buy / pv as buy_rate
from user_behavior_count
where buy > 0 and pv > 0
order by buy_rate desc
limit 10;

-- 3.4 购买率最低的用户（有购买行为）Top 10
select *, buy / pv as buy_rate
from user_behavior_count
where buy > 0 and pv > 0
order by buy_rate
limit 10;


-- ============================================
-- 四、基于 RFM 模型找出有价值的用户
-- ============================================

/*
RFM 模型说明：
  R - Recency（最近一次购买时间），值越小说明越活跃
  F - Frequency（消费频率），值越大说明越忠诚
  M - Money（消费金额），本数据集无金额字段，暂用 R + F 打分

评分规则：
  将用户按 R_rank 和 F_rank 分别 ntile(5) 分组，
  前 20% 打5分，20%-40% 打4分，...，后 20% 打1分
  最终得分 = R_score + F_score
*/

-- 4.1 R-Recency（最近一次购买时间）
select user_id,
       datediff('2017-12-04', max(datetime)) as R,
       dense_rank() over(order by datediff('2017-12-04', max(datetime))) as R_rank
from user_behavior
where behavior_type = 'buy'
group by user_id
limit 10;

-- 4.2 F-Frequency（消费频率）
select user_id,
       count(1) as F,
       dense_rank() over(order by count(1) desc) as F_rank
from user_behavior
where behavior_type = 'buy'
group by user_id
limit 10;

-- 4.3 综合评分（R + F）
with cte as (
    select user_id,
           datediff('2017-12-04', max(datetime)) as R,
           dense_rank() over(order by datediff('2017-12-04', max(datetime))) as R_rank,
           count(1) as F,
           dense_rank() over(order by count(1) desc) as F_rank
    from user_behavior
    where behavior_type = 'buy'
    group by user_id
)
select user_id,
       R,
       R_rank,
       R_score,
       F,
       F_rank,
       F_score,
       R_score + F_score as score
from (
    select *,
           case ntile(5) over(order by R_rank)
               when 1 then 5
               when 2 then 4
               when 3 then 3
               when 4 then 2
               when 5 then 1
           end as R_score,
           case ntile(5) over(order by F_rank)
               when 1 then 5
               when 2 then 4
               when 3 then 3
               when 4 then 2
               when 5 then 1
           end as F_score
    from cte
) as a
order by score desc
limit 20;


-- ============================================
-- 五、商品维度的分析
-- ============================================

-- 5.1 销量最高的商品 Top 10
select item_id,
       sum(case when behavior_type = 'pv'   then 1 else 0 end) as pv,    -- 点击数
       sum(case when behavior_type = 'fav'  then 1 else 0 end) as fav,   -- 收藏数
       sum(case when behavior_type = 'cart' then 1 else 0 end) as cart,  -- 加购物车数
       sum(case when behavior_type = 'buy'  then 1 else 0 end) as buy    -- 购买数
from user_behavior
group by item_id
order by buy desc
limit 10;

-- 5.2 销量最高的商品类目 Top 10
select category_id,
       sum(case when behavior_type = 'pv'   then 1 else 0 end) as pv,    -- 点击数
       sum(case when behavior_type = 'fav'  then 1 else 0 end) as fav,   -- 收藏数
       sum(case when behavior_type = 'cart' then 1 else 0 end) as cart,  -- 加购物车数
       sum(case when behavior_type = 'buy'  then 1 else 0 end) as buy    -- 购买数
from user_behavior
group by category_id
order by buy desc
limit 10;
