"""Evidence-linked report assembly and optional constrained AI narrative."""

import html
import json
import math
import re
from datetime import datetime
from typing import Dict, Optional

import pandas as pd
from pydantic import ValidationError

from core.analytics import brand_topic_matrix, sentiment_summary, topic_sentiment, topic_summary
from core.opportunity_engine import RECOMMENDATIONS, build_opportunities, rank_opportunities
from core.styles import REPORT_CSS
from models.schemas import StrategyNarrative
from services.llm_client import LLMConfig, OpenAICompatibleClient


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _top_values(series: pd.Series, limit: int = 3) -> list:
    return series.explode().dropna().value_counts().head(limit).rename_axis("label").reset_index(name="count").to_dict("records")


def build_report_data(
    frame: pd.DataFrame,
    dataset_name: str,
    is_demo: bool,
    target_brand: Optional[str] = None,
    fit_scores: Optional[Dict[str, float]] = None,
    weights: Optional[Dict[str, float]] = None,
    strategy_context: str = "",
) -> Dict:
    """All quantities and rankings in this report come from deterministic Python calculations."""
    topic_stats = topic_summary(frame)
    emotion_stats = sentiment_summary(frame)
    pain_points = _top_values(frame["pain_points"], 5)
    motivations = _top_values(frame["purchase_motivation"], 5)
    scenarios = _top_values(frame["scenarios"], 5)
    brand_counts = frame["brand"].dropna().value_counts() if "brand" in frame else pd.Series(dtype=int)
    platform_counts = frame["platform"].dropna().value_counts() if "platform" in frame else pd.Series(dtype=int)
    dates = pd.to_datetime(frame.get("published_at", pd.Series(dtype=object)), errors="coerce").dropna()
    date_range = "{} 至 {}".format(dates.min().date(), dates.max().date()) if not dates.empty else "未提供有效日期"
    source_label = "模拟演示数据" if is_demo else "用户导入数据"
    top_topic = topic_stats.iloc[0] if not topic_stats.empty else None
    top_sentiment = emotion_stats.sort_values("评论数", ascending=False).iloc[0] if not emotion_stats.empty else None
    if top_topic is not None:
        deterministic_summary = "当前样本共 {:,} 条评论；提及最多的主题是“{}”，涉及 {:,} 条评论（{:.1%}）。".format(
            len(frame), top_topic["需求主题"], int(top_topic["提及评论数"]), float(top_topic["提及率"])
        )
    else:
        deterministic_summary = "当前样本共 {:,} 条评论，尚无可用需求主题标签。".format(len(frame))
    if top_sentiment is not None:
        deterministic_summary += " 文本情绪中占比最高的是 {}（{:.1%}）。".format(top_sentiment["情绪"], float(top_sentiment["占比"]))
    deterministic_summary += "以上仅描述当前导入样本，不外推到整体市场。"

    weights = weights or {"需求热度": 35.0, "趋势增长": 25.0, "竞品覆盖缺口": 25.0, "品牌适配度": 15.0}
    opportunity_result = build_opportunities(frame, target_brand, fit_scores)
    opportunity_table = rank_opportunities(opportunity_result, weights)
    opportunity_rows = opportunity_table.head(5).to_dict("records")

    brand_matrix = brand_topic_matrix(frame)
    brand_differences = []
    if not brand_matrix.empty:
        for topic, group in brand_matrix.groupby("需求主题"):
            if group["品牌"].nunique() < 2:
                continue
            sorted_group = group.sort_values("提及率", ascending=False)
            high, low = sorted_group.iloc[0], sorted_group.iloc[-1]
            if high["品牌"] == low["品牌"] or float(high["提及率"]) <= float(low["提及率"]):
                continue
            brand_differences.append({
                "topic": topic,
                "text": "{} 在“{}”主题的评论提及率较高（{:.1%}，n={}）；{} 为 {:.1%}（n={}）。".format(
                    high["品牌"], topic, high["提及率"], high["样本量"], low["品牌"], low["提及率"], low["样本量"]
                ),
            })
    brand_differences = brand_differences[:5]
    per_topic_emotion = topic_sentiment(frame)
    recommendation_rows = []
    for item in opportunity_rows[:3]:
        topic = item["需求主题"]
        topic_frame = frame.loc[frame["topics"].map(lambda values: topic in (values or []))]
        selected = topic_frame.head(3)
        evidence = []
        for row in selected.itertuples():
            evidence.append({
                "record_id": str(row.record_id),
                "brand": str(getattr(row, "brand", "") or ""),
                "platform": str(getattr(row, "platform", "") or ""),
                "content": str(row.content),
                "sentiment": str(row.sentiment),
            })
        topic_scenarios = _top_values(topic_frame["scenarios"], 1)
        topic_motivations = _top_values(topic_frame["purchase_motivation"], 1)
        scenario = topic_scenarios[0]["label"] if topic_scenarios else ""
        motivation = topic_motivations[0]["label"] if topic_motivations else ""
        topic_row = topic_stats.loc[topic_stats["需求主题"].eq(topic)]
        mention_rate = float(topic_row.iloc[0]["提及率"]) if not topic_row.empty else 0.0
        mention_count = int(topic_row.iloc[0]["提及评论数"]) if not topic_row.empty else 0
        negative_row = per_topic_emotion.loc[per_topic_emotion["需求主题"].eq(topic)]
        negative_rate = float(negative_row.iloc[0]["负面比例"]) if not negative_row.empty else None
        recommendation_rows.append({
            "topic": topic,
            "opportunity_score": item.get("综合评分"),
            "mention_count": mention_count,
            "mention_rate": mention_rate,
            "negative_rate": negative_rate,
            "competitor_performance": item.get("竞品表现", ""),
            "dimension_scores": {name: item.get(name) for name in ("需求热度", "趋势增长", "竞品覆盖缺口", "品牌适配度")},
            "data_note": item.get("数据提示", ""),
            "recommendation": RECOMMENDATIONS.get(topic, RECOMMENDATIONS["其他"]),
            "scenario": scenario,
            "motivation": motivation,
            "message_direction": "围绕“{}”主题表达消费者真实提及的需求；传播承诺应与产品实际能力一致。".format(topic),
            "content_concept": "制作一组以“{}”为核心的评论回应或场景短内容，先验证内容反应再决定是否扩大。".format(topic),
            "verification_metrics": ["内容点击率", "产品详情页访问率", "试购转化率", "复访/复购率"],
            "evidence_ids": [x["record_id"] for x in evidence],
            "evidence": evidence,
        })

    date_limitations = "日期样本仅用于描述评论样本中的变化，不外推到整体市场。" if not dates.empty else "缺少有效日期，不能分析时间趋势。"
    limitations = [
        "本报告样本来自 {}；结论描述已导入评论，不能视为全体消费者或市场规模。".format(source_label),
        "平台来源、抓取/抽样方式、用户自选择表达和各品牌样本量可能造成比较偏差。",
        date_limitations,
        "情绪标签代表文本表达倾向，不等于满意度或购买行为。",
        "竞品覆盖缺口是主题讨论与负面文本的代理指标，不代表真实未满足需求。",
        "机会评分只用于辅助排序，不代表增长概率、销售额或商业收益。",
    ]
    report = {
        "dataset_name": dataset_name,
        "source_label": source_label,
        "record_count": int(len(frame)),
        "brand_counts": [{"brand": str(key), "count": int(value)} for key, value in brand_counts.items()],
        "platform_counts": [{"platform": str(key), "count": int(value)} for key, value in platform_counts.items()],
        "date_range": date_range,
        "deterministic_summary": deterministic_summary,
        "topic_stats": topic_stats.to_dict("records"),
        "sentiment_stats": emotion_stats.to_dict("records"),
        "topic_sentiment": per_topic_emotion.to_dict("records"),
        "pain_points": pain_points,
        "motivations": motivations,
        "scenarios": scenarios,
        "brand_differences": brand_differences,
        "opportunities": opportunity_rows,
        "recommendations": recommendation_rows,
        "limitations": limitations,
        "weights": weights,
        "target_brand": target_brand,
        "strategy_context": strategy_context,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ai_narrative": None,
    }
    return _json_safe(report)


def generate_ai_narrative(report: Dict, config: LLMConfig) -> StrategyNarrative:
    """Ask the model for qualitative synthesis only; never let it calculate report metrics."""
    if not config.configured:
        raise ValueError("没有配置模型 API")
    evidence_ids = {entry["record_id"] for rec in report["recommendations"] for entry in rec["evidence"]}
    summary_context = {
        "analysis_project": report["dataset_name"],
        "user_strategy_context": report["strategy_context"],
        "computed_topics": report["topic_stats"][:8],
        "computed_sentiment": report["sentiment_stats"],
        "computed_brand_differences": report["brand_differences"],
        "computed_opportunities": report["opportunities"][:5],
        "verified_evidence": [evidence for rec in report["recommendations"] for evidence in rec["evidence"]],
        "allowed_evidence_ids": sorted(evidence_ids),
    }
    system = (
        "你是谨慎的品牌策略分析助手。只解释输入中已计算的发现。不要计算或创造比例、人数、增长、市场规模、投放数据、收益或事实。"
        "只输出 JSON：{\"executive_summary\":\"...\",\"recommendations\":[{\"topic\":\"...\",\"recommendation\":\"...\",\"scenario\":\"...\",\"message_direction\":\"...\",\"content_concept\":\"...\",\"verification_metrics\":[\"...\"],\"evidence_ids\":[\"原始 record_id\"]}]}。"
        "推荐只能从输入机会主题中选；每条建议必须引用 allowed_evidence_ids 中的一个或多个编号。不得在 narrative 字段写数字，数值由程序独立显示。验证指标仅是建议测量项，不得声称已有结果。"
    )
    client = OpenAICompatibleClient(config)
    error = ""
    for attempt in range(3):
        prompt = json.dumps(summary_context, ensure_ascii=False)
        if error:
            prompt += "\n上次结果未通过校验，请重新输出并修复：" + error
        response = client.complete_json(system, prompt)
        try:
            narrative = StrategyNarrative.model_validate(response["data"])
            allowed_topics = {item["需求主题"] for item in report["opportunities"]}
            for recommendation in narrative.recommendations:
                if recommendation.topic not in allowed_topics:
                    raise ValueError("建议引用了未计算的主题")
                if not set(recommendation.evidence_ids).issubset(evidence_ids):
                    raise ValueError("建议引用了本次报告不存在的证据编号")
            joined_text = narrative.executive_summary + " ".join(
                rec.recommendation + rec.scenario + rec.message_direction + rec.content_concept + " ".join(rec.verification_metrics)
                for rec in narrative.recommendations
            )
            if re.search(r"\d|[零一二三四五六七八九十百千万亿]", joined_text):
                raise ValueError("定性解读中包含数字或数量描述，应由报告的计算指标区展示")
            return narrative
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            error = str(exc)[:300]
    raise ValueError("AI 解读连续未通过证据或格式校验：" + error)


def render_report_html(report: Dict) -> str:
    """Create a standalone escaped HTML report; all numeric values come from report data."""
    esc = lambda value: html.escape(str(value if value is not None else ""))
    topic_rows = "".join("<tr><td>{}</td><td>{:,}</td><td>{:.1%}</td></tr>".format(esc(x["需求主题"]), int(x["提及评论数"]), float(x["提及率"])) for x in report["topic_stats"])
    sentiment_rows = "".join("<tr><td>{}</td><td>{:,}</td><td>{:.1%}</td></tr>".format(esc(x["情绪"]), int(x["评论数"]), float(x["占比"])) for x in report["sentiment_stats"])
    def score_cell(value):
        return "不可用" if value is None or pd.isna(value) else "{:.1f}".format(float(value))

    opportunity_rows = "".join("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{:,}</td><td>{:.1%}</td><td>{}</td></tr>".format(
        esc(x["需求主题"]), score_cell(x.get("综合评分")), score_cell(x.get("需求热度")),
        score_cell(x.get("趋势增长")), score_cell(x.get("竞品覆盖缺口")), score_cell(x.get("品牌适配度")),
        int(x["提及评论数"]), float(x["提及率"]), esc(x.get("建议", ""))
    ) for x in report["opportunities"])
    diff_list = "".join("<li>{}</li>".format(esc(x["text"])) for x in report["brand_differences"]) or "<li>有效品牌样本不足，未生成品牌差异结论。</li>"
    recs = []
    for item in report["recommendations"]:
        evidence_html = "".join("<blockquote><b>{}</b> · {} · {}<br>{}</blockquote>".format(esc(e["record_id"]), esc(e["brand"]), esc(e["platform"]), esc(e["content"])) for e in item["evidence"])
        recs.append("<article><h3>{}</h3><p><b>评分依据：</b>{:,} 条评论，提及率 {:.1%}；机会分 {}</p><p><b>目标场景：</b>{}；消费动机：{}</p><p><b>对应竞品：</b>{}</p><p><b>传播方向：</b>{}</p><p><b>内容创意：</b>{}</p><p><b>建议策略：</b>{}</p><p><b>验证指标（建议）：</b>{}</p><p><b>证据编号：</b>{}</p><p><b>数据提示：</b>{}</p>{}</article>".format(
            esc(item["topic"]), int(item["mention_count"]), float(item["mention_rate"]),
            "不可用" if item.get("opportunity_score") is None else esc(item["opportunity_score"]),
            esc(item.get("scenario") or "文本未明确场景"), esc(item.get("motivation") or "未明确动机"),
            esc(item.get("competitor_performance", "")), esc(item["message_direction"]), esc(item["content_concept"]), esc(item["recommendation"]),
            esc("、".join(item["verification_metrics"])), esc("、".join(item["evidence_ids"])), esc(item.get("data_note", "")), evidence_html,
        ))
    ai_html = ""
    if report.get("ai_narrative"):
        ai = report["ai_narrative"]
        advice_html = "".join("<article><h3>{}</h3><p>{}</p><p><b>场景：</b>{}</p><p><b>传播方向：</b>{}</p><p><b>内容概念：</b>{}</p><p><b>验证指标建议：</b>{}</p><p><b>证据编号：</b>{}</p></article>".format(
            esc(item["topic"]), esc(item["recommendation"]), esc(item["scenario"]), esc(item["message_direction"]),
            esc(item["content_concept"]), esc("、".join(item["verification_metrics"])), esc("、".join(item["evidence_ids"])),
        ) for item in ai["recommendations"])
        ai_html = "<section><h2>AI 定性解读</h2><p>{}</p>{}</section>".format(esc(ai["executive_summary"]), advice_html)
    context = "<p><b>用户补充的策略背景：</b>{}</p>".format(esc(report["strategy_context"])) if report.get("strategy_context") else ""
    weight_text = "；".join("{} {}%".format(esc(key), float(value)) for key, value in report["weights"].items())
    limitations = "".join("<li>{}</li>".format(esc(item)) for item in report["limitations"])
    motivations_html = "、".join("{}（{} 条）".format(esc(x["label"]), int(x["count"])) for x in report["motivations"]) or "未明确标注"
    scenarios_html = "、".join("{}（{} 条）".format(esc(x["label"]), int(x["count"])) for x in report["scenarios"]) or "未明确标注"
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · BrandScope AI</title>
<style>{styles}</style></head><body><main>
<header><h1>BrandScope AI · 策略分析报告</h1><p>{dataset} · {source} · 生成时间 {date}</p><p class="tag">{source_note}</p></header>
<section><h2>项目概况</h2><p>分析记录：{count:,} 条；品牌：{brands}; 平台：{platforms}; 日期范围：{date_range}</p>{context}<small>统计口径：主题提及率 = 至少包含该主题的评论数 ÷ 当前样本评论数。评论允许多主题。</small></section>
<section><h2>规则化数据摘要</h2><p>{summary}</p><small>此摘要由已计算指标填充，不调用 AI。</small></section>
<section><h2>消费者核心需求</h2><div class="table-scroll"><table><thead><tr><th>主题</th><th>评论数</th><th>提及率</th></tr></thead><tbody>{topics}</tbody></table></div></section>
<section><h2>消费动机与明确场景</h2><p><b>动机：</b>{motivations}</p><p><b>场景：</b>{scenarios}</p><small>只有评论明确提及时才展示对应场景；没有证据的场景不会推断。</small></section>
<section><h2>消费者情绪与痛点</h2><div class="table-scroll"><table><thead><tr><th>文本情绪</th><th>评论数</th><th>占比</th></tr></thead><tbody>{sentiments}</tbody></table></div><h3>痛点主题</h3><ul>{pains}</ul><small>情绪标签反映文本表达，不等同于真实满意度。</small></section>
<section><h2>竞品品牌差异</h2><ul>{differences}</ul></section>
<section><h2>潜在营销机会排序</h2><p><b>权重输入：</b>{weights}</p><div class="table-scroll"><table class="opportunity-table"><thead><tr><th>主题</th><th>机会分</th><th>需求热度</th><th>趋势增长</th><th>竞品缺口</th><th>品牌适配</th><th>评论数</th><th>提及率</th><th>验证方向</th></tr></thead><tbody>{opportunities}</tbody></table></div><small>机会分为当前筛选样本中的辅助优先级，仅在可用维度中按权重归一化；不是增长概率或商业收益预测。不可用表示数据不足或尚无用户输入。</small></section>
{ai}<section><h2>推荐优先验证的策略</h2>{recommendations}</section>
<section><h2>关键指标与验证方法</h2><p>建议选取与策略目标对应的内容点击率、详情页访问率、试购转化率和复访/复购率。通过小规模对照实验记录基线、测试版本、周期和样本来源；这些指标尚未在本数据中测量。</p></section>
<section><h2>数据局限与后续研究</h2><ul>{limitations}</ul></section>
<footer><small>BrandScope AI · 可追溯消费者文本的营销分析 · {date}</small></footer></main></body></html>""".format(
        styles=REPORT_CSS, title=esc(report["dataset_name"]), dataset=esc(report["dataset_name"]), source=esc(report["source_label"]), date=esc(report["generated_at"]),
        source_note="模拟演示数据 · 不代表真实市场研究" if report["source_label"] == "模拟演示数据" else "用户导入数据",
        count=int(report["record_count"]), brands=esc("、".join(x["brand"] for x in report["brand_counts"]) or "未提供"),
        platforms=esc("、".join(x["platform"] for x in report["platform_counts"]) or "未提供"), date_range=esc(report["date_range"]), context=context,
        summary=esc(report["deterministic_summary"]), weights=weight_text,
        topics=topic_rows or "<tr><td colspan=3>暂无主题标签</td></tr>", sentiments=sentiment_rows,
        motivations=motivations_html, scenarios=scenarios_html,
        pains="".join("<li>{}（{:,} 条）</li>".format(esc(x["label"]), int(x["count"])) for x in report["pain_points"]) or "<li>未标注到明确痛点</li>",
        differences=diff_list, opportunities=opportunity_rows or "<tr><td colspan=5>暂无候选机会</td></tr>", ai=ai_html,
        recommendations="".join(recs) or "<p>没有足够证据生成建议。</p>", limitations=limitations,
    )
