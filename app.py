"""BrandScope AI: first-stage data workspace."""
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st
from core.ai_analyzer import AnnotationError, analyze_feedback
from core.data_cleaner import clean_feedback
from core.env_config import load_env_file
from core.data_loader import load_csv, suggest_mapping
from core.stats import dataset_summary
from core.styles import APP_CSS
from services.llm_client import LLMConfig, LLMError
from services.storage import AnalysisStorage
from models.schemas import CANONICAL_FIELDS

ROOT = Path(__file__).resolve().parent
DEMO_PATH = ROOT / "data" / "demo" / "coffee_feedback_demo.csv"
load_env_file(ROOT / ".env")

st.set_page_config(page_title="BrandScope AI · 数据工作台", page_icon="◉", layout="wide")
st.markdown(APP_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## ◉ BrandScope AI")
    st.caption("消费者洞察与品牌营销分析")
    st.markdown("---")
    st.markdown("**工作区**")
    st.page_link("app.py", label="数据工作台")
    st.page_link("pages/consumer_insights.py", label="消费者洞察")
    st.page_link("pages/competitor_analysis.py", label="竞品分析")
    st.page_link("pages/opportunity_radar.py", label="营销机会雷达")
    st.page_link("pages/strategy_report.py", label="AI 策略报告")
    st.caption("报告指标由 Python 计算；AI 解读可选")
    st.markdown("---")
    st.caption("数据工作台 · 数据管理与文本标注")

st.markdown('<div class="hero"><h1 style="margin:0">数据工作台</h1><p>导入评论数据，检查字段与数据质量，确认可用于后续分析的数据集。</p></div>', unsafe_allow_html=True)

def section_heading(title, description):
    st.subheader(title)
    st.caption(description)


with st.container(key="workspace_source"):
    section_heading("数据来源", "选择演示数据，或上传自己的消费者反馈 CSV。")
    source_choice = st.radio("数据来源", ["使用演示数据", "上传 CSV"], horizontal=True, label_visibility="collapsed")
    is_demo = source_choice == "使用演示数据"
    if is_demo:
        st.markdown('<span class="source-tag">模拟演示数据 · 3,000 条 · 不代表真实市场研究</span>', unsafe_allow_html=True)
        st.caption("咖啡行业固定随机种子生成，可用 data/demo/coffee_feedback_demo.csv 直接导入。")
        raw_bytes = DEMO_PATH.read_bytes() if DEMO_PATH.exists() else b""
        source_name = DEMO_PATH.name
    else:
        uploaded = st.file_uploader("上传消费者反馈 CSV", type=["csv"], help="兼容 UTF-8、UTF-8 BOM 和常见中文 GB18030 编码。")
        if uploaded is None:
            st.info("上传 CSV 后即可查看字段映射、质量检查和预览。")
            st.stop()
        raw_bytes = uploaded.getvalue()
        source_name = uploaded.name

try:
    raw_frame, encoding = load_csv(raw_bytes)
except Exception as exc:
    st.error(f"文件读取失败：{exc}")
    st.stop()

with st.container(key="workspace_mapping"):
    section_heading("字段映射", "自动匹配列名，也可以手动调整；评论内容是必需字段。")
    st.caption(f"文件：{source_name}　·　识别编码：{encoding}　·　原始记录：{len(raw_frame):,} 条　·　字段：{len(raw_frame.columns)} 个")
    with st.expander("查看原始数据预览", expanded=False):
        st.dataframe(raw_frame.head(12), width="stretch", hide_index=True)
    suggestions = suggest_mapping(raw_frame.columns)
    mapping = {}
    cols = st.columns(3)
    source_options = ["（未映射）"] + list(raw_frame.columns)
    for index, (canonical, label) in enumerate(CANONICAL_FIELDS.items()):
        with cols[index % 3]:
            default = suggestions.get(canonical, "")
            default_index = source_options.index(default) if default in source_options else 0
            picked = st.selectbox(label, source_options, index=default_index, key=f"map_{canonical}")
            mapping[canonical] = "" if picked == "（未映射）" else picked
    if not mapping.get("content"):
        st.error("必须映射评论内容字段，才能继续检查数据。")
        st.stop()

cleaned, cleaning = clean_feedback(raw_frame, mapping)
summary = dataset_summary(cleaned)
if len(cleaned) == 0:
    st.warning("清洗后没有可用记录，请检查评论内容映射和文件内容。")

brands = summary["brands"]
platforms = summary["platforms"]
visible = [name for name in ("record_id", "brand", "platform", "published_at", "content", "likes") if name in cleaned.columns]
with st.container(key="workspace_quality"):
    section_heading("数据质量与预览", "查看清洗结果，并在下方直接按品牌和平台筛选记录。")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("清洗后记录", f"{summary['records']:,}", f"清洗前 {cleaning['rows_before']:,}")
    m2.metric("品牌数量", f"{summary['brand_count']}", help="仅统计非空品牌名称。")
    m3.metric("数据时间范围", summary["date_range"])
    m4.metric("来源平台", f"{len(platforms)} 个", ", ".join(platforms) or "未提供")
    st.caption(f"清洗日志：清洗前 {cleaning['rows_before']:,} 条 → 清洗后 {cleaning['rows_after']:,} 条；移除 {cleaning['removed']:,} 条。无效日期保留记录并置空。")
    with st.expander("查看清洗日志", expanded=False):
        st.dataframe(pd.DataFrame(cleaning["logs"]), width="stretch", hide_index=True)
    st.markdown("#### 清洗后数据预览")
    filter_brand_col, filter_platform_col, result_col = st.columns([1, 1, 1.3])
    with filter_brand_col:
        preview_brand = st.selectbox("筛选品牌", ["全部品牌"] + brands)
    with filter_platform_col:
        preview_platform = st.selectbox("筛选平台", ["全部平台"] + platforms)
    preview = cleaned.copy()
    if preview_brand != "全部品牌":
        preview = preview.loc[preview["brand"] == preview_brand]
    if preview_platform != "全部平台":
        preview = preview.loc[preview["platform"] == preview_platform]
    with result_col:
        st.caption(f"当前显示 {len(preview):,} / {len(cleaned):,} 条")
    st.dataframe(
        preview[visible], width="stretch", hide_index=True, height=420,
        column_config={
            "content": st.column_config.TextColumn("评论内容", width="large"),
            "published_at": st.column_config.DatetimeColumn("发布日期", format="YYYY-MM-DD"),
            "likes": st.column_config.NumberColumn("点赞量", format="%d"),
        },
    )

with st.container(key="workspace_scope"):
    section_heading("分析范围", "选择纳入分析的品牌、分析维度与日期区间。")
    selected_brands = st.multiselect("纳入后续分析的品牌", brands, default=brands) if brands else []
    if not brands:
        st.info("未检测到品牌字段。后续品牌对比功能将不可用，总体文本分析仍可继续。")
    analysis_dimensions = st.multiselect(
        "分析维度",
        ["需求主题", "情绪倾向", "消费者痛点", "消费动机", "明确消费场景"],
        default=["需求主题", "情绪倾向", "消费者痛点", "消费动机", "明确消费场景"],
        help="这些选择会随数据集保存，后续分析页面按所选维度执行。",
    )
    date_values = cleaned["published_at"].dropna()
    selected_date_range = None
    if not date_values.empty:
        selected_date_range = st.date_input("分析日期范围", value=(date_values.min().date(), date_values.max().date()))
    else:
        st.caption("未提供有效日期，趋势分析将不可用。")

    if st.button("确认数据集", type="primary", disabled=cleaning["rows_after"] == 0):
        dataset_id = str(uuid4())
        st.session_state["dataset_id"] = dataset_id
        st.session_state["dataset_name"] = source_name
        st.session_state["dataset_is_demo"] = is_demo
        st.session_state["dataset_rows"] = len(cleaned)
        st.session_state["dataset_brands"] = selected_brands
        st.session_state["dataset_dimensions"] = analysis_dimensions
        st.session_state["dataset_date_range"] = selected_date_range
        st.session_state["dataset_cleaned"] = cleaned
        st.session_state["dataset_cleaning_log"] = cleaning["logs"]
        st.session_state["dataset_mapping"] = mapping
        st.session_state["dataset_encoding"] = encoding
        st.success(f"数据集已就绪：{dataset_id}。第一阶段的数据检查已完成。")
    if "dataset_id" in st.session_state:
        badge = "模拟数据" if st.session_state["dataset_is_demo"] else "用户导入数据"
        st.info(f"当前工作区数据集：{st.session_state['dataset_name']} · {st.session_state['dataset_rows']:,} 条 · {badge} · ID {st.session_state['dataset_id']}")

if "dataset_id" in st.session_state:
    with st.container(key="workspace_annotation"):
        section_heading("AI 文本标注", "将评论整理为可统计、可回溯的主题、情绪、痛点、动机与场景标签。")
        saved_frame = st.session_state.get("dataset_cleaned")
        dataset_is_demo = bool(st.session_state.get("dataset_is_demo"))
        model_config = LLMConfig.from_env()
        if dataset_is_demo and saved_frame is not None and {"demo_topic", "demo_sentiment"}.issubset(saved_frame.columns):
            st.warning("当前为模拟演示数据。按钮使用 CSV 中预置的模拟标签，不调用 AI，也不代表真实研究结论。")
            button_label = "生成演示标签（不调用 AI）"
            can_run = True
        elif model_config.configured:
            st.caption("模型配置已检测到。运行后会调用所配置的模型 API；文本内容将发送至该 API 服务。")
            button_label = "开始 AI 文本标注"
            can_run = True
        else:
            st.info("当前上传数据没有可用的演示标签。配置模型 API 后才能执行 AI 标注；其他数据检查仍可使用。")
            with st.expander("如何配置模型 API（只需设置一次）"):
                st.markdown("1. 在项目文件夹中复制 `.env.example` 并命名为 `.env`。\n2. 用记事本打开 `.env`，填入 API Key、模型名称和服务地址。\n3. 保存后，在终端按 `Ctrl+C` 停止应用，再运行 `streamlit run app.py`。\n\n**API Key 是秘密信息，不要发到聊天中，也不要提交 `.env` 文件。**")
                st.code("BRANDSCOPE_API_KEY=你的密钥\nBRANDSCOPE_BASE_URL=https://api.openai.com/v1\nBRANDSCOPE_MODEL=gpt-4o-mini", language="text")
            button_label = "开始 AI 文本标注"
            can_run = False

        if saved_frame is not None:
            st.caption("按确认数据集时选定的品牌范围执行；文本标签统计由 Python 确定性代码完成。")
            if st.button(button_label, type="primary", disabled=not can_run, key="run_text_annotation"):
                scoped_frame = saved_frame.copy()
                selected = st.session_state.get("dataset_brands", [])
                if selected and "brand" in scoped_frame:
                    scoped_frame = scoped_frame.loc[scoped_frame["brand"].isin(selected)].reset_index(drop=True)
                progress_bar = st.progress(0, text="准备标注…")
                status = st.empty()

                def update_progress(done, total):
                    ratio = done / total if total else 1.0
                    progress_bar.progress(min(1.0, ratio), text="已处理 {:,} / {:,} 条".format(done, total))

                try:
                    run = analyze_feedback(
                        scoped_frame, dataset_is_demo, model_config,
                        AnalysisStorage(ROOT / "data" / "brandscope.sqlite3"),
                        progress=update_progress,
                    )
                    st.session_state["annotation_run"] = run
                    st.session_state["annotation_dataset_id"] = st.session_state["dataset_id"]
                    st.session_state["annotation_source_frame"] = scoped_frame.copy()
                    status.success("标注完成：{} 条 · {}".format(len(run.annotations), run.mode))
                except (AnnotationError, LLMError) as exc:
                    status.error(str(exc))
                except Exception as exc:
                    status.error("标注未完成，发生意外错误：{}。可检查配置后重试。".format(exc))

        run = st.session_state.get("annotation_run")
        if run and st.session_state.get("annotation_dataset_id") == st.session_state.get("dataset_id"):
            st.success("结果来源：{}。这些情绪标签描述文本表达，不等同于实际满意度。".format(run.mode))
            a, b, c, d = st.columns(4)
            a.metric("已标注评论", "{:,}".format(len(run.annotations)))
            a11y_modes = sum(1 for item in run.annotations if item.analysis_method == "llm")
            b.metric("真实模型标注", "{:,}".format(a11y_modes))
            c.metric("缓存复用", "{:,}".format(run.cache_hits))
            d.metric("API 批次数", "{:,}".format(run.api_batches))
            st.caption("本次处理耗时 {:.1f} 秒。费用以模型服务商账单为准，平台不会根据 token 自行估算费用。".format(run.elapsed_seconds))
            if run.prompt_tokens is not None or run.completion_tokens is not None:
                st.caption("API 返回用量：输入 {} tokens，输出 {} tokens。费用以服务商账单为准。".format(run.prompt_tokens or 0, run.completion_tokens or 0))
            annotated = pd.DataFrame([
                {
                    "record_id": item.record_id,
                    "需求主题": "、".join(topic.value for topic in item.topics),
                    "情绪": item.sentiment.value,
                    "消费者痛点": "、".join(item.pain_points),
                    "消费动机": "、".join(item.purchase_motivation),
                    "明确场景": "、".join(item.scenarios),
                    "证据原文": item.evidence_text,
                    "分析来源": item.analysis_method,
                }
                for item in run.annotations
            ])
            st.dataframe(annotated, width="stretch", hide_index=True, height=360)
