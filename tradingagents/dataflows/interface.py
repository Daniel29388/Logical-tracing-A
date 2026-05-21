from typing import Annotated, Callable

from .alpha_vantage_common import AlphaVantageRateLimitError


def _lazy(module_name: str, func_name: str) -> Callable:
    """Return a callable that imports the vendor function only when used."""

    def _call(*args, **kwargs):
        module = __import__(f"tradingagents.dataflows.{module_name}", fromlist=[func_name])
        return getattr(module, func_name)(*args, **kwargs)

    _call.__name__ = func_name
    return _call

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "signal_data": {
        "description": "A-stock signal layer (topic attribution, capital flow, consensus forecast)",
        "tools": [
            "get_profit_forecast",
            "get_hot_stocks",
            "get_northbound_flow",
            "get_concept_blocks",
            "get_fund_flow",
            "get_dragon_tiger_board",
            "get_lockup_expiry",
            "get_industry_comparison",
            "get_stocks_by_keyword",
        ]
    }
}

VENDOR_LIST = [
    "a_stock",
    "yfinance",
    "alpha_vantage",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "a_stock": _lazy("a_stock", "get_stock_data"),
        "alpha_vantage": _lazy("alpha_vantage", "get_stock"),
        "yfinance": _lazy("y_finance", "get_YFin_data_online"),
    },
    # technical_indicators
    "get_indicators": {
        "a_stock": _lazy("a_stock", "get_indicators"),
        "alpha_vantage": _lazy("alpha_vantage", "get_indicator"),
        "yfinance": _lazy("y_finance", "get_stock_stats_indicators_window"),
    },
    # fundamental_data
    "get_fundamentals": {
        "a_stock": _lazy("a_stock", "get_fundamentals"),
        "alpha_vantage": _lazy("alpha_vantage", "get_fundamentals"),
        "yfinance": _lazy("y_finance", "get_fundamentals"),
    },
    "get_balance_sheet": {
        "a_stock": _lazy("a_stock", "get_balance_sheet"),
        "alpha_vantage": _lazy("alpha_vantage", "get_balance_sheet"),
        "yfinance": _lazy("y_finance", "get_balance_sheet"),
    },
    "get_cashflow": {
        "a_stock": _lazy("a_stock", "get_cashflow"),
        "alpha_vantage": _lazy("alpha_vantage", "get_cashflow"),
        "yfinance": _lazy("y_finance", "get_cashflow"),
    },
    "get_income_statement": {
        "a_stock": _lazy("a_stock", "get_income_statement"),
        "alpha_vantage": _lazy("alpha_vantage", "get_income_statement"),
        "yfinance": _lazy("y_finance", "get_income_statement"),
    },
    # news_data
    "get_news": {
        "a_stock": _lazy("a_stock", "get_news"),
        "alpha_vantage": _lazy("alpha_vantage", "get_news"),
        "yfinance": _lazy("yfinance_news", "get_news_yfinance"),
    },
    "get_global_news": {
        "a_stock": _lazy("a_stock", "get_global_news"),
        "yfinance": _lazy("yfinance_news", "get_global_news_yfinance"),
        "alpha_vantage": _lazy("alpha_vantage", "get_global_news"),
    },
    "get_insider_transactions": {
        "a_stock": _lazy("a_stock", "get_insider_transactions"),
        "alpha_vantage": _lazy("alpha_vantage", "get_insider_transactions"),
        "yfinance": _lazy("y_finance", "get_insider_transactions"),
    },
    # signal_data (A-stock only)
    "get_profit_forecast": {
        "a_stock": _lazy("a_stock", "get_profit_forecast"),
    },
    "get_hot_stocks": {
        "a_stock": _lazy("a_stock", "get_hot_stocks"),
    },
    "get_northbound_flow": {
        "a_stock": _lazy("a_stock", "get_northbound_flow"),
    },
    "get_concept_blocks": {
        "a_stock": _lazy("a_stock", "get_concept_blocks"),
    },
    "get_fund_flow": {
        "a_stock": _lazy("a_stock", "get_fund_flow"),
    },
    "get_dragon_tiger_board": {
        "a_stock": _lazy("a_stock", "get_dragon_tiger_board"),
    },
    "get_lockup_expiry": {
        "a_stock": _lazy("a_stock", "get_lockup_expiry"),
    },
    "get_industry_comparison": {
        "a_stock": _lazy("a_stock", "get_industry_comparison"),
    },
    "get_stocks_by_keyword": {
        "a_stock": _lazy("a_stock", "get_stocks_by_keyword"),
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue  # Only rate limits trigger fallback

    raise RuntimeError(f"No available vendor for '{method}'")
