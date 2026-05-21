"""Prompt specifications for the event-driven A-share workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from tradingagents.agents.utils.agent_utils import (
    get_concept_blocks,
    get_dragon_tiger_board,
    get_fund_flow,
    get_fundamentals,
    get_global_news,
    get_hot_stocks,
    get_indicators,
    get_lockup_expiry,
    get_news,
    get_northbound_flow,
    get_stocks_by_keyword,
    get_stock_data,
)


@dataclass(frozen=True)
class EventStageSpec:
    """Configuration for one event-driven workflow stage."""

    key: str
    report_field: str
    display_name: str
    role_prompt: str
    output_contract: str
    context_fields: Sequence[str] = ()
    tools: Sequence = ()


EVENT_STAGE_SPECS = [
    EventStageSpec(
        key="event",
        report_field="event_report",
        display_name="新闻事件 Agent",
        tools=(get_global_news, get_hot_stocks),
        role_prompt=(
            "你负责从新闻、政策、公告、强势股题材和市场传闻中提取未来可能继续发酵的事件。"
            "优先识别未完全兑现、可被资金扩散、能映射到 A 股产业链的事件。"
        ),
        output_contract=(
            "输出 Markdown，必须包含：事件名称、来源/触发信号、发酵阶段、潜在受益链条、"
            "未来 3 个需要验证的观察点。不要给交易建议。"
        ),
    ),
    EventStageSpec(
        key="logic",
        report_field="logic_report",
        display_name="逻辑提炼 Agent",
        context_fields=("event_report",),
        role_prompt=(
            "你负责把事件转成可跟踪的投资逻辑。逻辑必须能被后续数据验证，避免只复述新闻标题。"
        ),
        output_contract=(
            "输出 Markdown，必须按 `事件 -> 传导机制 -> 受益环节 -> 可验证指标 -> 失效条件` 展开。"
            "标注逻辑强度：强/中/弱。"
        ),
    ),
    EventStageSpec(
        key="target",
        report_field="target_report",
        display_name="标的发现 Agent",
        tools=(get_stocks_by_keyword, get_hot_stocks),
        context_fields=("event_report", "logic_report"),
        role_prompt=(
            "你负责根据关键词、产业链、地域、股权、概念板块和强势股题材寻找相关 A 股标的。"
            "必须优先使用 `get_stocks_by_keyword` 反查相关股票池；可以把一个复合逻辑拆成多个关键词分别查询，"
            "例如 `国产存储`、`半导体设备`、`合肥`、`国资`。"
        ),
        output_contract=(
            "输出 Markdown 表格，列出候选标的、关联环节、关联证据、确定性等级、需要补证的数据。"
            "把确定性不足或明显蹭概念的标的单独列为观察。"
        ),
    ),
    EventStageSpec(
        key="selection",
        report_field="selection_report",
        display_name="选股理由 Agent",
        tools=(get_news, get_concept_blocks, get_fundamentals, get_lockup_expiry),
        context_fields=("logic_report", "target_report"),
        role_prompt=(
            "你负责给每个候选标的生成入选理由，并区分强关联、弱关联、蹭概念、风险剔除。"
            "优先使用概念板块、公司新闻、基本面和解禁风险验证关联。"
        ),
        output_contract=(
            "输出 Markdown 表格，包含：代码/名称、关联类型、核心理由、主要风险、入池结论。"
            "入池结论只能是 核心/弹性/观察/剔除。"
        ),
    ),
    EventStageSpec(
        key="block",
        report_field="block_report",
        display_name="逻辑板块 Agent",
        context_fields=("event_report", "logic_report", "selection_report"),
        role_prompt=(
            "你负责把候选标的组织成一个自定义逻辑板块，而不是简单行业板块。"
            "板块必须围绕一个核心事件和可跟踪逻辑命名。"
        ),
        output_contract=(
            "输出 Markdown，包含：板块名称、核心触发事件、核心票、弹性票、观察票、剔除票、"
            "跟踪周期和每日更新字段。"
        ),
    ),
    EventStageSpec(
        key="tracker",
        report_field="tracker_report",
        display_name="逻辑追踪 Agent",
        tools=(get_global_news, get_hot_stocks, get_northbound_flow, get_fund_flow, get_dragon_tiger_board),
        context_fields=("block_report", "selection_report"),
        role_prompt=(
            "你负责对逻辑板块内个股进行近 30 个交易日的实时追踪，更新事件进展、新闻强度、涨跌幅、资金流、龙虎榜和板块扩散情况。"
            "你的重点是判断板块逻辑在升温、扩散、分歧还是退潮。"
        ),
        output_contract=(
            "输出 Markdown 表格，包含：代码/名称、30日涨跌幅状态、近5日状态、资金/龙虎榜信号、新闻催化、跟踪结论、明日观察点。"
        ),
    ),
    EventStageSpec(
        key="technical",
        report_field="technical_report",
        display_name="技术面 Analyst",
        tools=(get_stock_data, get_indicators),
        context_fields=("selection_report", "block_report", "tracker_report"),
        role_prompt=(
            "你负责像原项目 Market Analyst 一样分析趋势、均线、量价、突破、回踩和失效位。"
            "只分析候选池中值得跟踪的标的，无法拿到代码时先给技术验证清单。"
        ),
        output_contract=(
            "输出 Markdown 表格，包含：标的、趋势状态、量价状态、关键支撑/压力、技术评分、失效位。"
        ),
    ),
]


BOARD_REFRESH_STAGE_SPECS = [
    EventStageSpec(
        key="tracker",
        report_field="tracker_report",
        display_name="30日追踪 Agent",
        tools=(get_global_news, get_hot_stocks, get_northbound_flow, get_fund_flow, get_dragon_tiger_board, get_news),
        context_fields=("block_report", "selection_report"),
        role_prompt=(
            "你负责刷新一个已存在的自定义逻辑板块。必须围绕给定股票池，对每只个股做近 30 个交易日追踪，"
            "观察事件热度、新闻催化、涨跌幅、资金流、龙虎榜、是否扩散或退潮。"
        ),
        output_contract=(
            "输出 Markdown 表格，包含：代码/名称、近30日表现、近5日状态、新闻/事件更新、资金/龙虎榜、"
            "板块地位、风险信号、后续观察。不要输出买卖建议。"
        ),
    ),
    EventStageSpec(
        key="technical",
        report_field="technical_report",
        display_name="技术面 Analyst",
        tools=(get_stock_data, get_indicators),
        context_fields=("selection_report", "block_report", "tracker_report"),
        role_prompt=(
            "你负责对板块股票池做技术面看板分析。必须使用给定股票代码，重点看近 30 个交易日趋势、均线、量价、"
            "突破、回踩、支撑压力和失效位。"
        ),
        output_contract=(
            "输出 Markdown 表格，包含：代码/名称、30日趋势、量价结构、均线/动量、关键支撑、关键压力、"
            "技术评分、失效位。不要输出最终买卖决策。"
        ),
    ),
]
