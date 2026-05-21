"""Background thread runner for TradingAgentsGraph pipeline."""

from __future__ import annotations

import re
import threading
from typing import Any

from web.progress import (
    BOARD_BUILD_STAGE_IDS,
    BOARD_BUILD_STAGES,
    BOARD_REFRESH_STAGE_IDS,
    BOARD_REFRESH_STAGES,
    EVENT_PIPELINE_STAGES,
    EVENT_STAGE_IDS,
    PIPELINE_STAGES,
    ProgressTracker,
)


_REPORT_KEY_TO_STAGE = {s["report_key"]: s["id"] for s in PIPELINE_STAGES}
_EVENT_REPORT_KEY_TO_STAGE = {s["report_key"]: s["id"] for s in EVENT_PIPELINE_STAGES}
_BOARD_REPORT_KEY_TO_STAGE = {s["report_key"]: s["id"] for s in BOARD_REFRESH_STAGES}
_BOARD_BUILD_REPORT_KEY_TO_STAGE = {s["report_key"]: s["id"] for s in BOARD_BUILD_STAGES}

_ANALYST_REPORT_KEYS = [
    "market_report", "sentiment_report", "news_report",
    "fundamentals_report", "policy_report", "hot_money_report", "lockup_report",
]


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from LLM output."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def _detect_completed_stages(
    chunk: dict[str, Any],
    tracker: ProgressTracker,
) -> None:
    """Check the streamed chunk for newly completed stages."""
    for report_key in _ANALYST_REPORT_KEYS:
        stage_id = _REPORT_KEY_TO_STAGE[report_key]
        content = chunk.get(report_key, "")
        if content and tracker.stage_status(stage_id) != "done":
            tracker.mark_stage_done(stage_id, _strip_think_tags(str(content)))

    dqs = chunk.get("data_quality_summary", "")
    if dqs and tracker.stage_status("quality_gate") != "done":
        tracker.mark_stage_done("quality_gate", str(dqs))

    debate = chunk.get("investment_debate_state")
    if debate and isinstance(debate, dict):
        judge = debate.get("judge_decision", "")
        if judge and tracker.stage_status("debate") != "done":
            tracker.mark_stage_done("debate", str(judge))

    trader_plan = chunk.get("trader_investment_plan", "")
    if trader_plan and tracker.stage_status("trader") != "done":
        tracker.mark_stage_done("trader", _strip_think_tags(str(trader_plan)))

    risk = chunk.get("risk_debate_state")
    if risk and isinstance(risk, dict):
        risk_judge = risk.get("judge_decision", "")
        if risk_judge and tracker.stage_status("risk") != "done":
            tracker.mark_stage_done("risk", str(risk_judge))

    final = chunk.get("final_trade_decision", "")
    if final and tracker.stage_status("pm") != "done":
        tracker.mark_stage_done("pm", _strip_think_tags(str(final)))


def _infer_active_stage(tracker: ProgressTracker) -> None:
    """Set the current_stage to the first non-completed stage."""
    from web.progress import STAGE_IDS
    for sid in STAGE_IDS:
        if tracker.stage_status(sid) == "pending":
            tracker.mark_stage_active(sid)
            return


def _run(ticker: str, trade_date: str, config: dict, tracker: ProgressTracker) -> None:
    """Execute the full pipeline in the current thread."""
    from cli.stats_handler import StatsCallbackHandler
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    stats = StatsCallbackHandler()

    graph = TradingAgentsGraph(
        debug=True,
        config=config,
        callbacks=[stats],
    )

    init_state = graph.propagator.create_initial_state(ticker, trade_date)
    args = graph.propagator.get_graph_args(callbacks=[stats])

    last_chunk: dict[str, Any] = {}

    for chunk in graph.graph.stream(init_state, **args):
        last_chunk = chunk
        _detect_completed_stages(chunk, tracker)
        _infer_active_stage(tracker)

        s = stats.get_stats()
        tracker.update_stats(s["llm_calls"], s["tool_calls"], s["tokens_in"], s["tokens_out"])

    signal = graph.process_signal(last_chunk.get("final_trade_decision", ""))

    graph.ticker = ticker
    graph._log_state(trade_date, last_chunk)

    tracker.mark_complete(last_chunk, signal)


def run_analysis_in_thread(
    ticker: str,
    trade_date: str,
    config: dict,
    tracker: ProgressTracker,
) -> threading.Thread:
    """Launch the pipeline in a daemon thread. Returns the thread handle."""
    tracker.ticker = ticker
    tracker.trade_date = trade_date
    tracker.is_running = True
    tracker.mark_stage_active("market")

    def _target() -> None:
        try:
            _run(ticker, trade_date, config, tracker)
        except Exception as exc:
            tracker.mark_error(str(exc))

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t


def _detect_completed_event_stages(chunk: dict[str, Any], tracker: ProgressTracker) -> None:
    for report_key, stage_id in _EVENT_REPORT_KEY_TO_STAGE.items():
        content = chunk.get(report_key, "")
        if content and tracker.stage_status(stage_id) != "done":
            tracker.mark_stage_done(stage_id, _strip_think_tags(str(content)))


def _infer_active_event_stage(tracker: ProgressTracker) -> None:
    for sid in EVENT_STAGE_IDS:
        if tracker.stage_status(sid) == "pending":
            tracker.mark_stage_active(sid)
            return


def _detect_completed_board_stages(chunk: dict[str, Any], tracker: ProgressTracker) -> None:
    for report_key, stage_id in _BOARD_REPORT_KEY_TO_STAGE.items():
        content = chunk.get(report_key, "")
        if content and tracker.stage_status(stage_id) != "done":
            tracker.mark_stage_done(stage_id, _strip_think_tags(str(content)))


def _detect_completed_build_stages(chunk: dict[str, Any], tracker: ProgressTracker) -> None:
    for report_key, stage_id in _BOARD_BUILD_REPORT_KEY_TO_STAGE.items():
        content = chunk.get(report_key, "")
        if content and tracker.stage_status(stage_id) != "done":
            tracker.mark_stage_done(stage_id, _strip_think_tags(str(content)))


def _infer_active_board_stage(tracker: ProgressTracker) -> None:
    for sid in BOARD_REFRESH_STAGE_IDS:
        if tracker.stage_status(sid) == "pending":
            tracker.mark_stage_active(sid)
            return


def _infer_active_build_stage(tracker: ProgressTracker) -> None:
    for sid in BOARD_BUILD_STAGE_IDS:
        if tracker.stage_status(sid) == "pending":
            tracker.mark_stage_active(sid)
            return


def _run_event(seed: str, trade_date: str, config: dict, tracker: ProgressTracker) -> None:
    from cli.stats_handler import StatsCallbackHandler
    from tradingagents.event_driven.graph import EventDrivenAgentsGraph, save_event_artifacts

    stats = StatsCallbackHandler()
    graph = EventDrivenAgentsGraph(
        debug=True,
        config=config,
        callbacks=[stats],
    )
    init_state = graph.create_initial_state(seed, trade_date)
    args = {
        "stream_mode": "values",
        "config": {"recursion_limit": config.get("max_recur_limit", 100)},
    }

    last_chunk: dict[str, Any] = {}
    for chunk in graph.graph.stream(init_state, **args):
        last_chunk = chunk
        _detect_completed_event_stages(chunk, tracker)
        _infer_active_event_stage(tracker)
        s = stats.get_stats()
        tracker.update_stats(s["llm_calls"], s["tool_calls"], s["tokens_in"], s["tokens_out"])

    graph.curr_state = last_chunk
    graph._log_state(seed, trade_date, last_chunk)
    save_event_artifacts(last_chunk, config["results_dir"], seed, trade_date)
    tracker.mark_complete(last_chunk, last_chunk.get("technical_report", ""))


def run_event_analysis_in_thread(
    seed: str,
    trade_date: str,
    config: dict,
    tracker: ProgressTracker,
) -> threading.Thread:
    """Launch the event-driven pipeline in a daemon thread."""
    tracker.ticker = seed
    tracker.trade_date = trade_date
    tracker.is_running = True
    tracker.mark_stage_active("event")

    def _target() -> None:
        try:
            _run_event(seed, trade_date, config, tracker)
        except Exception as exc:
            tracker.mark_error(str(exc))

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t


def _run_board_refresh(board_id: str, trade_date: str, config: dict, tracker: ProgressTracker) -> None:
    from cli.stats_handler import StatsCallbackHandler
    from tradingagents.event_driven.boards import load_logic_board, save_logic_board, update_board_from_state
    from tradingagents.event_driven.graph import EventDrivenAgentsGraph
    from tradingagents.event_driven.tool_prefetch import (
        prefetch_board_tool_context,
        prefetch_seed_discovery_context,
    )

    stats = StatsCallbackHandler()
    prefetch_tool_calls = 0

    def count_prefetch_tool() -> None:
        nonlocal prefetch_tool_calls
        prefetch_tool_calls += 1
        tracker.increment_tool_calls()

    board = load_logic_board(board_id, config["results_dir"])
    graph = EventDrivenAgentsGraph(
        debug=True,
        config=config,
        callbacks=[stats],
    )

    if not board.stocks:
        tracker.mark_stage_active("discovery_prefetch")
        discovery_context = prefetch_seed_discovery_context(
            board.seed_query,
            trade_date,
            on_tool_call=count_prefetch_tool,
        )
        tracker.mark_stage_done("discovery_prefetch", "已完成关键词反查和强势股候选发现。")

        init_state = graph.create_initial_state(
            board.seed_query,
            trade_date,
            discovery_context=discovery_context,
        )
        args = {
            "stream_mode": "values",
            "config": {"recursion_limit": config.get("max_recur_limit", 100)},
        }

        build_chunk: dict[str, Any] = {}
        for chunk in graph.graph.stream(init_state, **args):
            build_chunk = chunk
            _detect_completed_build_stages(chunk, tracker)
            _infer_active_build_stage(tracker)
            s = stats.get_stats()
            tracker.update_stats(
                s["llm_calls"],
                prefetch_tool_calls + s["tool_calls"],
                s["tokens_in"],
                s["tokens_out"],
            )

        board = update_board_from_state(board, build_chunk, trade_date)
        save_logic_board(board, config["results_dir"])
        if not board.stocks:
            graph.curr_state = build_chunk
            tracker.mark_complete(build_chunk, build_chunk.get("technical_report", ""))
            return

        tracker.mark_stage_active("prefetch")
        tool_context = prefetch_board_tool_context(
            board,
            trade_date,
            on_tool_call=count_prefetch_tool,
        )
        tracker.mark_stage_done("prefetch", f"已抓取 {len(board.stocks)} 只股票的行情、指标与资金数据。")
        init_state = graph.create_board_refresh_state(board, trade_date, tool_context=tool_context)
        active_graph = graph.refresh_graph
        stage_detector = _detect_completed_board_stages
        stage_inferer = _infer_active_board_stage
    else:
        tracker.mark_stage_active("prefetch")
        tool_context = prefetch_board_tool_context(
            board,
            trade_date,
            on_tool_call=count_prefetch_tool,
        )
        tracker.mark_stage_done("prefetch", f"已抓取 {len(board.stocks)} 只股票的行情、指标与资金数据。")
        init_state = graph.create_board_refresh_state(board, trade_date, tool_context=tool_context)
        active_graph = graph.refresh_graph
        stage_detector = _detect_completed_board_stages
        stage_inferer = _infer_active_board_stage

    args = {
        "stream_mode": "values",
        "config": {"recursion_limit": config.get("max_recur_limit", 100)},
    }

    last_chunk: dict[str, Any] = {}
    for chunk in active_graph.stream(init_state, **args):
        last_chunk = chunk
        stage_detector(chunk, tracker)
        stage_inferer(tracker)
        s = stats.get_stats()
        tracker.update_stats(
            s["llm_calls"],
            prefetch_tool_calls + s["tool_calls"],
            s["tokens_in"],
            s["tokens_out"],
        )

    graph.curr_state = last_chunk
    board.last_trade_date = trade_date
    board.tracker_report = last_chunk.get("tracker_report", "") or board.tracker_report
    board.technical_report = last_chunk.get("technical_report", "") or board.technical_report
    save_logic_board(board, config["results_dir"])

    tracker.mark_complete(last_chunk, last_chunk.get("technical_report", ""))


def run_board_refresh_in_thread(
    board_id: str,
    board_name: str,
    trade_date: str,
    config: dict,
    tracker: ProgressTracker,
    has_stocks: bool = True,
) -> threading.Thread:
    """Refresh one logic board in a daemon thread."""
    tracker.ticker = board_name
    tracker.trade_date = trade_date
    tracker.is_running = True
    tracker.mark_stage_active("prefetch" if has_stocks else "discovery_prefetch")

    def _target() -> None:
        try:
            _run_board_refresh(board_id, trade_date, config, tracker)
        except Exception as exc:
            tracker.mark_error(str(exc))

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t
