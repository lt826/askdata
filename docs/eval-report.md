# AskData 执行准确率评测报告

- 日期：2026-11-11　模型：glm-4-flash　题量：255
- 判定：生成 SQL 与标准 SQL **结果集逐行比对**（列数相等 + 行多重集相等，数值 ROUND 2 位）——确定性判定，无裁判模型

## 总指标

| 指标 | 数值 |
|---|---|
| **执行准确率**（非拒答题） | **96.1%**（223/232） |
| 拒答召回（域外/恶意题） | **100.0%**（23/23） |
| 首过率（第 1 轮即成功） | 99.1% |
| 修复循环救回 | 2 题（平均多用 1.00 轮） |
| 平均单题耗时 | 4.7s |

## 分题型准确率

| 题型 | 准确率 |
|---|---|
| group | 55/55（100%） |
| topn | 42/45（93%） |
| colloquial | 38/40（95%） |
| filter | 32/35（91%） |
| user | 22/23（96%） |
| scalar | 20/20（100%） |
| timeseries | 8/8（100%） |
| edge | 6/6（100%） |

## 失败明细（修复迭代用）

- **E083** [topn] 最近90天销量最高的前5个性别：结果不一致: 生成3列5行 vs gold2列2行; 生成SQL=SELECT u.gender, p.product_name, SUM(o.quantity) AS total_quantity
FROM order
- **E082** [topn] 2026年6月销量最高的前3个性别：结果不一致: 生成3列3行 vs gold2列2行; 生成SQL=SELECT u.gender, p.category, SUM(o.quantity) AS total_quantity
FROM orders o

- **E084** [topn] 最近90天销量最高的前10个性别：结果不一致: 生成3列10行 vs gold2列2行; 生成SQL=SELECT u.gender, p.product_name, SUM(o.quantity) AS total_quantity
FROM orde
- **E137** [filter] 全部时间服饰鞋包品类的销量：结果不一致: 生成1列1行 vs gold1列1行; 生成SQL=SELECT SUM(quantity) AS total_sales
FROM orders o
JOIN products p ON o.produc
- **E140** [filter] 全部时间门店渠道的订单量：结果不一致: 生成2列1行 vs gold1列1行; 生成SQL=SELECT channel, COUNT(*) AS order_count
FROM orders
WHERE channel = '门店'
GROU
- **E151** [filter] 全部时间西安用户的订单量：结果不一致: 生成1列1行 vs gold1列1行; 生成SQL=SELECT COUNT(*) AS order_count
FROM orders o
JOIN users u ON o.user_id = u.us
- **E166** [user] 复购用户（下单超过1次）有多少人：结果不一致: 生成1列200行 vs gold1列1行; 生成SQL=SELECT COUNT(DISTINCT user_id) AS repeat_buyers_count
FROM orders
WHERE sta
- **E187** [colloquial] 今年各会员等级的单量：结果不一致: 生成2列4行 vs gold2列4行; 生成SQL=SELECT member_level, SUM(quantity) AS 单量
FROM orders o
JOIN users u ON o.user
- **E212** [colloquial] 2026年6月各品类的单量：结果不一致: 生成2列6行 vs gold2列6行; 生成SQL=SELECT p.category, SUM(o.quantity) AS total_quantity
FROM orders o
JOIN produ
