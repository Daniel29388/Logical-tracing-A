"""Render logic-board dashboard reports."""

from __future__ import annotations

import re
from typing import Any

import streamlit as st

from tradingagents.event_driven.boards import LogicBoard


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def _render_stock_pool(board: LogicBoard) -> None:
    if not board.stocks:
        st.info("这个板块还没有股票池。点击左侧“刷新板块看板”，系统会先根据事件逻辑自动建池。")
        return

    rows = [
        {"代码": item.code, "名称": item.name or "-", "来源": item.source or "-"}
        for item in board.stocks
    ]
    st.dataframe(rows, width="stretch", hide_index=True)


def render_board_dashboard(
    board: LogicBoard,
    final_state: dict[str, Any] | None = None,
    elapsed: float | None = None,
) -> None:
    """Render one logic-board dashboard."""
    state = final_state or {}
    tracker_report = state.get("tracker_report") or board.tracker_report
    technical_report = state.get("technical_report") or board.technical_report
    block_report = state.get("block_report") or board.block_report
    selection_report = state.get("selection_report") or board.selection_report

    stats_html = ""
    if elapsed is not None:
        m, s = divmod(int(elapsed), 60)
        stats_html = f'<div style="font-size:0.9rem; color:#888; margin-top:0.3rem;">耗时 {m}:{s:02d}</div>'

    st.markdown(
        f"""
        <div style="
            background: #141414;
            border: 1px solid #292929;
            border-radius: 8px;
            padding: 1.25rem 1.4rem;
            margin: 0.8rem 0 1.4rem;
        ">
            <div style="font-size:0.78rem; color:#888; letter-spacing:2px;">LOGIC BOARD</div>
            <div style="font-size:1.65rem; font-weight:800; color:#f5f1eb; margin:0.45rem 0;">
                {board.name}
            </div>
            <div style="font-size:0.95rem; color:#ff8c42;">
                {len(board.stocks)} 只股票 · 近 {board.tracking_days} 个交易日追踪 · 上次刷新 {board.last_trade_date or "未刷新"}
            </div>
            {stats_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("AI 自动生成，仅供学习研究，不构成投资建议。")

    tab_pool, tab_track, tab_tech, tab_logic = st.tabs(["股票池", "30日追踪", "技术面", "建池逻辑"])

    with tab_pool:
        _render_stock_pool(board)

    with tab_track:
        if tracker_report:
            st.markdown(_strip_think(str(tracker_report)))
        else:
            st.info("暂无追踪报告。点击左侧“刷新板块看板”。")

    with tab_tech:
        if technical_report:
            st.markdown(_strip_think(str(technical_report)))
        else:
            st.info("暂无技术面报告。点击左侧“刷新板块看板”。")

    with tab_logic:
        if block_report:
            st.markdown("#### 逻辑板块")
            st.markdown(_strip_think(str(block_report)))
        if selection_report:
            st.markdown("#### 入池理由")
            st.markdown(_strip_think(str(selection_report)))
        if not block_report and not selection_report:
            st.info("暂无建池逻辑。首次刷新会自动生成。")


def render_event_report(
    final_state: dict[str, Any],
    seed: str,
    trade_date: str,
    elapsed: float | None = None,
) -> None:
    """Compatibility wrapper for older callers."""
    from tradingagents.event_driven.boards import build_board_from_state

    board = build_board_from_state(final_state, seed, trade_date)
    render_board_dashboard(board, final_state, elapsed)


def render_report(*args, **kwargs) -> None:
    """Legacy stock-analysis renderer removed from the board-only UI."""
    st.info("个股投研入口已移除。请在左侧选择逻辑板块并刷新看板。")
