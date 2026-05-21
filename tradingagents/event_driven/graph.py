from __future__ import annotations

import json
import os
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents.event_driven import create_event_stage_agent
from tradingagents.agents.event_driven.prompts import BOARD_REFRESH_STAGE_SPECS, EVENT_STAGE_SPECS
from tradingagents.agents.utils.agent_utils import create_msg_delete
from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.event_driven.boards import LogicBoard, build_board_from_state, save_logic_board
from tradingagents.event_driven.state import EventDrivenAgentState
from tradingagents.event_driven.stock_pool import extract_stock_candidates, render_candidate_table
from tradingagents.llm_clients import create_llm_client

EVENT_REPORT_FIELDS = [
    "event_report",
    "logic_report",
    "target_report",
    "selection_report",
    "block_report",
    "tracker_report",
    "technical_report",
]


class EventDrivenAgentsGraph:
    """Lightweight event-driven multi-agent workflow for A-share discovery."""

    def __init__(
        self,
        debug: bool = False,
        config: Optional[Dict[str, Any]] = None,
        callbacks: Optional[list] = None,
    ):
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []
        set_config(self.config)

        os.makedirs(self.config["data_cache_dir"], exist_ok=True)
        os.makedirs(self.config["results_dir"], exist_ok=True)

        llm_kwargs = self._get_provider_kwargs()
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.quick_llm = quick_client.get_llm()
        self.deep_llm = deep_client.get_llm()
        self.workflow = self._setup_graph()
        self.graph = self.workflow.compile()
        self.refresh_workflow = self._setup_refresh_graph()
        self.refresh_graph = self.refresh_workflow.compile()
        self.curr_state = None

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()
        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level
        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort
        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort
        return kwargs

    def _setup_graph(self):
        workflow = StateGraph(EventDrivenAgentState)

        clear_messages = create_msg_delete()
        previous_node = START

        for spec in EVENT_STAGE_SPECS:
            agent_node = spec.display_name
            clear_node = f"Msg Clear {spec.key}"
            workflow.add_node(agent_node, create_event_stage_agent(self.quick_llm, spec))
            workflow.add_node(clear_node, clear_messages)

            if spec.tools:
                tools_node = f"tools_{spec.key}"
                workflow.add_node(tools_node, ToolNode(list(spec.tools)))
                workflow.add_conditional_edges(
                    agent_node,
                    self._should_continue(agent_node, tools_node, clear_node),
                    [tools_node, clear_node],
                )
                workflow.add_edge(tools_node, agent_node)
            else:
                workflow.add_edge(agent_node, clear_node)

            workflow.add_edge(previous_node, agent_node)
            previous_node = clear_node

        workflow.add_edge(previous_node, END)
        return workflow

    def _setup_refresh_graph(self):
        workflow = StateGraph(EventDrivenAgentState)

        clear_messages = create_msg_delete()
        previous_node = START

        for spec in BOARD_REFRESH_STAGE_SPECS:
            agent_node = spec.display_name
            clear_node = f"Msg Clear refresh {spec.key}"
            workflow.add_node(agent_node, create_event_stage_agent(self.quick_llm, spec))
            workflow.add_node(clear_node, clear_messages)

            if spec.tools:
                tools_node = f"tools_refresh_{spec.key}"
                workflow.add_node(tools_node, ToolNode(list(spec.tools)))
                workflow.add_conditional_edges(
                    agent_node,
                    self._should_continue(agent_node, tools_node, clear_node),
                    [tools_node, clear_node],
                )
                workflow.add_edge(tools_node, agent_node)
            else:
                workflow.add_edge(agent_node, clear_node)

            workflow.add_edge(previous_node, agent_node)
            previous_node = clear_node

        workflow.add_edge(previous_node, END)
        return workflow

    @staticmethod
    def _should_continue(agent_node: str, tools_node: str, clear_node: str):
        def should_continue(state: EventDrivenAgentState) -> str:
            messages = state["messages"]
            last_message = messages[-1]
            if getattr(last_message, "tool_calls", []):
                return tools_node
            return clear_node

        should_continue.__name__ = f"should_continue_{agent_node}"
        return should_continue

    def create_initial_state(
        self,
        seed_query: str,
        trade_date: str,
        discovery_context: str = "",
    ) -> Dict[str, Any]:
        tool_section = f"\n\n已预取的候选发现工具数据:\n{discovery_context}" if discovery_context else ""
        return {
            "messages": [HumanMessage(content=f"{seed_query}{tool_section}")],
            "seed_query": seed_query,
            "trade_date": str(trade_date),
            "sender": "User",
            "event_report": "",
            "logic_report": "",
            "target_report": "",
            "selection_report": "",
            "block_report": "",
            "tracker_report": "",
            "technical_report": "",
        }

    def create_board_refresh_state(
        self,
        board: LogicBoard,
        trade_date: str,
        tool_context: str = "",
    ) -> Dict[str, Any]:
        stock_pool = render_candidate_table(board.stocks)
        seed_query = f"刷新逻辑板块：{board.name}"
        tool_section = f"\n\n已预取的实时工具数据：\n{tool_context}" if tool_context else ""
        return {
            "messages": [
                HumanMessage(
                    content=(
                        f"请刷新逻辑板块 `{board.name}`，交易日期 {trade_date}，固定追踪窗口为近 {board.tracking_days} 个交易日。\n\n"
                        f"股票池：\n{stock_pool}\n\n"
                        "不要新增最终决策，只输出追踪和技术看板。"
                        f"{tool_section}"
                    )
                )
            ],
            "seed_query": seed_query,
            "trade_date": str(trade_date),
            "sender": "User",
            "event_report": board.source_event,
            "logic_report": "",
            "target_report": stock_pool,
            "selection_report": board.selection_report or stock_pool,
            "block_report": board.block_report or f"## {board.name}\n\n{stock_pool}",
            "tracker_report": "",
            "technical_report": "",
        }

    def run(self, seed_query: str, trade_date: str) -> tuple[dict, str]:
        init_state = self.create_initial_state(seed_query, trade_date)
        args = {
            "stream_mode": "values",
            "config": {
                "recursion_limit": self.config.get("max_recur_limit", 100),
            },
        }

        if self.debug:
            trace = []
            for chunk in self.graph.stream(init_state, **args):
                trace.append(chunk)
            final_state = trace[-1]
        else:
            final_state = self.graph.invoke(init_state, **args)

        self.curr_state = final_state
        self._log_state(seed_query, trade_date, final_state)
        board = build_board_from_state(final_state, seed_query, trade_date)
        save_logic_board(board, self.config["results_dir"])
        return final_state, final_state.get("technical_report", "")

    def refresh_board(self, board: LogicBoard, trade_date: str) -> tuple[dict, str]:
        init_state = self.create_board_refresh_state(board, trade_date)
        args = {
            "stream_mode": "values",
            "config": {
                "recursion_limit": self.config.get("max_recur_limit", 100),
            },
        }

        if self.debug:
            trace = []
            for chunk in self.refresh_graph.stream(init_state, **args):
                trace.append(chunk)
            final_state = trace[-1]
        else:
            final_state = self.refresh_graph.invoke(init_state, **args)

        self.curr_state = final_state
        board.last_trade_date = trade_date
        board.tracker_report = final_state.get("tracker_report", "")
        board.technical_report = final_state.get("technical_report", "")
        save_logic_board(board, self.config["results_dir"])
        return final_state, final_state.get("technical_report", "")

    def _log_state(self, seed_query: str, trade_date: str, final_state: dict) -> None:
        directory = event_result_dir(self.config["results_dir"], seed_query)
        log_path = directory / f"event_driven_state_{trade_date}.json"
        payload = event_state_payload(seed_query, trade_date, final_state)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


def safe_event_slug(seed_query: str, max_len: int = 48) -> str:
    """Create a filesystem-safe slug for an event query."""
    safe_name = "".join(
        ch if ch.isascii() and (ch.isalnum() or ch in "._-") else "_"
        for ch in seed_query
    ).strip("._-")
    digest = sha1(seed_query.encode("utf-8")).hexdigest()[:8]
    prefix = (safe_name[: max_len - 9].strip("._-") or "event")
    return f"{prefix}-{digest}"


def event_result_dir(results_dir: str, seed_query: str) -> Path:
    directory = Path(results_dir) / "event_driven" / safe_event_slug(seed_query)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def event_state_payload(seed_query: str, trade_date: str, final_state: dict) -> dict:
    payload = {
        "seed_query": seed_query,
        "trade_date": trade_date,
    }
    for field in EVENT_REPORT_FIELDS:
        payload[field] = final_state.get(field, "")
    return payload


def render_event_report_markdown(final_state: dict) -> str:
    """Render all event-driven stage reports into one markdown document."""
    sections = [
        ("新闻事件 Agent", "event_report"),
        ("逻辑提炼 Agent", "logic_report"),
        ("标的发现 Agent", "target_report"),
        ("选股理由 Agent", "selection_report"),
        ("逻辑板块 Agent", "block_report"),
        ("逻辑追踪 Agent", "tracker_report"),
        ("技术面 Analyst", "technical_report"),
    ]
    parts = [
        f"# 事件驱动多 Agent 报告: {final_state.get('seed_query', '')}",
        "",
        f"分析日期: {final_state.get('trade_date', '')}",
    ]
    for title, field in sections:
        content = final_state.get(field, "")
        if content:
            parts.extend(["", f"## {title}", "", str(content)])
    return "\n".join(parts).strip() + "\n"


def save_event_artifacts(final_state: dict, results_dir: str, seed_query: str, trade_date: str) -> dict[str, Path]:
    """Save event-driven state, markdown report, and reusable block profile."""
    directory = event_result_dir(results_dir, seed_query)
    payload = event_state_payload(seed_query, trade_date, final_state)

    state_path = directory / f"event_driven_state_{trade_date}.json"
    report_path = directory / f"event_driven_report_{trade_date}.md"
    block_path = directory / "logic_block.json"

    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_event_report_markdown(final_state), encoding="utf-8")
    block_path.write_text(
        json.dumps(
            {
                "seed_query": seed_query,
                "last_trade_date": trade_date,
                "block_report": final_state.get("block_report", ""),
                "selection_report": final_state.get("selection_report", ""),
                "tracker_report": final_state.get("tracker_report", ""),
                "technical_report": final_state.get("technical_report", ""),
                "stocks": [
                    {
                        "code": item.code,
                        "name": item.name,
                        "source": item.source,
                    }
                    for item in extract_stock_candidates(
                        "\n\n".join(
                            [
                                str(final_state.get("selection_report", "")),
                                str(final_state.get("block_report", "")),
                                str(final_state.get("target_report", "")),
                            ]
                        ),
                        "event_report",
                    )
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "directory": directory,
        "state": state_path,
        "report": report_path,
        "block": block_path,
    }
