"""Sidebar for logic-board selection and LLM config."""

from __future__ import annotations

import os
from datetime import date

import streamlit as st

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.event_driven.boards import LogicBoard, ensure_default_boards, save_logic_board
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

_PROVIDERS: list[tuple[str, str]] = [
    ("DeepSeek", "deepseek"),
    ("MiniMax（国内直连）", "minimax"),
    ("通义千问 Qwen", "qwen"),
    ("智谱 GLM", "glm"),
    ("OpenAI", "openai"),
    ("Anthropic", "anthropic"),
    ("Google Gemini", "google"),
    ("xAI Grok", "xai"),
    ("Ollama（本地）", "ollama"),
]

_PROVIDER_DISPLAY = [name for name, _ in _PROVIDERS]
_PROVIDER_KEYS = [key for _, key in _PROVIDERS]


def _default_provider_idx() -> int:
    provider = "deepseek" if os.environ.get("DEEPSEEK_API_KEY") else "minimax"
    return _PROVIDER_KEYS.index(provider)


def _default_model_idx(values: list[str], preferred: str) -> int:
    return values.index(preferred) if preferred in values else 0


def _render_llm_config() -> None:
    provider_idx = st.selectbox(
        "LLM 供应商",
        range(len(_PROVIDERS)),
        format_func=lambda i: _PROVIDER_DISPLAY[i],
        key="llm_provider_idx",
        index=_default_provider_idx(),
    )
    provider_key = _PROVIDER_KEYS[provider_idx]
    st.session_state["llm_provider"] = provider_key

    if provider_key in MODEL_OPTIONS:
        quick_options = MODEL_OPTIONS[provider_key]["quick"]
        deep_options = MODEL_OPTIONS[provider_key]["deep"]
        quick_labels = [label for label, _ in quick_options]
        quick_values = [value for _, value in quick_options]
        deep_labels = [label for label, _ in deep_options]
        deep_values = [value for _, value in deep_options]

        quick_idx = st.selectbox(
            "看板刷新模型",
            range(len(quick_options)),
            format_func=lambda i: quick_labels[i],
            key="quick_model_idx",
            index=_default_model_idx(quick_values, "deepseek-chat") if provider_key == "deepseek" else 0,
        )
        st.session_state["quick_think_llm"] = quick_values[quick_idx]

        deep_idx = st.selectbox(
            "建板块模型",
            range(len(deep_options)),
            format_func=lambda i: deep_labels[i],
            key="deep_model_idx",
            index=_default_model_idx(deep_values, "deepseek-chat") if provider_key == "deepseek" else 0,
        )
        st.session_state["deep_think_llm"] = deep_values[deep_idx]


def render_sidebar() -> None:
    st.markdown(
        """
        <div style="text-align:center; margin-bottom:1.4rem;">
            <span style="font-size:1.9rem; font-weight:800; color:#ff5a1f;">逻辑追踪</span>
            <div style="font-size:0.82rem; color:#888; margin-top:0.35rem;">
                板块看板 · 30日追踪 · 技术分析
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    boards = ensure_default_boards(DEFAULT_CONFIG["results_dir"])
    pending_board_id = st.session_state.pop("pending_selected_board_id", None)
    current_board_id = pending_board_id or st.session_state.get("selected_board_id")
    default_idx = 0
    if current_board_id:
        default_idx = next((i for i, board in enumerate(boards) if board.id == current_board_id), 0)
    board_labels = [f"{b.name}  ·  {len(b.stocks)}只" for b in boards]
    selected_idx = st.selectbox(
        "板块",
        range(len(boards)),
        format_func=lambda i: board_labels[i],
        key="board_select_idx",
        index=default_idx,
    )
    selected = boards[selected_idx]
    st.session_state["selected_board_id"] = selected.id

    st.caption(f"上次刷新: {selected.last_trade_date or '未刷新'}")
    if selected.stocks:
        st.caption("股票池: " + " / ".join(f"{s.code}{s.name}" for s in selected.stocks[:6]))
    else:
        st.caption("股票池为空，首次刷新会先自动建池。")

    trade_date = st.date_input("刷新日期", value=date.today(), key="input_date")

    if st.button("刷新板块看板", width="stretch", type="primary"):
        st.session_state["start_board_refresh"] = {
            "board_id": selected.id,
            "board_name": selected.name,
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "has_stocks": bool(selected.stocks),
        }
        st.session_state["viewing_board_id"] = selected.id
        st.session_state["tracker"] = None

    st.markdown("---")
    st.markdown("#### 新建逻辑板块")
    new_name = st.text_input("板块名称", placeholder="例：长鑫存储上市", key="new_board_name")
    new_seed = st.text_area(
        "触发事件 / 逻辑线索",
        placeholder="例：长鑫存储上市 -> 国产存储/合肥国资/半导体设备",
        key="new_board_seed",
        height=82,
    )
    if st.button("保存新板块", width="stretch", disabled=not new_name.strip() or not new_seed.strip()):
        from tradingagents.event_driven.boards import board_id_from_name

        board = LogicBoard(
            id=board_id_from_name(new_name.strip()),
            name=new_name.strip(),
            seed_query=new_seed.strip(),
            source_event=new_seed.strip(),
        )
        save_logic_board(board, DEFAULT_CONFIG["results_dir"])
        st.session_state["pending_selected_board_id"] = board.id
        st.session_state["selected_board_id"] = board.id
        st.rerun()

    st.markdown("---")
    with st.expander("模型配置", expanded=False):
        _render_llm_config()

    st.caption("仅供学习研究，不构成投资建议")
