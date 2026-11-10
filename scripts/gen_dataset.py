"""合成电商数据集生成：固定随机种子保证可复现。

为什么用合成数据而不是公开数据集：
- Schema/枚举值完全可控 —— Schema 白话层（SQL 准确率的命门）可以写得严丝合缝
- 数据带"业务形状"（周末高峰、双11/618尖峰、会员消费分层、品类销量差异），
  分析出来的结论有故事可讲，演示效果好
- 无版权/下载问题，评测集的"标准答案"可以离线算好

三张表：products(500) / users(20000) / orders(100000，近365天)
输出：data/datasets/*.csv（gitignored，duckdb 文件才是运行时唯一真身）
"""

import numpy as np
import pandas as pd
from pathlib import Path

SEED = 42
N_PRODUCTS = 500
N_USERS = 20_000
N_ORDERS = 100_000
OUT = Path(__file__).resolve().parents[1] / "data" / "datasets"

rng = np.random.default_rng(SEED)

# 品类画像：子类 × 价位区间 × 销量权重（数码贵但低频，食品便宜但高频）
CATEGORIES = {
    "数码家电": {"subs": ["手机", "笔记本", "平板", "耳机", "智能手表", "相机"],
               "price": (399, 9999), "weight": 12,
               "brands": ["星辰", "极客邦", "声浪", "光影"]},
    "服饰鞋包": {"subs": ["T恤", "卫衣", "牛仔裤", "运动鞋", "双肩包", "羽绒服"],
               "price": (79, 1299), "weight": 26,
               "brands": ["素白", "山野间", "步履", "织造社"]},
    "美妆个护": {"subs": ["面霜", "精华", "口红", "防晒", "洗发水", "面膜"],
               "price": (39, 699), "weight": 22,
               "brands": ["花知", "澄肌", "本草新语", "晨露"]},
    "食品饮料": {"subs": ["坚果", "咖啡豆", "零食大礼包", "牛排", "牛奶", "茶叶"],
               "price": (19, 399), "weight": 20,
               "brands": ["山货铺子", "焙研所", "牧场直供", "叶语"]},
    "家居日用": {"subs": ["收纳箱", "台灯", "四件套", "保温杯", "香薰", "抱枕"],
               "price": (29, 899), "weight": 12,
               "brands": ["栖居", "暖房", "木言", "器物所"]},
    "运动户外": {"subs": ["瑜伽垫", "哑铃", "跑鞋", "帐篷", "骑行头盔", "跳绳"],
               "price": (49, 1999), "weight": 8,
               "brands": ["力形", "野径", "衡", "风速"]},
}
CITIES = ["上海", "北京", "广州", "深圳", "杭州", "成都", "武汉", "南京", "重庆", "西安"]
CITY_WEIGHTS = [15, 15, 10, 10, 9, 9, 8, 8, 8, 8]
CHANNELS = ["App", "小程序", "网页", "门店"]
CHANNEL_W = [0.45, 0.30, 0.15, 0.10]
STATUS = ["已完成", "已取消", "退款中", "已退款"]
STATUS_W = [0.92, 0.05, 0.02, 0.01]


def gen_products() -> pd.DataFrame:
    rows = []
    pid = 1
    for cat, cfg in CATEGORIES.items():
        # 按品类均分500个商品位
        n = round(N_PRODUCTS * len(cfg["subs"]) / sum(len(c["subs"]) for c in CATEGORIES.values()))
        for _ in range(n):
            sub = rng.choice(cfg["subs"])
            brand = rng.choice(cfg["brands"])
            lo, hi = cfg["price"]
            price = round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))), -1)  # 对数均匀+取整十
            rows.append({
                "product_id": f"P{pid:04d}",
                "product_name": f"{brand}{sub}",
                "category": cat, "subcategory": sub,
                "brand": brand,
                "unit_price": price,
                "cost_price": round(price * rng.uniform(0.5, 0.75), 2),
            })
            pid += 1
    return pd.DataFrame(rows)


def gen_users() -> pd.DataFrame:
    uid = np.arange(1, N_USERS + 1)
    gender = rng.choice(["男", "女"], N_USERS, p=[0.46, 0.54])
    age = np.clip(rng.normal(32, 10, N_USERS).round(), 16, 70).astype(int)
    city = rng.choice(CITIES, N_USERS, p=np.array(CITY_WEIGHTS) / 100)
    reg_days_ago = rng.integers(1, 1100, N_USERS)  # 注册于近3年内
    register_date = pd.Timestamp("2026-11-10") - pd.to_timedelta(reg_days_ago, unit="D")
    # 会员等级按消费能力分层（金卡钻石稀少）
    level = rng.choice(["普通", "银卡", "金卡", "钻石"], N_USERS, p=[0.55, 0.30, 0.12, 0.03])
    return pd.DataFrame({
        "user_id": [f"U{i:05d}" for i in uid],
        "gender": gender, "age": age, "city": city,
        "register_date": register_date.strftime("%Y-%m-%d"),
        "member_level": level,
    })


def gen_orders(products: pd.DataFrame, users: pd.DataFrame) -> pd.DataFrame:
    end = pd.Timestamp("2026-11-10")
    dates = end - pd.to_timedelta(rng.integers(0, 365, N_ORDERS), unit="D")

    # 业务形状①：周末销量高 ②：双11/618/年货节尖峰
    weights = np.where(dates.day_of_week >= 5, 1.4, 1.0)
    promo = dates.strftime("%m-%d").isin(["11-11", "06-18", "01-28", "12-12"])
    weights = np.where(promo, 3.5, weights)
    weights /= weights.sum()
    # 有放回重抽按业务权重分布；choice 返回 ndarray，转回 DatetimeIndex 保住 pandas 方法
    dates = pd.to_datetime(rng.choice(dates.values, N_ORDERS, p=weights))

    # 业务形状③：二八定律——20%活跃用户贡献60%订单（zipf偏斜）
    active = rng.choice(N_USERS, size=N_USERS // 5, replace=False)
    pool = np.concatenate([np.repeat(active, 3), np.arange(N_USERS)])
    buyer_idx = rng.choice(pool, N_ORDERS)

    # 业务形状④：品类销量按 weight 偏置（高频低价品类多）
    cat_names = list(CATEGORIES)
    cat_p = np.array([CATEGORIES[c]["weight"] for c in cat_names], dtype=float)
    cat_p /= cat_p.sum()
    prod_cat = rng.choice(cat_names, N_ORDERS, p=cat_p)
    prod_idx = [rng.choice(products.index[products.category == c]) for c in prod_cat]

    qty = rng.choice([1, 2, 3, 4, 5], N_ORDERS, p=[0.62, 0.22, 0.09, 0.04, 0.03])
    price = products.iloc[prod_idx]["unit_price"].values
    discount = rng.uniform(0.85, 1.0, N_ORDERS).round(3)  # 折扣：会员日/大促更低
    discount = np.where(promo_dates(dates), rng.uniform(0.7, 0.9, N_ORDERS).round(3), discount)
    amount = (qty * price * discount).round(2)

    df = pd.DataFrame({
        "order_id": [f"O{i:06d}" for i in range(1, N_ORDERS + 1)],
        "user_id": users.iloc[buyer_idx]["user_id"].values,
        "product_id": products.iloc[prod_idx]["product_id"].values,
        "quantity": qty,
        "unit_price": price,            # 成交单价（含折扣后）
        "amount": amount,               # 订单金额 = 数量×成交单价
        "order_date": dates.strftime("%Y-%m-%d"),
        "channel": rng.choice(CHANNELS, N_ORDERS, p=CHANNEL_W),
        "status": rng.choice(STATUS, N_ORDERS, p=STATUS_W),
    })
    return df


def promo_dates(dates) -> np.ndarray:
    return dates.strftime("%m-%d").isin(["11-11", "06-18", "01-28", "12-12"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    products, users = gen_products(), gen_users()
    orders = gen_orders(products, users)
    for name, df in [("products", products), ("users", users), ("orders", orders)]:
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"{name}: {len(df)} 行 → {OUT / f'{name}.csv'}")
    done = orders[orders.status == "已完成"]
    print(f"验收: GMV(已完成订单) = {done.amount.sum():,.0f} 元, "
          f"客单价 = {done.amount.mean():,.1f} 元, 日期跨度 "
          f"{orders.order_date.min()} ~ {orders.order_date.max()}")


if __name__ == "__main__":
    main()
