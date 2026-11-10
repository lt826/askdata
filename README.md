# AskData · 问数

> 中文问数据，自动出 SQL、自动修错、自动出图 —— ChatBI 数据分析 Agent，让业务人员零 SQL 做分析

**与 [FitPilot](https://github.com/lt826/fit-pilot)（RAG 知识问答）互补**：FitPilot 解决"知识问题"（检索 + 生成），AskData 解决"计算问题"（代码生成 + 执行验证）。

## 六层架构

```
① 意图与上下文层    多轮指代消解（"那上个月呢？"）
② Schema 理解层     DDL + 每列业务白话解释 + 枚举值注入 —— SQL 准确率的命门
③ SQL 生成层        只读 SELECT 约束 + few-shot
④ 沙箱执行+修复循环  报错分类(语法/列名/逻辑)→错误+表结构回喂重生成→N轮熔断 ★项目灵魂
⑤ 呈现层            模型判断表格/图型 → matplotlib 代码 → 沙箱渲染
⑥ 安全护栏          SQL 白名单拦 DELETE/UPDATE/DROP、LIMIT 强制、超时熔断
横切：LangFuse 观测（修复轮数=核心质量指标）+ 执行准确率评测
```

## 评测：执行准确率（Execution Accuracy）

生成 SQL 与标准 SQL 的**结果集逐行比对**——确定性评测，无需裁判模型。
比 LLM-as-judge 更硬：对就是对，错就是错。

## 技术栈

DuckDB（单文件列存）· LangGraph + LangChain · FastAPI + SSE · Vue3 + ECharts · glm-4-flash

## 开发步骤

- [x] 第 0 步 · 项目骨架（uv + git + 配置）
- [x] 第 1 步 · 数据底座：合成电商数据集 → DuckDB 建库 → Schema 白话层（498商品/2万用户/10万订单）
- [x] 第 2 步 · NL→SQL→执行 单链路跑通（验收 3/4：歧义列名失败案例正好留给第 3 步）
- [x] 第 3 步 · 沙箱修复循环（灵魂）——错误分类回喂重生成,实测歧义列名1轮修复;口径速查补 COUNT(DISTINCT)/TopN聚合规范后语义跑偏消除
- [ ] 第 4 步 · 呈现层（表格/图表）
- [ ] 第 5 步 · API + 前端
- [ ] 第 6 步 · 执行准确率评测（30~50 题）
- [ ] 第 7 步 · 观测 + 部署
- [ ] 第 8 步 · 简历 + 文档

## 快速开始（待第 2 步后补全）

```bash
uv sync
cp .env.example .env   # 填 ZHIPU_API_KEY
uv run scripts/gen_dataset.py   # 生成合成数据集
uv run scripts/build_db.py      # 建 DuckDB 库
```
