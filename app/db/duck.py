"""DuckDB 连接：单文件列存分析库。

读写分离的设计：
- 建库脚本（scripts/build_db.py）持写连接灌数据
- 查询链路一律 read_only=True——天然保证 Agent 生成的 SQL 不可能改库，
  只读约束的第一道防线在连接层，而不是提示词层
"""

import duckdb

from app.core.config import get_settings


def get_conn(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = get_settings().db_path
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)
