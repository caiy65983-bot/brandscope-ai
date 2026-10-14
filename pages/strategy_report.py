"""Evidence-based HTML strategy report, with an optional constrained AI layer."""

import re
from pathlib import Path

import streamlit as st

from core.dashboard import begin_page
from core.env_config import load_env_file
from core.report_generator import build_report_data, generate_ai_narrative, render_report_html
from services.llm_client import LLMConfig
from services.storage import AnalysisStorage


ROOT = Path(__file__).resolve().parents[1]
load_env_file(ROOT / ".env")
frame = begin_page("AI 策略报告", "把消费者需求、品牌差异和机会评分汇总为带计算口径与原始评论证据的可下载报告。")
if frame is not None:
    if frame.empty:
        st.warning("当前筛选条件下没有记录，无法生成报告。")
        st.stop()

    run = st.session_state["annotation_run"]
    dataset_id = st.session_state["dataset_id"]
    saved_config = st.session_state.get("opportunity_config", {})
    default_target = saved_config.get("target_brand")
    strategy_context = st.text_area(
        "项目背景（可选）",
        placeholder="例如：本季度希望改善通勤场景的复购体验；请只填写已确认的品牌目标或业务约束。",
        key="report_strategy_context",
    )
    model_config = LLMConfig.from_env()
    if model_config.configured:
        mode = st.radio("报告解读方式", ["数据摘要报告（不调用 AI）", "AI 策略解读 + 数据报告（调用模型）"], horizontal=True)
        if mode.startswith("AI "):
            st.caption("AI 解读会把本次计算摘要和少量代表性评论发送到已配置的模型服务；报告数值仍由本地 Python 计算。")
    else:
        mode = "数据摘要报告（不调用 AI）"
        st.info("未检测到模型 API。仍可生成规则化数据摘要；它不会被标记为 AI 生成。")
        with st.expander("配置模型 API 后启用 AI 定性解读"):
            st.markdown("复制 `.env.example` 为 `.env`，填写 API 密钥、服务地址和模型名称，然后重启 Streamlit。不要把密钥发到聊天或提交到代码库。")

    if st.button("生成并保存策略报告", type="primary", key="generate_strategy_report"):
        config = st.session_state.get("opportunity_config", {})
        report = build_report_data(
            frame=frame,
            dataset_name=st.session_state.get("dataset_name", "当前分析项目"),
            is_demo=bool(st.session_state.get("dataset_is_demo")),
            target_brand=config.get("target_brand", default_target),
            fit_scores=config.get("fit_scores"),
            weights=config.get("weights"),
            strategy_context="\n".join(part for part in (
                strategy_context.strip(),
                "品牌适配度输入依据：" + config.get("fit_rationale", "") if config.get("fit_rationale") else "",
            ) if part),
        )
        if mode.startswith("AI "):
            try:
                narrative = generate_ai_narrative(report, model_config)
                report["ai_narrative"] = narrative.model_dump(mode="json")
                st.session_state["report_generation_mode"] = "AI 定性解读 + Python 计算指标"
            except Exception as exc:
                st.session_state["report_generation_error"] = str(exc)
                st.session_state["report_generation_mode"] = "规则化数据摘要（AI 解读未完成）"
                st.warning("AI 解读没有通过调用或证据校验；已保留规则化数据摘要。错误：{}".format(exc))
        else:
            st.session_state["report_generation_mode"] = "规则化数据摘要（未调用 AI）"
            st.session_state.pop("report_generation_error", None)
        report_html = render_report_html(report)
        storage = AnalysisStorage(ROOT / "data" / "brandscope.sqlite3")
        storage.save_report(dataset_id, report, report_html)
        st.session_state["saved_strategy_report"] = {"payload": report, "html": report_html, "updated_at": "刚刚"}
        st.session_state["saved_strategy_report_dataset"] = dataset_id

    if st.session_state.get("saved_strategy_report_dataset") == dataset_id:
        saved = st.session_state.get("saved_strategy_report")
    else:
        saved = AnalysisStorage(ROOT / "data" / "brandscope.sqlite3").get_report(dataset_id)
        if saved:
            st.session_state["saved_strategy_report"] = saved
            st.session_state["saved_strategy_report_dataset"] = dataset_id
        else:
            st.session_state.pop("saved_strategy_report", None)
            st.session_state.pop("saved_strategy_report_dataset", None)

    if saved:
        report = saved["payload"]
        # Apply the current layout to saved reports without regenerating their analysis.
        display_html = render_report_html(report)
        mode_text = st.session_state.get("report_generation_mode", "已保存报告")
        st.success("报告已保存：{} · {} · {} 条评论".format(mode_text, report["source_label"], report["record_count"]))
        if report["source_label"] == "模拟演示数据":
            st.warning("模拟演示报告 · 数据和结论仅用于体验产品，不代表真实市场研究。")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("分析评论", "{:,}".format(report["record_count"]))
        c2.metric("消费者主题", str(len(report["topic_stats"])))
        c3.metric("纳入品牌", str(len(report["brand_counts"])))
        c4.metric("报告更新时间", str(saved.get("updated_at", "")))
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(report["dataset_name"])).strip("._") or "brandscope"
        st.download_button(
            "下载 HTML 报告", data=display_html.encode("utf-8"), file_name=safe_name + "_strategy_report.html",
            mime="text/html", type="primary",
        )
        st.caption("报告保存在本机 data/brandscope.sqlite3，证据区会保存少量代表性评论。导出文件是独立 HTML，可用浏览器打开。")
        st.markdown("### HTML 报告预览")
        st.components.v1.html(display_html, height=1500, scrolling=True)
        with st.expander("查看 AI 定性解读的校验结果"):
            if report.get("ai_narrative"):
                st.markdown("**AI 生成的定性总结**")
                st.write(report["ai_narrative"]["executive_summary"])
                st.caption("AI 建议仅可引用报告证据编号；报告中的数字、占比、机会分和品牌差异由 Python 指标计算。")
            elif st.session_state.get("report_generation_error"):
                st.error(st.session_state["report_generation_error"])
            else:
                st.caption("此报告没有调用 AI；策略方向来自可解释的规则模板。")
    else:
        st.info("报告尚未生成。完成文本标注后，点击上方按钮生成并保存当前筛选条件下的报告。")
