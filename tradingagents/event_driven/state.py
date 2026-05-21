from typing import Annotated

from langgraph.graph import MessagesState


class EventDrivenAgentState(MessagesState):
    """State for the event-driven stock discovery workflow."""

    seed_query: Annotated[str, "User supplied event, theme, rumor, or tracking query"]
    trade_date: Annotated[str, "Analysis date in YYYY-MM-DD format"]
    sender: Annotated[str, "Agent that produced the latest message"]

    event_report: Annotated[str, "Potentially fermenting events extracted from news and market signals"]
    logic_report: Annotated[str, "Traceable event logic chains"]
    target_report: Annotated[str, "Candidate A-share targets related to the logic chains"]
    selection_report: Annotated[str, "Per-target selection rationale and association strength"]
    block_report: Annotated[str, "Custom logical block definition and tracking plan"]
    tracker_report: Annotated[str, "Daily progress tracking for the custom logical block"]
    technical_report: Annotated[str, "Technical analysis for candidate targets"]
