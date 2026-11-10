"""建库：CSV → DuckDB 三张表（幂等，CREATE OR REPLACE）。

建完跑两条"业务人员视角"的示例查询当验收——
这两条也就是将来评测集里最典型的问题形状。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.duck import get_conn  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data" / "datasets"


def main() -> None:
    conn = get_conn()
    for table in ["products", "users", "orders"]:
        conn.execute(f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT * FROM read_csv_auto('{DATA / f"{table}.csv"}')
        """)
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n} 行")

    # 日期列显式转 DATE（read_csv_auto 偶尔推成 VARCHAR，分析查询要按日期切）
    conn.execute("ALTER TABLE orders ALTER order_date TYPE DATE")
    conn.execute("ALTER TABLE users ALTER register_date TYPE DATE")

    print("\n验收查询①（品类销售额 Top3，只算已完成订单）:")
    for row in conn.execute("""
        SELECT p.category, ROUND(SUM(o.amount),0) AS gmv
        FROM orders o JOIN products p USING(product_id)
        WHERE o.status='已完成'
        GROUP BY 1 ORDER BY gmv DESC LIMIT 3
    """).fetchall():
        print("  ", row)

    print("验收查询②（各渠道订单量与平均客单价）:")
    for row in conn.execute("""
        SELECT channel, COUNT(*) AS n, ROUND(AVG(amount),1) AS aov
        FROM orders WHERE status='已完成' GROUP BY 1 ORDER BY n DESC
    """).fetchall():
        print("  ", row)

    print("\n建库完成 →", conn.execute("SELECT current_database()").fetchone()[0])


if __name__ == "__main__":
    main()
