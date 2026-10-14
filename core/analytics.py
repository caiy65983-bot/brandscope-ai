"""Deterministic calculations for annotated consumer feedback."""

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


SENTIMENTS = ["positive", "negative", "neutral", "mixed"]


def build_labeled_frame(source: pd.DataFrame, annotations: Sequence) -> pd.DataFrame:
    """Join annotations to exactly the cleaned rows used by the annotation run."""
    frame = source.copy().reset_index(drop=True)
    generated = []
    for index, row in frame.iterrows():
        raw_id = row.get("record_id")
        rid = "" if pd.isna(raw_id) else str(raw_id).strip()
        generated.append(rid or "R{:06d}".format(index + 1))
    frame["record_id"] = generated
    annotation_rows = []
    for item in annotations:
        annotation_rows.append({
            "record_id": item.record_id,
            "topics": [topic.value for topic in item.topics],
            "sentiment": item.sentiment.value,
            "pain_points": item.pain_points,
            "purchase_motivation": item.purchase_motivation,
            "scenarios": item.scenarios,
            "evidence_text": item.evidence_text,
            "analysis_method": item.analysis_method,
        })
    labels = pd.DataFrame(annotation_rows)
    if labels.empty:
        return frame.iloc[0:0].copy()
    return frame.merge(labels, on="record_id", how="inner", validate="one_to_one")


def topic_summary(frame: pd.DataFrame) -> pd.DataFrame:
    total = len(frame)
    counts: Dict[str, int] = {}
    for values in frame.get("topics", []):
        for topic in set(values or []):
            counts[topic] = counts.get(topic, 0) + 1
    rows = [{"需求主题": topic, "提及评论数": count, "提及率": count / total if total else 0.0}
            for topic, count in counts.items()]
    return pd.DataFrame(rows, columns=["需求主题", "提及评论数", "提及率"]).sort_values("提及评论数", ascending=False).reset_index(drop=True)


def sentiment_summary(frame: pd.DataFrame) -> pd.DataFrame:
    counts = frame.get("sentiment", pd.Series(dtype=str)).value_counts()
    total = int(counts.sum())
    return pd.DataFrame([
        {"情绪": sentiment, "评论数": int(counts.get(sentiment, 0)), "占比": float(counts.get(sentiment, 0)) / total if total else 0.0}
        for sentiment in SENTIMENTS
    ])


def brand_topic_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for brand, group in frame.dropna(subset=["brand"]).groupby("brand"):
        denom = len(group)
        counts: Dict[str, int] = {}
        for values in group["topics"]:
            for topic in set(values or []):
                counts[topic] = counts.get(topic, 0) + 1
        for topic, count in counts.items():
            rows.append({"品牌": brand, "需求主题": topic, "评论数": count, "样本量": denom, "提及率": count / denom if denom else 0.0})
    return pd.DataFrame(rows, columns=["品牌", "需求主题", "评论数", "样本量", "提及率"])


def topic_sentiment(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for topic in sorted({topic for items in frame.get("topics", []) for topic in (items or [])}):
        subset = frame.loc[frame["topics"].map(lambda values: topic in (values or []))]
        neg = int(subset["sentiment"].eq("negative").sum())
        rows.append({"需求主题": topic, "提及评论数": len(subset), "负面评论数": neg, "负面比例": neg / len(subset) if len(subset) else 0.0})
    return pd.DataFrame(rows)


def list_evidence(frame: pd.DataFrame, topic: Optional[str] = None, sentiment: Optional[str] = None, limit: int = 500) -> pd.DataFrame:
    subset = frame
    if topic:
        subset = subset.loc[subset["topics"].map(lambda values: topic in (values or []))]
    if sentiment:
        subset = subset.loc[subset["sentiment"].eq(sentiment)]
    columns = [name for name in ("record_id", "brand", "platform", "published_at", "content", "topics", "sentiment", "pain_points", "purchase_motivation", "scenarios", "evidence_text", "analysis_method") if name in subset.columns]
    return subset[columns].head(limit).copy()


def monthly_topic_rates(frame: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str]]:
    if "published_at" not in frame:
        return pd.DataFrame(), "数据中没有日期字段，无法计算时间趋势。"
    dated = frame.loc[frame["published_at"].notna()].copy()
    if len(dated) < 50 or dated.empty:
        return pd.DataFrame(), "有效日期记录少于 50 条，趋势样本不足。"
    dates = pd.to_datetime(dated["published_at"], errors="coerce")
    dated = dated.loc[dates.notna()].copy()
    dated["月份"] = pd.to_datetime(dates.loc[dated.index]).dt.to_period("M").astype(str)
    if dated["月份"].nunique() < 3:
        return pd.DataFrame(), "日期跨度不足 3 个自然月，不能提供趋势分数。"
    all_topics = sorted({topic for values in dated["topics"] for topic in (values or [])})
    rows = []
    for month, group in dated.groupby("月份", sort=True):
        counts: Dict[str, int] = {}
        for values in group["topics"]:
            for topic in set(values or []):
                counts[topic] = counts.get(topic, 0) + 1
        for topic in all_topics:
            count = counts.get(topic, 0)
            rows.append({"月份": month, "需求主题": topic, "提及评论数": count, "样本量": len(group), "提及率": count / len(group)})
    return pd.DataFrame(rows), None


def growth_by_topic(trend: pd.DataFrame) -> Dict[str, float]:
    if trend.empty:
        return {}
    topics = sorted(trend["需求主题"].unique())
    raw = {}
    months = sorted(trend["月份"].unique())
    first_rows = trend.loc[trend["月份"].isin(months[:min(2, len(months))])]
    last_rows = trend.loc[trend["月份"].isin(months[-min(2, len(months)):])]
    first = first_rows.groupby("需求主题")["提及评论数"].sum() / first_rows.groupby("需求主题")["样本量"].sum()
    last = last_rows.groupby("需求主题")["提及评论数"].sum() / last_rows.groupby("需求主题")["样本量"].sum()
    for topic in topics:
        a, b = float(first.get(topic, 0)), float(last.get(topic, 0))
        raw[topic] = ((b - a) / a * 100) if a > 0 else (100.0 if b > 0 else 0.0)
    low, high = min(raw.values()), max(raw.values())
    if high == low:
        return {topic: 50.0 for topic in raw}
    return {topic: max(0.0, min(100.0, (value - low) / (high - low) * 100)) for topic, value in raw.items()}
