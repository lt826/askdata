"""NL→SQL 生成层：Schema 白话注入 + 只读约束 + few-shot + 今天日期注入。

设计要点：
- 今天日期必须注入——"上个月/最近30天"的相对时间，模型不知道今天几号就会瞎猜年份
- few-shot 选例覆盖三种最高频错误形状：跨表 join、业绩口径(status)、相对时间窗
- 输出解析要扒掉 ```sql 围栏——模型几乎总会加围栏，直接 text 当 SQL 执行必报错
"""

import re
from datetime import date

from app.core.llm import chat
from app.db.schema_doc import get_schema_doc

SYSTEM_TEMPLATE = """你是 DuckDB 的 SQL 专家。今天是 {today}。

{schema}

## 生成规则（必须遵守）
1. 只生成一条只读 SELECT 语句（可用 WITH 子查询），禁止任何写操作
2. 业绩统计（销售额/GMV/客单价/销量）只算 status='已完成' 的订单
3. "上个月/最近N天/今年"等相对时间，用 CURRENT_DATE 算出明确日期边界放进 WHERE
4. TopN 类问题用 ORDER BY ... DESC + LIMIT
5. 只输出一条 SQL，放在 ```sql 代码块中，不要任何解释

## 示例

问：上个月各渠道的销售额是多少？
```sql
SELECT channel, ROUND(SUM(amount), 2) AS sales
FROM orders
WHERE status = '已完成'
  AND order_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL 1 MONTH)
  AND order_date < DATE_TRUNC('month', CURRENT_DATE)
GROUP BY channel
ORDER BY sales DESC;
```

问：销售额最高的前五个商品（含品牌和品类）
```sql
SELECT p.product_name, p.brand, p.category,
       ROUND(SUM(o.amount), 2) AS sales
FROM orders o
JOIN products p ON o.product_id = p.product_id
WHERE o.status = '已完成'
GROUP BY 1, 2, 3
ORDER BY sales DESC
LIMIT 5;
```"""


def extract_sql(text: str) -> str:
    """从模型回复里扒 SQL：优先 ```sql 围栏，退化到裸文本。"""
    m = re.search(r"```sql\s*(.+?)```", text, re.S | re.I)
    sql = m.group(1) if m else text.strip()
    # 去掉可能的尾部分号后再规范：单语句保留一个分号都不影响 duckdb，直接 strip
    return sql.strip().rstrip(";").strip()


def generate_sql(question: str) -> str:
    messages = [
        {"role": "system",
         "content": SYSTEM_TEMPLATE.format(today=date.today().isoformat(),
                                           schema=get_schema_doc())},
        {"role": "user", "content": f"问：{question}"},
    ]
    return extract_sql(chat(messages, temperature=0))
