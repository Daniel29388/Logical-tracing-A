from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
def test_signal_data_category_includes_keyword_lookup():
    from tradingagents.dataflows.interface import TOOLS_CATEGORIES, get_category_for_method

    assert "get_stocks_by_keyword" in TOOLS_CATEGORIES["signal_data"]["tools"]
    assert get_category_for_method("get_stocks_by_keyword") == "signal_data"


@pytest.mark.unit
def test_keyword_lookup_routes_to_astock_vendor(monkeypatch):
    from tradingagents.dataflows import interface

    fake = MagicMock(return_value="# Keyword Stock Pool: 存储芯片")
    monkeypatch.setitem(interface.VENDOR_METHODS["get_stocks_by_keyword"], "a_stock", fake)
    monkeypatch.setattr(
        interface,
        "get_config",
        lambda: {
            "data_vendors": {"signal_data": "a_stock"},
            "tool_vendors": {},
        },
    )

    result = interface.route_to_vendor("get_stocks_by_keyword", "存储芯片", "2026-05-20", 10, 3)

    assert result.startswith("# Keyword Stock Pool")
    fake.assert_called_once_with("存储芯片", "2026-05-20", 10, 3)


@pytest.mark.unit
def test_keyword_lookup_no_keyword_is_error():
    from tradingagents.dataflows.a_stock import get_stocks_by_keyword

    assert get_stocks_by_keyword("") == "Error: keyword cannot be empty"
