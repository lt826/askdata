# AskData 执行准确率评测报告

- 日期：2026-11-10　模型：glm-4-flash　题量：255
- 判定：生成 SQL 与标准 SQL **结果集逐行比对**（列数相等 + 行多重集相等，数值 ROUND 2 位）——确定性判定，无裁判模型

## 总指标

| 指标 | 数值 |
|---|---|
| **执行准确率**（非拒答题） | **92.2%**（214/232） |
| 拒答召回（域外/恶意题） | **100.0%**（23/23） |
| 首过率（第 1 轮即成功） | 97.4% |
| 修复循环救回 | 5 题（平均多用 1.00 轮） |
| 平均单题耗时 | 4.1s |

## 分题型准确率

| 题型 | 准确率 |
|---|---|
| group | 55/55（100%） |
| topn | 38/45（84%） |
| colloquial | 35/40（88%） |
| filter | 32/35（91%） |
| user | 22/23（96%） |
| scalar | 18/20（90%） |
| timeseries | 8/8（100%） |
| edge | 6/6（100%） |

## 失败明细（修复迭代用）

- **E008** [scalar] 今年的总订单量是多少：结果不一致: 生成1列1行 vs gold1列1行; 生成SQL=SELECT COUNT(*) AS total_order_count
FROM orders
WHERE status = '已完成'
  AND o
- **E012** [scalar] 今年的总销量是多少：结果不一致: 生成1列1行 vs gold1列1行; 生成SQL=SELECT SUM(quantity) AS total_quantity_sold
FROM orders
WHERE status = '已完成'

- **E084** [topn] 最近90天销量最高的前10个性别：结果不一致: 生成3列10行 vs gold2列2行; 生成SQL=SELECT u.gender, p.product_name, SUM(o.quantity) AS total_quantity
FROM orde
- **E083** [topn] 最近90天销量最高的前5个性别：结果不一致: 生成3列5行 vs gold2列2行; 生成SQL=SELECT u.gender, p.product_name, SUM(o.quantity) AS total_quantity
FROM order
- **E082** [topn] 2026年6月销量最高的前3个性别：结果不一致: 生成3列3行 vs gold2列2行; 生成SQL=SELECT u.gender, p.category, SUM(o.quantity) AS total_quantity
FROM orders o

- **E094** [topn] 今年销量最高的前3个城市：结果不一致: 生成2列3行 vs gold2列3行; 生成SQL=SELECT u.city,
       SUM(o.quantity) AS total_quantity
FROM orders o
JOIN us
- **E106** [topn] 今年销量最高的前10个品类：结果不一致: 生成2列6行 vs gold2列6行; 生成SQL=SELECT p.category,
       SUM(o.quantity) AS total_quantity
FROM orders o
JOI
- **E103** [topn] 最近90天订单量最高的前5个城市：结果不一致: 生成2列5行 vs gold2列5行; 生成SQL=SELECT u.city, COUNT(*) AS order_count
FROM orders o
JOIN users u ON o.user_i
- **E096** [topn] 最近90天销量最高的前5个城市：结果不一致: 生成2列5行 vs gold2列5行; 生成SQL=SELECT u.city,
       SUM(o.quantity) AS total_quantity
FROM orders o
JOIN us
- **E127** [filter] 今年服饰鞋包品类的订单量：结果不一致: 生成1列1行 vs gold1列1行; 生成SQL=SELECT COUNT(*) AS order_count
FROM orders o
JOIN products p ON o.product_id 
- **E138** [filter] 今年南京用户的订单量：结果不一致: 生成1列1行 vs gold1列1行; 生成SQL=SELECT COUNT(*) AS order_count
FROM orders o
JOIN users u ON o.user_id = u.us
- **E166** [user] 复购用户（下单超过1次）有多少人：结果不一致: 生成1列200行 vs gold1列1行; 生成SQL=SELECT COUNT(DISTINCT user_id) AS unique_buyers
FROM orders
WHERE status = 
- **E153** [filter] 今年家居日用品类的订单量：结果不一致: 生成1列1行 vs gold1列1行; 生成SQL=SELECT COUNT(*) AS order_count
FROM orders o
JOIN products p ON o.product_id 
- **E212** [colloquial] 2026年6月各品类的单量：结果不一致: 生成2列6行 vs gold2列6行; 生成SQL=SELECT p.category, SUM(o.quantity) AS total_quantity
FROM orders o
JOIN produ
- **E215** [colloquial] 最近90天单量最高的前5个城市：结果不一致: 生成2列5行 vs gold2列5行; 生成SQL=SELECT u.city, COUNT(*) AS order_count
FROM orders o
JOIN users u ON o.user_i
- **E207** [colloquial] 最近90天客单价Top的前10个品类：结果不一致: 生成1列6行 vs gold2列6行; 生成SQL=WITH CompletedOrders AS (
    SELECT p.category,
           AVG(o.amount) AS 
- **E225** [colloquial] 最近90天销量最多的前5个城市：结果不一致: 生成2列5行 vs gold2列5行; 生成SQL=SELECT u.city, SUM(o.quantity) AS total_quantity
FROM orders o
JOIN users u O
- **E218** [colloquial] 今年的总单量是多少：结果不一致: 生成1列1行 vs gold1列1行; 生成SQL=SELECT COUNT(*) AS total_order_count
FROM orders
WHERE status = '已完成'
  AND o
