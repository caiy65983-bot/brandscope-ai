"""Transparent opportunity hypotheses derived from observed annotation metrics."""

from typing import Dict, Optional, Union

import pandas as pd

from core.analytics import growth_by_topic, monthly_topic_rates, topic_summary


RECOMMENDATIONS = {
    "价格与性价比": "围绕消费者提及的价格顾虑设计清晰的套餐或权益表达，并用小范围文案测试验证。",
    "产品口味": "围绕被提及的口味偏好设计新品或风味内容测试，先验证具体口味反馈。",
    "提神与功能性需求": "针对明确表达的提神需求，测试不同时间段的产品沟通与使用场景内容。",
    "健康与低糖": "围绕低糖或健康相关诉求测试产品信息表达，避免未经验证的健康功效承诺。",
    "门店服务与便利性": "根据评论中明确出现的服务或便利问题，优先测试流程说明、取餐便利或服务触点改进。",
    "社交与生活方式": "围绕评论明确提到的社交或休闲情境，测试场景化内容和组合体验。",
    "品牌形象": "围绕消费者实际提到的品牌印象，测试更具体的品牌表达并观察认知变化。",
    "其他": "先查看该主题下的原始评论，人工归纳后再设计小范围验证。",
}


def build_opportunities(frame: pd.DataFrame, target_brand: Optional[str], brand_fit_score: Optional[Union[float, Dict[str, float]]] = None) -> Dict:
    summary = topic_summary(frame)
    topics = summary["需求主题"].tolist() if not summary.empty else []
    max_rate = float(summary["提及率"].max()) if not summary.empty else 0.0
    trend, trend_reason = monthly_topic_rates(frame)
    growth_scores = growth_by_topic(trend)
    brand_fit_reason = "由用户依据本品牌定位逐主题输入；未填写时该维度不参与该主题评分。"

    competitor_frame = frame
    competitors_available = bool(target_brand and "brand" in frame.columns and frame["brand"].notna().any())
    if competitors_available:
        competitor_frame = frame.loc[frame["brand"].ne(target_brand)]
        competitors_available = len(competitor_frame) >= 30
    gap_scores = {}
    competitor_profiles = {}
    gap_reason = "需提供目标品牌及至少 30 条竞品评论。"
    if competitors_available:
        comp_summary = topic_summary(competitor_frame)
        comp_max_rate = float(comp_summary["提及率"].max()) if not comp_summary.empty else 0.0
        if comp_max_rate > 0:
            for topic in topics:
                subset = competitor_frame.loc[competitor_frame["topics"].map(lambda values: topic in (values or []))]
                if len(subset) < 10:
                    continue
                current_rate = len(subset) / len(competitor_frame)
                under_coverage = 1 - min(1.0, current_rate / comp_max_rate)
                negative_proxy = float(subset["sentiment"].eq("negative").mean())
                gap_scores[topic] = 100 * (0.5 * under_coverage + 0.5 * negative_proxy)
                profile = []
                for competitor, brand_rows in competitor_frame.groupby("brand"):
                    topic_rows = brand_rows.loc[brand_rows["topics"].map(lambda values: topic in (values or []))]
                    if len(topic_rows) >= 5:
                        profile.append("{}：提及率 {:.1%}，该主题负面 {:.1%}（n={}）".format(
                            competitor, len(topic_rows) / len(brand_rows),
                            float(topic_rows["sentiment"].eq("negative").mean()), len(topic_rows),
                        ))
                competitor_profiles[topic] = "；".join(profile)
            gap_reason = "代理指标：竞品主题相对提及率较低 + 该主题负面文本占比；不等同于未满足市场需求。"

    rows = []
    for item in summary.to_dict("records"):
        topic = item["需求主题"]
        demand = (item["提及率"] / max_rate * 100) if max_rate else 0.0
        if isinstance(brand_fit_score, dict):
            topic_fit = brand_fit_score.get(topic)
        else:
            topic_fit = brand_fit_score
        components = {
            "需求热度": {"score": demand, "available": True, "reason": "主题提及率相对于本数据集最高主题标准化。"},
            "趋势增长": {"score": growth_scores.get(topic), "available": topic in growth_scores, "reason": trend_reason or "按本数据集最早与最近两个月的主题提及率变化进行相对标准化；不是市场预测。"},
            "竞品覆盖缺口": {"score": gap_scores.get(topic), "available": topic in gap_scores, "reason": gap_reason},
            "品牌适配度": {"score": float(topic_fit) if topic_fit is not None else None, "available": topic_fit is not None, "reason": brand_fit_reason},
        }
        rows.append({
            "机会名称": topic + "相关需求验证",
            "需求主题": topic,
            "综合评分": None,
            "维度": components,
            "提及评论数": item["提及评论数"],
            "样本量": len(frame),
            "提及率": item["提及率"],
            "目标品牌": target_brand,
            "证据记录数": int(frame["topics"].map(lambda values: topic in (values or [])).sum()),
            "竞品表现": competitor_profiles.get(topic, "暂无达到最小样本条件的品牌级竞品数据。"),
            "数据提示": "低样本提示（n<30）" if len(frame) < 30 else ("样本量提示（n<100）" if len(frame) < 100 else "样本量较高；仍不代表总体市场"),
            "建议": RECOMMENDATIONS.get(topic, RECOMMENDATIONS["其他"]),
        })
    return {"opportunities": rows, "trend_unavailable_reason": trend_reason, "gap_unavailable_reason": gap_reason}


def rank_opportunities(result: Dict, weights: Dict[str, float]) -> pd.DataFrame:
    rows = []
    for opportunity in result["opportunities"]:
        available = opportunity["维度"]
        active_weight = sum(float(weights.get(name, 0)) for name, cell in available.items() if cell["available"])
        if active_weight > 0:
            score = sum(float(weights.get(name, 0)) * float(cell["score"]) for name, cell in available.items() if cell["available"]) / active_weight
        else:
            score = None
        opportunity["综合评分"] = round(score, 1) if score is not None else None
        row = {key: opportunity[key] for key in ("机会名称", "需求主题", "综合评分", "提及评论数", "样本量", "提及率", "竞品表现", "数据提示", "建议")}
        for name, cell in available.items():
            row[name] = round(float(cell["score"]), 1) if cell["available"] else None
        rows.append(row)
    return pd.DataFrame(rows).sort_values("综合评分", ascending=False, na_position="last").reset_index(drop=True)
