"""Brand comparison dashboard using the currently filtered comment sample."""

import pandas as pd
import plotly.express as px
import streamlit as st

from core.analytics import brand_topic_matrix, topic_sentiment
from core.dashboard import begin_page


frame = begin_page("竞品分析", "对比品牌在相同主题上的评论提及率、文本情绪和明确痛点；指标只描述当前样本。")
if frame is not None:
    brands = sorted(frame["brand"].dropna().astype(str).unique().tolist()) if "brand" in frame else []
    if len(brands) < 2:
        st.info("至少需要两个品牌的有效评论，才能进行品牌比较。请检查数据字段或左侧品牌筛选。")
        st.stop()
    selected = st.multiselect("选择 2–3 个品牌对比", brands, default=brands[:min(3, len(brands))], max_selections=3, key="competitor_brands")
    compare = frame.loc[frame["brand"].isin(selected)]
    if len(selected) < 2:
        st.warning("请选择至少两个品牌。")
        st.stop()
    counts = compare.groupby("brand").size().rename("样本量").reset_index()
    for row in counts.itertuples():
        if row.样本量 < 30:
            st.warning("{} 当前只有 {} 条评论，品牌比较结果不稳定。".format(row.brand, row.样本量))
    st.dataframe(counts, width="stretch", hide_index=True)

    matrix = brand_topic_matrix(compare)
    if matrix.empty:
        st.info("所选品牌没有主题标注数据。")
    else:
        st.subheader("品牌 × 需求主题提及率矩阵")
        rates = matrix.pivot(index="品牌", columns="需求主题", values="提及率").fillna(0)
        samples = matrix.pivot(index="品牌", columns="需求主题", values="样本量").fillna(0)
        chart = px.imshow(rates, text_auto=".1%", aspect="auto", color_continuous_scale="Blues", labels={"color": "评论提及率"})
        chart.update_traces(customdata=samples, hovertemplate="品牌：%{y}<br>主题：%{x}<br>提及率：%{z:.1%}<br>该品牌样本量：%{customdata}<extra></extra>")
        st.plotly_chart(chart, use_container_width=True)
        st.caption("单元格 = 该品牌提及此主题的评论数 ÷ 当前筛选的该品牌评论总数；一条评论可进入多个主题。")

    st.subheader("品牌文本情绪比较")
    sentiment = compare.groupby(["brand", "sentiment"]).size().rename("评论数").reset_index()
    denominator = compare.groupby("brand").size().rename("品牌样本量")
    sentiment["品牌样本量"] = sentiment["brand"].map(denominator)
    sentiment["占比"] = sentiment["评论数"] / sentiment["品牌样本量"]
    chart = px.bar(sentiment, x="brand", y="占比", color="sentiment", barmode="stack", hover_data={"评论数": True, "品牌样本量": True}, labels={"brand": "品牌", "占比": "该品牌评论内比例", "sentiment": "文本情绪"})
    chart.update_yaxes(tickformat=".0%")
    st.plotly_chart(chart, use_container_width=True)
    st.caption("情绪分类反映评论文本表达，不能直接解读为用户满意度。样本来源和采样偏差会影响品牌间比较。")

    st.subheader("主题负面文本与集中痛点")
    neg_by_brand = []
    for brand, group in compare.groupby("brand"):
        for record in topic_sentiment(group).to_dict("records"):
            neg_by_brand.append({"品牌": brand, **record})
    if neg_by_brand:
        negative = pd.DataFrame(neg_by_brand)
        chart = px.bar(negative, x="需求主题", y="负面比例", color="品牌", barmode="group", hover_data={"负面评论数": True, "提及评论数": True}, labels={"负面比例": "负面文本占比"})
        chart.update_yaxes(tickformat=".0%")
        st.plotly_chart(chart, use_container_width=True)
    pain_rows = []
    for row in compare.itertuples():
        for pain in row.pain_points:
            pain_rows.append({"品牌": row.brand, "痛点": pain, "record_id": row.record_id})
    if pain_rows:
        pain = pd.DataFrame(pain_rows).groupby(["品牌", "痛点"]).size().rename("评论数").reset_index().sort_values("评论数", ascending=False)
        st.dataframe(pain, width="stretch", hide_index=True)
    else:
        st.info("当前样本没有标注到明确痛点。")

    st.subheader("品牌代表性评论")
    brand_choice = st.selectbox("查看品牌证据", selected)
    topic_options = ["全部主题"] + sorted({topic for values in compare["topics"] for topic in values})
    topic_choice = st.selectbox("需求主题", topic_options)
    evidence = compare.loc[compare["brand"].eq(brand_choice)]
    if topic_choice != "全部主题":
        evidence = evidence.loc[evidence["topics"].map(lambda values: topic_choice in values)]
    st.dataframe(evidence[[c for c in ("record_id", "brand", "platform", "content", "topics", "sentiment", "pain_points", "evidence_text") if c in evidence.columns]], width="stretch", hide_index=True, height=350)
