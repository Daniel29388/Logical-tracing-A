# TradingAgents/graph/__init__.py

from .trading_graph import TradingAgentsGraph
from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor

__all__ = [
    "TradingAgentsGraph",
    "EventDrivenAgentsGraph",
    "ConditionalLogic",
    "GraphSetup",
    "Propagator",
    "Reflector",
    "SignalProcessor",
]


def __getattr__(name):
    if name == "EventDrivenAgentsGraph":
        from tradingagents.event_driven.graph import EventDrivenAgentsGraph

        return EventDrivenAgentsGraph
    raise AttributeError(name)
