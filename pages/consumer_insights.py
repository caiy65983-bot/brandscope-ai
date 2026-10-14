"""Consumer insights dashboard backed by validated annotations."""

import pandas as pd
import plotly.express as px
import streamlit as st

from core.analytics import list_evidence, monthly_topic_rates, sentiment_summary, topic_sentiment, topic_summary
from core.dashboard import begin_page


frame = begin_page("消费者洞察", "查看消费者讨论主题、文本情绪、痛点和明确表达的使用场景，并可回到原评论核查依据。")
if frame is not None:
    if frame.empty:
        st.warning("当前筛选条件下没有记录，请调整左侧筛选。")
        st.stop()
    topics = topic_summary(frame)
    sentiments = sentiment_summary(frame)
    negatives = int(frame["sentiment"].eq("negative").sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("分析评论", "{:,}".format(len(frame)))
    c2.metric("负面文本占比", "{:.1%}".format(negatives / len(frame)))
    c3.metric("需求主题", str(len(topics)))
    c4.metric("有痛点记录", "{:,}".format(sum(bool(v) for v in frame["pain_points"])))
    st.caption("情绪为文本表达分类，不代表用户真实满意度。主题提及率按评论数计算，一条评论多主题时各主题比例可合计超过 100%。")

    left, right = st.columns(2)
    with left:
        st.subheader("需求主题提及")
        if topics.empty:
            st.info("没有可统计的主题标签。")
        else:
            chart = px.bar(topics, x="需求主题", y="提及率", hover_data={"提及评论数": True, "提及率": ":.1%"}, labels={"提及率": "评论提及率", "需求主题": "主题"})
            chart.update_yaxes(tickformat=".0%")
            st.plotly_chart(chart, use_container_width=True)
    with right:
        st.subheader("文本情绪分布")
        chart = px.pie(sentiments, names="情绪", values="评论数", hole=0.48, hover_data={"占比": ":.1%"})
        st.plotly_chart(chart, use_container_width=True)

    trend, reason = monthly_topic_rates(frame)
    st.subheader("主题讨论趋势")
    if reason:
        st.info("趋势暂不可用：" + reason)
    elif not trend.empty:
        chart = px.line(trend, x="月份", y="提及率", color="需求主题", markers=True, hover_data={"提及评论数": True, "样本量": True}, labels={"提及率": "当月评论提及率", "月份": "月份"})
        chart.update_yaxes(tickformat=".0%")
        st.plotly_chart(chart, use_container_width=True)
        st.caption("每月分母为该月有有效日期的评论数；这是评论样本中的讨论变化，不是总体市场需求预测。")

    left, right = st.columns(2)
    with left:
        st.subheader("主题负面文本比例")
        per_topic = topic_sentiment(frame)
        if not per_topic.empty:
            chart = px.bar(per_topic.sort_values("负面比例"), x="负面比例", y="需求主题", orientation="h", hover_data={"负面评论数": True, "提及评论数": True}, labels={"负面比例": "负面文本占比"})
            chart.update_xaxes(tickformat=".0%")
            st.plotly_chart(chart, use_container_width=True)
    with right:
        st.subheader("明确表达的消费场景")
        scene_rows = [{"消费场景": scene} for scenes in frame["scenarios"] for scene in scenes]
        if scene_rows:
            counts = pd.DataFrame(scene_rows)["消费场景"].value_counts().rename_axis("消费场景").reset_index(name="提及次数")
            st.dataframe(counts, width="stretch", hide_index=True)
        else:
            st.info("当前样本没有明确场景标签。系统不会从模糊文本推断场景。")

    pain_rows = [{"痛点": pain, "record_id": row.record_id} for row in frame.itertuples() for pain in row.pain_points]
    st.subheader("消费者痛点")
    if pain_rows:
        pain_counts = pd.DataFrame(pain_rows)["痛点"].value_counts().rename_axis("痛点").reset_index(name="评论数")
        st.dataframe(pain_counts, width="stretch", hide_index=True)
    else:
        st.info("当前样本没有标注到明确痛点。")

    st.subheader("查看原始评论证据")
    options = ["全部主题"] + (topics["需求主题"].tolist() if not topics.empty else [])
    chosen = st.selectbox("按主题筛选证据", options)
    sentiment_choice = st.selectbox("按情绪筛选", ["全部情绪", "positive", "negative", "neutral", "mixed"])
    evidence = list_evidence(frame, None if chosen == "全部主题" else chosen, None if sentiment_choice == "全部情绪" else sentiment_choice)
    st.dataframe(evidence, width="stretch", hide_index=True, height=400)
