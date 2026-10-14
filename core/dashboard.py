"""Shared data access, filters and page framing for the analysis dashboards."""

from typing import Optional

import pandas as pd
import streamlit as st

from core.analytics import build_labeled_frame
from core.styles import APP_CSS




def begin_page(title: str, subtitle: str) -> Optional[pd.DataFrame]:
    st.set_page_config(page_title="BrandScope AI · " + title, page_icon="◉", layout="wide")
    st.markdown(APP_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("## ◉ BrandScope AI")
        st.caption("消费者洞察与品牌营销分析")
        st.markdown("---")
        st.page_link("app.py", label="数据工作台")
        st.page_link("pages/consumer_insights.py", label="消费者洞察")
        st.page_link("pages/competitor_analysis.py", label="竞品分析")
        st.page_link("pages/opportunity_radar.py", label="营销机会雷达")
        st.page_link("pages/strategy_report.py", label="AI 策略报告")
        st.markdown("---")
        st.caption("分析工作区 · 交互看板与策略报告")
    st.markdown('<div class="dash-hero"><h1>{}</h1><p>{}</p></div>'.format(title, subtitle), unsafe_allow_html=True)

    run = st.session_state.get("annotation_run")
    if not run or st.session_state.get("annotation_dataset_id") != st.session_state.get("dataset_id"):
        st.info("先到“数据工作台”确认数据集并完成文本标注，再返回本页查看洞察。")
        return None
    source = st.session_state.get("annotation_source_frame")
    if source is None:
        source = st.session_state.get("dataset_cleaned")
        if source is None:
            st.info("当前会话中没有已确认的数据集，请返回数据工作台重新确认。")
            return None
        selected = st.session_state.get("dataset_brands", [])
        if selected and "brand" in source.columns:
            source = source.loc[source["brand"].isin(selected)].reset_index(drop=True)
    frame = build_labeled_frame(source, run.annotations)
    if frame.empty:
        st.warning("当前数据集没有可匹配的标注结果。请在数据工作台重新运行文本标注。")
        return None
    if st.session_state.get("dataset_is_demo"):
        st.warning("模拟演示数据 · 以下结果用于体验产品功能，不代表真实市场研究。")
    else:
        st.caption("分析数据集：{} · {:,} 条有标注的评论 · 结果来源：{}".format(
            st.session_state.get("dataset_name", "用户数据"), len(frame), run.mode
        ))

    with st.sidebar:
        st.markdown("### 分析筛选")
        if "brand" in frame.columns and frame["brand"].notna().any():
            brands = sorted(frame["brand"].dropna().astype(str).unique().tolist())
            previous = st.session_state.get("dashboard_brands")
            default = [brand for brand in previous if brand in brands] if previous is not None else brands
            selected_brands = st.multiselect("品牌", brands, default=default, key="dashboard_brands")
            frame = frame.loc[frame["brand"].isin(selected_brands)]
        if "published_at" in frame.columns:
            dates = pd.to_datetime(frame["published_at"], errors="coerce").dropna()
            if not dates.empty:
                date_min, date_max = dates.min().date(), dates.max().date()
                current = st.session_state.get("dashboard_dates")
                if not isinstance(current, tuple) or len(current) != 2 or current[0] < date_min or current[1] > date_max:
                    current = (date_min, date_max)
                selection = st.date_input("日期范围", value=current, min_value=date_min, max_value=date_max, key="dashboard_dates")
                if isinstance(selection, tuple) and len(selection) == 2:
                    start, end = pd.Timestamp(selection[0]), pd.Timestamp(selection[1]) + pd.Timedelta(days=1)
                    parsed = pd.to_datetime(frame["published_at"], errors="coerce")
                    frame = frame.loc[parsed.ge(start) & parsed.lt(end)]
    st.caption("筛选后样本：{:,} 条。主题提及率以当前筛选评论数为分母；一条评论可涉及多个主题。".format(len(frame)))
    return frame.reset_index(drop=True)


def render_evidence(frame: pd.DataFrame, topic: Optional[str] = None, sentiment: Optional[str] = None, key: str = "evidence") -> None:
    from core.analytics import list_evidence

    evidence = list_evidence(frame, topic, sentiment)
    st.dataframe(evidence, width="stretch", hide_index=True, height=380)

