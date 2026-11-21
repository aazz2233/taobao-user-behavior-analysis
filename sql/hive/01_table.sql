/*
说明：淘宝用户行为数据
来源：https://tianchi.aliyun.com/dataset/dataDetail?dataId=649&userId=1
大小：3.5 G
记录数：100,150,807
字段数：5（user_id, item_id, category_id, behavior_type, timestamp）
注意：CSV 只有 5 列，datetime 列在数据清洗时通过 from_unixtime 生成
*/

-- ============================================
-- Hive 运行参数配置（根据实际环境调整）
-- ============================================

-- 设置执行引擎为 MapReduce（或改为 spark / tez）
-- set hive.execution.engine=mr;

-- 开启并行执行
set hive.exec.parallel=true;
set hive.exec.parallel.thread.number=8;

-- 动态分区设置
set hive.exec.dynamic.partition=true;
set hive.exec.dynamic.partition.mode=nonstrict;

-- 压缩输出
set hive.exec.compress.output=true;
set mapreduce.output.fileoutputformat.compress=true;

-- 内存设置（根据实际集群资源调整）
-- set mapreduce.map.memory.mb=4096;
-- set mapreduce.reduce.memory.mb=4096;
-- set yarn.app.mapreduce.am.resource.mb=4096;


-- ============================================
-- 0. 选择数据库（根据实际环境修改数据库名）
-- ============================================
-- use your_database_name;


-- ============================================
-- 1. 建表
-- ============================================
-- 注意：CSV 只有 5 列，datetime 列在加载后通过清洗步骤补充
drop table if exists user_behavior;
create table user_behavior (
    `user_id`       string  comment '用户ID',
    `item_id`       string  comment '商品ID',
    `category_id`   string  comment '商品类目ID',
    `behavior_type` string  comment '行为类型，枚举类型，包括(pv, buy, cart, fav)',
    `timestamp`     bigint  comment '行为时间戳（Unix秒级时间戳）',
    `datetime`      string  comment '行为时间（清洗后填充）'
)
row format delimited
fields terminated by ','
lines terminated by '\n'
stored as textfile;


-- ============================================
-- 2. 加载数据
-- ============================================
-- 【重要】根据实际环境选择以下方式之一：

-- 方式A：从 Hive 服务器本地文件系统加载（原脚本路径，Linux 环境）
-- LOAD DATA LOCAL INPATH '/home/getway/UserBehavior.csv'
-- OVERWRITE INTO TABLE user_behavior;

-- 方式B：从 HDFS 加载（推荐生产环境使用）
-- 先上传到 HDFS：
--   hadoop fs -put D:/一亿条用户行为数据分析/UserBehavior.csv /user/hive/warehouse/
-- 然后加载：
-- LOAD DATA INPATH '/user/hive/warehouse/UserBehavior.csv'
-- OVERWRITE INTO TABLE user_behavior;

-- 方式C：从本地加载（如果 Hive 服务器运行在 Windows 上，或使用 Hive 本地模式）
LOAD DATA LOCAL INPATH 'D:/一亿条用户行为数据分析/UserBehavior.csv'
OVERWRITE INTO TABLE user_behavior;

-- 如果上面路径报错，请在 Hive CLI 中手动执行：
--   LOAD DATA LOCAL INPATH '<你的CSV文件绝对路径>' OVERWRITE INTO TABLE user_behavior;


-- ============================================
-- 3. 查看数据（快速验证）
-- ============================================
select * from user_behavior limit 10;

-- 查看总记录数
select count(1) from user_behavior;


-- ============================================
-- 4. 数据清洗：去掉完全重复的数据
-- ============================================
insert overwrite table user_behavior
select user_id, item_id, category_id, behavior_type, timestamp, datetime
from user_behavior
group by user_id, item_id, category_id, behavior_type, timestamp, datetime;

-- 清洗后记录数
select count(1) from user_behavior;


-- ============================================
-- 5. 数据清洗：时间戳格式化成 datetime
-- ============================================
-- CSV 中没有 datetime 列（加载后为 NULL），此步骤从 timestamp 生成 datetime
insert overwrite table user_behavior
select user_id,
       item_id,
       category_id,
       behavior_type,
       timestamp,
       from_unixtime(timestamp, 'yyyy-MM-dd HH:mm:ss') as datetime
from user_behavior;


-- ============================================
-- 6. 查看时间是否有异常值
-- ============================================
select date(datetime) as day
from user_behavior
group by date(datetime)
order by day;


-- ============================================
-- 7. 数据清洗：去掉时间异常的数据
-- ============================================
-- 只保留 2017-11-25 到 2017-12-03 之间的数据
insert overwrite table user_behavior
select user_id, item_id, category_id, behavior_type, timestamp, datetime
from user_behavior
where to_date(datetime) between '2017-11-25' and '2017-12-03';


-- ============================================
-- 8. 查看 behavior_type 是否有异常值
-- ============================================
select behavior_type
from user_behavior
group by behavior_type;


-- ============================================
-- 9. 最终数据量确认
-- ============================================
select count(1) as total_records from user_behavior;
