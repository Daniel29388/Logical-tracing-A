from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.event_driven.prompts import EventStageSpec
from tradingagents.agents.utils.agent_utils import get_language_instruction


def _format_context(state: dict, context_fields: tuple[str, ...]) -> str:
    sections = []
    for field in context_fields:
        value = state.get(field, "")
        if value:
            sections.append(f"## {field}\n{value}")
    return "\n\n".join(sections) if sections else "暂无上游报告。"


def create_event_stage_agent(llm, spec: EventStageSpec):
    """Create one tool-capable event-driven workflow node."""

    tools = list(spec.tools)

    def event_stage_node(state: dict) -> dict:
        current_date = state["trade_date"]
        seed_query = state["seed_query"]
        upstream_context = _format_context(state, tuple(spec.context_fields))

        system_message = (
            f"你是 `{spec.display_name}`。\n"
            f"{spec.role_prompt}\n\n"
            "工作边界：你只完成当前角色职责，不输出买卖结论。\n"
            "如果数据不足，明确写出 `[数据缺失: xxx]` 和下一步补证方式。\n\n"
            f"输出要求：{spec.output_contract}"
            f"{get_language_instruction()}"
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你正在和其他 A 股事件驱动 Agent 协作。"
                    "请使用可用工具推进当前阶段。"
                    "可用工具：{tool_names}。\n\n"
                    "{system_message}\n\n"
                    "当前日期：{current_date}\n"
                    "用户关注的事件/主题/线索：{seed_query}\n\n"
                    "上游报告：\n{upstream_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]) or "无")
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(seed_query=seed_query)
        prompt = prompt.partial(upstream_context=upstream_context)

        chain = prompt | llm.bind_tools(tools) if tools else prompt | llm
        result = chain.invoke(state["messages"])

        report = ""
        if len(getattr(result, "tool_calls", [])) == 0:
            report = result.content

        return {
            "messages": [result],
            "sender": spec.display_name,
            spec.report_field: report,
        }

    return event_stage_node
