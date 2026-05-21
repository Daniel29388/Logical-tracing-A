"""Logic-board dashboard Streamlit UI."""

from __future__ import annotations

import sys
import time
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

os.environ.setdefault("TRADINGAGENTS_RESULTS_DIR", str(_PROJECT_ROOT / ".tradingagents" / "logs"))
os.environ.setdefault("TRADINGAGENTS_CACHE_DIR", str(_PROJECT_ROOT / ".tradingagents" / "cache"))

from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.event_driven.boards import ensure_default_boards, load_logic_board  # noqa: E402
from web.components.progress_panel import render_progress  # noqa: E402
from web.components.report_viewer import render_board_dashboard  # noqa: E402
from web.components.sidebar import render_sidebar  # noqa: E402
from web.progress import ProgressTracker  # noqa: E402
from web.runner import run_board_refresh_in_thread  # noqa: E402

st.set_page_config(
    page_title="逻辑板块看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
    #MainMenu, header[data-testid="stHeader"], footer,
    div[data-testid="stDecoration"], div[data-testid="stToolbar"] { display: none !important; }
    button[data-testid="collapsedControl"] { display: flex !important; }
    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    .stApp { background: #0a0a0a; }
    section[data-testid="stSidebar"] { background: #0f0f0f; border-right: 1px solid #1f1f1f; }
    .stMetric label { color: #888 !important; font-size: 0.8rem !important; }
    .stMetric [data-testid="stMetricValue"] { color: #ff5a1f !important; font-weight: 700 !important; }
    .stProgress > div > div > div { background: linear-gradient(90deg, #ff5a1f, #ff8c42) !important; }
    button[kind="primary"] {
        background: #ff5a1f !important;
        border: none !important;
        font-weight: 700 !important;
    }
    button[kind="secondary"] {
        background: #161616 !important;
        border: 1px solid #2a2a2a !important;
        color: #ddd !important;
    }
    .stTabs [aria-selected="true"] { color: #ff5a1f !important; border-bottom-color: #ff5a1f !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _build_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = st.session_state.get("llm_provider", "deepseek")
    config["deep_think_llm"] = st.session_state.get("deep_think_llm", "deepseek-chat")
    config["quick_think_llm"] = st.session_state.get("quick_think_llm", "deepseek-chat")
    config["data_vendors"] = {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    }
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["output_language"] = "Chinese"
    return config


with st.sidebar:
    render_sidebar()

start_req = st.session_state.pop("start_board_refresh", None)
if start_req:
    tracker = ProgressTracker(
        ticker=start_req["board_name"],
        trade_date=start_req["trade_date"],
    )
    st.session_state["tracker"] = tracker
    st.session_state["active_analysis_mode"] = "逻辑板块" if start_req.get("has_stocks") else "板块建池"
    st.session_state["active_board_id"] = start_req["board_id"]
    run_board_refresh_in_thread(
        board_id=start_req["board_id"],
        board_name=start_req["board_name"],
        trade_date=start_req["trade_date"],
        config=_build_config(),
        tracker=tracker,
        has_stocks=start_req.get("has_stocks", True),
    )

tracker: ProgressTracker | None = st.session_state.get("tracker")

if tracker and tracker.is_running:
    render_progress(tracker)
    time.sleep(2)
    st.rerun()
elif tracker and tracker.error:
    st.error(f"分析失败: {tracker.error}")
    if st.button("清除错误"):
        st.session_state.pop("tracker", None)
        st.rerun()
elif tracker and tracker.is_complete:
    board_id = st.session_state.get("active_board_id")
    board = load_logic_board(board_id, DEFAULT_CONFIG["results_dir"]) if board_id else ensure_default_boards(DEFAULT_CONFIG["results_dir"])[0]
    render_board_dashboard(board, tracker.final_state, elapsed=tracker.elapsed)
else:
    boards = ensure_default_boards(DEFAULT_CONFIG["results_dir"])
    selected_board_id = st.session_state.get("selected_board_id")
    selected_board = next((board for board in boards if board.id == selected_board_id), boards[0])
    render_board_dashboard(selected_board)
