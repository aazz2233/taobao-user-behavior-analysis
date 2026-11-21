# legacy —— 优化前的原始脚本

这里保留项目重构前的全部代码，仅作对照与追溯，**不再维护**。

| 文件 | 原位置 | 说明 |
| --- | --- | --- |
| `run_analysis_v1.py` | `run_analysis.py` | DuckDB 单文件脚本：建表、清洗、13 项分析全部 `print` 到终端 |
| `../sql/hive/01_table.sql` | `table.sql` | 原始 Hive 建表 / 加载 / 清洗脚本 |
| `../sql/hive/02_analyse.sql` | `analyse.sql` | 原始 Hive 分析查询 |

两个 Hive 脚本在 `sql/hive/` 下，因为它们是这套指标口径的出处，对仍在使用
Hive 的读者依然有价值；`run_analysis_v1.py` 是本仓库的重点改造对象。

## 原脚本存在的问题

### 正确性

1. **Top 10 榜单其实是随机 10 行**
   `[11] R-Recency Top 10` 与 `[12] F-Frequency Top 10` 只写了 `LIMIT 10`，
   没有 `ORDER BY`。SQL 不保证返回顺序，这两张榜只是「随便 10 个用户」。
   新版见 `sql/analysis/10_rfm.sql`（合并为一条带完整排序的查询）。
2. **基准日写死**：`DATE '2017-12-04'` 硬编码在 SQL 里，换数据集就算错。
   新版从数据自身推导（`max(event_time)` 的次日）。
3. **依赖运行机器的时区**：`to_timestamp()` 按会话时区解释 Unix 秒。
   原脚本在 UTC 机器上运行会让日期边界和小时分布整体偏移 8 小时。
   新版显式转换：`to_timestamp(ts) AT TIME ZONE 'Asia/Shanghai'`。
4. **星期几靠取模公式**：`pmod(datediff(datetime,'1920-01-01') - 3, 7)`，
   正确性取决于纪元的星期数，难以复核。新版用 `dayofweek()` 显式计算。
5. **去重口径含派生列**：`GROUP BY` 里带上了本应推导出来的 `datetime` 字符串。

### 性能

6. **对 1 亿行做了 4 次全表写**：
   建表 → 全列 GROUP BY 去重 → 重写 `datetime` → 按日期过滤。
   每次都把整表重写一遍，磁盘 I/O 是必要量的数倍。
   新版合并为**一次扫描、一次落表**（见 `sql/build.sql`），实测 15.2 s。
7. **`datetime` 存 VARCHAR**：每行多存 19 字节字符串，且每条查询都要
   `CAST(datetime AS TIMESTAMP)` 才能取小时/日期。
   新版直接存 `TIMESTAMP`，库文件从 7.04 GiB 降到 1.39 GiB（−80%）。
8. **每张图都要重算**：`user_behavior_count` 之外的聚合都在分析时现算。

### 工程

9. **硬编码绝对路径** `D:\一亿条用户行为数据分析\...`，换台机器就跑不了。
   新版走 `--csv` / `--db` 参数，默认值自动探测。
10. **结果只打印**：无法复用、无法画图、无法进 CI。新版落 CSV + Markdown + PNG。
11. **没有测试**：清洗和漏斗口径都靠人眼看终端。
    新版有 30 个测试覆盖清洗等价性与每条 SQL 的口径。
12. **缺少 `.gitignore`**：3.6 GB 的 CSV 与 7.5 GB 的 `.db` 紧挨着代码，
    一次 `git add .` 就会把仓库撑爆。

## 运行旧脚本

需要自备 `duckdb`，并把脚本顶部的 `CSV_PATH` / `DB_PATH` 改成本机路径：

```bash
python legacy/run_analysis_v1.py
```
