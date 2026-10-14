"""Transparent opportunity hypotheses with explicit unavailable dimensions."""

import pandas as pd
import plotly.express as px
import streamlit as st

from core.analytics import list_evidence
from core.dashboard import begin_page
from core.opportunity_engine import build_opportunities, rank_opportunities


frame = begin_page("营销机会雷达", "使用可观测需求、时间趋势、竞品主题与用户输入的品牌适配度，形成可追溯的优先级假设。")
if frame is not None:
    if frame.empty:
        st.warning("当前筛选条件下没有记录。")
        st.stop()
    brands = sorted(frame["brand"].dropna().astype(str).unique().tolist()) if "brand" in frame else []
    left, right = st.columns(2)
    with left:
        target = st.selectbox("目标品牌", ["（不指定）"] + brands, help="缺少品牌字段时，竞品覆盖缺口不可用。")
        target_brand = None if target == "（不指定）" else target
    with right:
        fit_rationale = st.text_input("本品牌定位/目标人群依据（由你填写）", placeholder="例如：主打通勤便捷的平价咖啡", key="opportunity_fit_rationale")
    preliminary = build_opportunities(frame, target_brand)
    fit_table = pd.DataFrame({"需求主题": [item["需求主题"] for item in preliminary["opportunities"]], "人工适配评分（0–100）": pd.Series([None] * len(preliminary["opportunities"]), dtype="Int64")})
    if fit_rationale.strip():
        st.caption("按主题逐项填写适配评分；空白主题的品牌适配度保持不可用。评分仅代表你输入的判断。")
        fit_edits = st.data_editor(
            fit_table, width="stretch", hide_index=True, num_rows="fixed", key="opportunity_fit_" + (target_brand or "unspecified"),
            disabled=["需求主题"],
            column_config={"人工适配评分（0–100）": st.column_config.NumberColumn(min_value=0, max_value=100, step=1, format="%d")},
        )
        user_fit = {
            row["需求主题"]: int(row["人工适配评分（0–100）"])
            for _, row in fit_edits.iterrows() if pd.notna(row["人工适配评分（0–100）"])
        }
    else:
        user_fit = None
        st.info("品牌适配度暂不可用：请填写定位依据后再手动给出评分。")

    st.subheader("评分权重")
    weight_cols = st.columns(4)
    names = ["需求热度", "趋势增长", "竞品覆盖缺口", "品牌适配度"]
    defaults = [35, 25, 25, 15]
    weights = {name: float(weight_cols[i].slider(name, 0, 100, defaults[i], key="opportunity_weight_" + str(i))) for i, name in enumerate(names)}
    st.session_state["opportunity_config"] = {
        "target_brand": target_brand,
        "fit_rationale": fit_rationale.strip(),
        "fit_scores": user_fit or {},
        "weights": weights,
    }
    st.caption("权重会在当前可用维度内重新归一化。机会分是当前样本中的辅助优先级，不代表市场增长概率或商业收益。")
    if sum(weights.values()) == 0:
        st.warning("请至少为一个维度设置大于 0 的权重。")
        st.stop()

    result = build_opportunities(frame, target_brand, user_fit)
    ranked = rank_opportunities(result, weights)
    if ranked.empty:
        st.info("当前数据没有可生成的主题机会。")
        st.stop()
    if result["trend_unavailable_reason"]:
        st.info("趋势增长暂不可用：" + result["trend_unavailable_reason"])
    if target_brand and result["gap_unavailable_reason"]:
        st.info("竞品覆盖缺口暂不可用：" + result["gap_unavailable_reason"])

    st.subheader("候选机会排序")
    display = ranked.copy()
    display["提及率"] = display["提及率"].map(lambda value: "{:.1%}".format(value))
    st.dataframe(display, width="stretch", hide_index=True, height=380)
    chart_data = ranked.dropna(subset=["综合评分"])
    if not chart_data.empty:
        chart = px.bar(chart_data.sort_values("综合评分"), x="综合评分", y="需求主题", orientation="h", color="综合评分", color_continuous_scale="Tealgrn", hover_data=["提及评论数", "样本量", "需求热度", "趋势增长", "竞品覆盖缺口", "品牌适配度"])
        st.plotly_chart(chart, use_container_width=True)
    else:
        st.info("目前没有任何可用权重维度，无法计算综合分。")

    st.subheader("评分依据与消费者证据")
    topic = st.selectbox("查看机会详情", ranked["需求主题"].tolist())
    opportunity = next(item for item in result["opportunities"] if item["需求主题"] == topic)
    details = pd.DataFrame([
        {"维度": name, "得分": "{:.1f}".format(cell["score"]) if cell["available"] else "不可用", "说明": cell["reason"]}
        for name, cell in opportunity["维度"].items()
    ])
    st.dataframe(details, width="stretch", hide_index=True)
    st.markdown("**主要需求：** {}。当前筛选中该主题提及 {:,} 条 / {:,} 条（{:.1%}）。".format(topic, opportunity["提及评论数"], opportunity["样本量"], opportunity["提及率"]))
    st.markdown("**竞品参考：** " + opportunity["竞品表现"])
    st.markdown("**初步验证方向：** " + opportunity["建议"])
    st.caption(opportunity["数据提示"] + "。评分权重只在可用维度之间归一化；趋势增长使用当前样本内相对变化，竞品缺口是代理指标。")
    st.caption("建议属于基于主题的规则化验证方向。执行前应查看证据、确认品牌约束，并通过用户研究或小规模实验验证。")
    st.dataframe(list_evidence(frame, topic=topic), width="stretch", hide_index=True, height=350)
