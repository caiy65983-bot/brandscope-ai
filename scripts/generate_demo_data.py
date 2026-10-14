"""Generate the reproducible 3,000-row simulated coffee feedback dataset."""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261013
ROWS = 3000
BRANDS = ["瑞幸咖啡", "库迪咖啡", "星巴克"]
PLATFORMS = ["小红书", "微博", "大众点评", "抖音"]
TEMPLATES = [
    ("价格与性价比", "{brand}这杯价格挺友好，日常喝不太有负担。", "positive"),
    ("价格与性价比", "{brand}最近优惠少了，算下来不如之前划算。", "negative"),
    ("价格与性价比", "看到{brand}有活动就买了，价格和口味都还可以。", "mixed"),
    ("口味和产品体验", "{brand}的拿铁奶香明显，咖啡味也够，今天这杯不错。", "positive"),
    ("口味和产品体验", "{brand}这次做得有点淡，冰块化了以后更像水。", "negative"),
    ("口味和产品体验", "第一次试{brand}的新品，香气不错但甜度偏高。", "mixed"),
    ("提神与功能性", "赶方案前买了{brand}，喝完精神一些，能继续工作。", "positive"),
    ("提神与功能性", "晚上喝{brand}之后有点睡不着，以后要早点喝。", "negative"),
    ("健康与低糖", "希望{brand}能把低糖选项做得更清楚，控糖时好选择。", "neutral"),
    ("健康与低糖", "点了{brand}的少糖版本，味道还在，甜度舒服多了。", "positive"),
    ("服务与便利性", "楼下就有{brand}，手机下单到店取很方便。", "positive"),
    ("服务与便利性", "{brand}高峰期等了很久，取餐提示也不太清楚。", "negative"),
    ("社交与生活方式", "周末和朋友在{brand}坐了一会儿，聊天氛围挺轻松。", "positive"),
    ("社交与生活方式", "在{brand}约同事讨论事情，位置好找也方便碰面。", "positive"),
    ("品牌形象", "一直觉得{brand}的包装和门店设计很有辨识度。", "positive"),
    ("品牌形象", "{brand}的宣传挺多，但我更想知道咖啡豆和配料信息。", "mixed"),
]

def main():
    rng = random.Random(SEED)
    today = date(2026, 10, 11)
    output = Path(__file__).resolve().parents[1] / "data" / "demo" / "coffee_feedback_demo.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    headers = ["record_id", "brand", "platform", "published_at", "content", "content_type", "likes", "source_id", "source_url", "demo_topic", "demo_sentiment"]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for index in range(1, ROWS + 1):
            brand = rng.choice(BRANDS)
            topic, template, sentiment = rng.choice(TEMPLATES)
            published = today - timedelta(days=rng.randrange(365))
            writer.writerow({"record_id": f"R{index:04d}", "brand": brand,
                "platform": rng.choice(PLATFORMS), "published_at": published.isoformat(),
                "content": template.format(brand=brand), "content_type": "模拟评论",
                "likes": rng.randint(0, 280), "source_id": f"SIM-{index:04d}",
                "source_url": "", "demo_topic": topic, "demo_sentiment": sentiment})
    print(f"Generated {ROWS} simulated records: {output}")

if __name__ == "__main__":
    main()
