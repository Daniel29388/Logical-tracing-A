"""Real-time progress display for the board pipeline."""

from __future__ import annotations

import streamlit as st

from web.progress import (
    BOARD_BUILD_STAGES,
    BOARD_REFRESH_STAGES,
    EVENT_PIPELINE_STAGES,
    PIPELINE_STAGES,
    ProgressTracker,
)


def _status_badge(status: str) -> str:
    if status == "done":
        return '<span style="color:#22c55e; font-size:1.3rem;">●</span>'
    if status == "active":
        return '<span style="color:#ff5a1f; font-size:1.3rem;">●</span>'
    return '<span style="color:#333; font-size:1.3rem;">○</span>'


def _format_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _stages_for_mode(mode: str | None) -> list[dict[str, str]]:
    if mode == "板块建池":
        return BOARD_BUILD_STAGES
    if mode == "逻辑板块":
        return BOARD_REFRESH_STAGES
    return PIPELINE_STAGES


def render_progress(tracker: ProgressTracker) -> None:
    """Render the pipeline progress panel."""
    mode = st.session_state.get("active_analysis_mode")
    stages = _stages_for_mode(mode)

    st.markdown(
        f"""
        <div style="text-align:center; margin:1rem 0 0.5rem;">
            <span style="font-size:1.6rem; font-weight:700; color:#f5f1eb;">看板刷新中</span>
            <span style="font-size:1.1rem; color:#888; margin-left:0.8rem;">{tracker.ticker}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    completed = len(tracker.completed_stages)
    total = len(stages)
    pct = completed / total if total else 0
    st.progress(pct, text=f"{completed}/{total} 阶段完成 · {_format_time(tracker.elapsed)}")

    st.markdown(
        '<div style="margin:0.5rem 0 0.3rem; font-size:0.85rem; color:#888;">BOARD FLOW</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(len(stages))
    for col, stage in zip(cols, stages):
        status = tracker.stage_status(stage["id"])
        label_color = "#f5f1eb" if status == "active" else "#888" if status == "pending" else "#22c55e"
        col.markdown(
            f"""
            <div style="text-align:center; padding:0.5rem 0;">
                {_status_badge(status)}<br>
                <span style="font-size:0.75rem; color:{label_color};">{stage['name']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("LLM 调用", tracker.llm_calls)
    c2.metric("工具调用", tracker.tool_calls)
    c3.metric("输入 Tokens", f"{tracker.tokens_in:,}")
    c4.metric("输出 Tokens", f"{tracker.tokens_out:,}")

    if tracker.current_stage == "prefetch":
        st.info("正在抓取股票池的行情、指标和资金数据；这个阶段只会增加工具调用，抓取完成后才会进入 LLM 报告生成。")
    elif tracker.current_stage == "discovery_prefetch":
        st.info("正在用关键词和强势股工具反查候选股票池；这个阶段会先增加工具调用，然后进入建池 Agent。")

    if tracker.error:
        st.error(f"错误: {tracker.error}")

    completed_reports = [
        (stage["name"], stage["icon"], tracker.stage_reports[stage["id"]])
        for stage in stages
        if stage["id"] in tracker.stage_reports
    ]

    if completed_reports:
        st.markdown(
            '<div style="margin:0.5rem 0 0.3rem; font-size:0.85rem; color:#888;">'
            f"REPORTS ({len(completed_reports)})</div>",
            unsafe_allow_html=True,
        )
        for name, icon, report in reversed(completed_reports):
            is_latest = name == completed_reports[-1][0]
            with st.expander(f"{icon} {name}", expanded=is_latest):
                st.markdown(report[:3000])
