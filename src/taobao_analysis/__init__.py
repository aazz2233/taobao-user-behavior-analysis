"""淘宝用户行为数据分析（DuckDB 版）。

模块结构：
    db         —— 连接、建表、清洗
    analysis   —— 执行 sql/analysis 下的查询并导出结果
    charts     —— 由结果生成图表
    cli        —— 命令行入口
"""

__version__ = "2.0.0"

__all__ = ["__version__"]
