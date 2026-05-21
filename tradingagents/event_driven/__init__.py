from .boards import LogicBoard
from .state import EventDrivenAgentState

__all__ = [
    "EventDrivenAgentState",
    "EventDrivenAgentsGraph",
    "LogicBoard",
]


def __getattr__(name):
    if name == "EventDrivenAgentsGraph":
        from .graph import EventDrivenAgentsGraph

        return EventDrivenAgentsGraph
    raise AttributeError(name)
