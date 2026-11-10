"""Schema 白话层：注入给 LLM 的表结构卡片（手写，不自动生成——这是 SQL 准确率的命门）。

设计原则：
- 每列给"业务含义"而不是干巴巴的列名（revenue 不如"订单实付金额，含折扣"）
- 枚举值全部列全——模型不知道有哪些城市/渠道/状态，就会编造 WHERE 条件
- join 路径显式写明——跨表题错 join 是最高频错误
- 示例行给 2~3 条锚点，帮模型对齐格式（如 order_id 的 O 前缀）
"""

SCHEMA_DOC = """## 数据库：sales（电商订单分析库，近一年数据）

### 表 orders —— 订单流水（事实表，10 万行）
| 列 | 类型 | 业务含义 |
|---|---|---|
| order_id | VARCHAR | 订单号，主键，形如 O000042 |
| user_id | VARCHAR | 下单用户 → users.user_id |
| product_id | VARCHAR | 购买商品 → products.product_id |
| quantity | INTEGER | 购买件数（1~5） |
| unit_price | DOUBLE | 成交单价（已含折扣），元 |
| amount | DOUBLE | 订单实付金额 = quantity × unit_price，元。算"销售额/GMV"用它 |
| order_date | DATE | 下单日期，2025-11-11 ~ 2026-11-10 |
| channel | VARCHAR | 下单渠道，枚举：App / 小程序 / 网页 / 门店 |
| status | VARCHAR | 订单状态，枚举：已完成 / 已取消 / 退款中 / 已退款 |

⚠️ 统计销售额、客单价、销量等真实业绩时，**必须加 `WHERE status='已完成'`**（已取消/退款的订单不算业绩）。

示例行：('O000042','U01337','P0231',1,4599.0,4599.0,'2026-11-11','App','已完成')

### 表 users —— 用户（维度表，2 万行）
| 列 | 类型 | 业务含义 |
|---|---|---|
| user_id | VARCHAR | 用户ID，主键，形如 U01337 |
| gender | VARCHAR | 性别，枚举：男 / 女 |
| age | INTEGER | 年龄，16~70 |
| city | VARCHAR | 所在城市，枚举：上海/北京/广州/深圳/杭州/成都/武汉/南京/重庆/西安 |
| register_date | DATE | 注册日期（近 3 年内） |
| member_level | VARCHAR | 会员等级，枚举：普通 / 银卡 / 金卡 / 钻石 |

### 表 products —— 商品（维度表，498 行）
| 列 | 类型 | 业务含义 |
|---|---|---|
| product_id | VARCHAR | 商品ID，主键，形如 P0231 |
| product_name | VARCHAR | 商品名 = 品牌+子类，如"声浪耳机" |
| category | VARCHAR | 一级品类，枚举：数码家电/服饰鞋包/美妆个护/食品饮料/家居日用/运动户外 |
| subcategory | VARCHAR | 二级子类，如 手机/卫衣/面霜/坚果 |
| brand | VARCHAR | 品牌 |
| unit_price | DOUBLE | 商品原价（挂牌价）。订单实际成交价看 orders.unit_price |
| cost_price | DOUBLE | 成本价。毛利 = amount - cost_price×quantity（需 join 后计算） |

### Join 路径（跨表分析必看）
- orders.user_id = users.user_id（看用户画像：城市/性别/年龄/会员等级）
- orders.product_id = products.product_id（看品类/品牌/毛利）
- 三表星型：orders 为中心，users/products 为两翼；不存在 users↔products 直连

### 常用口径速查
- 销售额/GMV = SUM(orders.amount) WHERE status='已完成'
- 客单价 = AVG(orders.amount)（同上只算已完成）
- 复购用户 = 按 user_id 分组 HAVING COUNT(*)>1
- 毛利 = SUM(o.amount - p.cost_price * o.quantity)（join 后）
"""


def get_schema_doc() -> str:
    return SCHEMA_DOC


if __name__ == "__main__":
    print(SCHEMA_DOC)
