from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from tradingagents.agents.utils.agent_utils import (
    get_fund_flow,
    get_hot_stocks,
    get_indicators,
    get_stock_data,
    get_stocks_by_keyword,
)
from tradingagents.event_driven.boards import LogicBoard


def _call_tool(tool, payload: dict[str, Any]) -> str:
    """Invoke a LangChain tool or plain callable and normalize failures."""
    try:
        if hasattr(tool, "invoke"):
            return str(tool.invoke(payload))
        return str(tool(**payload))
    except Exception as exc:
        return f"[数据缺失: {getattr(tool, 'name', repr(tool))}: {type(exc).__name__}: {exc}]"


def _start_date(curr_date: str, calendar_days: int = 60) -> str:
    try:
        dt = datetime.strptime(curr_date, "%Y-%m-%d")
    except ValueError:
        dt = datetime.now()
    return (dt - timedelta(days=calendar_days)).strftime("%Y-%m-%d")


def _seed_keywords(seed_query: str, max_keywords: int = 5) -> list[str]:
    normalized = seed_query.replace("->", "/")
    for sep in ("，", ",", "、", "|", "\n", ";", "；"):
        normalized = normalized.replace(sep, "/")
    candidates = [seed_query.strip()]
    candidates.extend(part.strip(" `#*:-_") for part in normalized.split("/"))

    keywords: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if len(item) < 2 or item in seen:
            continue
        seen.add(item)
        keywords.append(item)
        if len(keywords) >= max_keywords:
            break
    return keywords


def prefetch_seed_discovery_context(
    seed_query: str,
    trade_date: str,
    on_tool_call: Callable[[], None] | None = None,
    max_keywords: int = 5,
) -> str:
    """Force keyword/hot-stock discovery before the build agents run."""
    sections: list[str] = [
        "# 强制工具候选发现",
        f"主题: {seed_query}",
        f"日期: {trade_date}",
    ]

    def run(tool, payload: dict[str, Any]) -> str:
        if on_tool_call:
            on_tool_call()
        return _call_tool(tool, payload)

    for keyword in _seed_keywords(seed_query, max_keywords=max_keywords):
        sections.extend(
            [
                "",
                f"## 关键词反查: {keyword}",
                run(
                    get_stocks_by_keyword,
                    {
                        "keyword": keyword,
                        "curr_date": trade_date,
                        "top_n": 25,
                        "max_blocks": 4,
                    },
                )[:6000],
            ]
        )

    sections.extend(
        [
            "",
            "## 当日强势股线索",
            run(get_hot_stocks, {"curr_date": trade_date})[:6000],
        ]
    )

    return "\n".join(sections)


def prefetch_board_tool_context(
    board: LogicBoard,
    trade_date: str,
    on_tool_call: Callable[[], None] | None = None,
    max_stocks: int = 12,
) -> str:
    """Fetch deterministic board data before the LLM writes a tracking report."""
    sections: list[str] = [
        f"# 工具预取数据",
        f"板块: {board.name}",
        f"日期: {trade_date}",
        f"窗口: 近 {board.tracking_days} 个交易日",
    ]
    start = _start_date(trade_date)

    def run(tool, payload: dict[str, Any]) -> str:
        if on_tool_call:
            on_tool_call()
        return _call_tool(tool, payload)

    for stock in board.stocks[:max_stocks]:
        sections.extend(
            [
                "",
                f"## {stock.code} {stock.name}",
                "",
                "### 近30日行情",
                run(get_stock_data, {"symbol": stock.code, "start_date": start, "end_date": trade_date})[:5000],
                "",
                "### 技术指标",
                run(
                    get_indicators,
                    {
                        "symbol": stock.code,
                        "indicator": "rsi,macd,boll,close_50_sma",
                        "curr_date": trade_date,
                        "look_back_days": board.tracking_days,
                    },
                )[:5000],
                "",
                "### 资金流",
                run(get_fund_flow, {"ticker": stock.code, "curr_date": trade_date, "include_history": True})[:2500],
            ]
        )

    return "\n".join(sections)
