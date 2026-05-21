from unittest.mock import MagicMock

import pytest

from tradingagents.event_driven.graph import EventDrivenAgentsGraph
from tradingagents.event_driven.graph import save_event_artifacts
from tradingagents.event_driven.boards import (
    LogicBoard,
    build_board_from_state,
    load_logic_board,
    save_logic_board,
    update_board_from_state,
)
from tradingagents.event_driven.stock_pool import StockCandidate, extract_stock_candidates, render_candidate_table


@pytest.mark.unit
def test_build_board_from_state_extracts_stock_pool():
    state = {
        "block_report": "## 国产存储链",
        "selection_report": "| 结论 | 代码 | 名称 |\n|---|---|---|\n| 核心 | 688012 | 中微公司 |",
        "target_report": "",
    }

    board = build_board_from_state(state, "长鑫存储 IPO", "2026-05-20")

    assert board.name == "国产存储链"
    assert [(s.code, s.name) for s in board.stocks] == [("688012", "中微公司")]


@pytest.mark.unit
def test_event_driven_graph_builds_with_mock_llm(monkeypatch, tmp_path):
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.with_structured_output.return_value = llm

    client = MagicMock()
    client.get_llm.return_value = llm
    monkeypatch.setattr(
        "tradingagents.event_driven.graph.create_llm_client",
        MagicMock(return_value=client),
    )

    config = {
        "data_cache_dir": str(tmp_path / "cache"),
        "results_dir": str(tmp_path / "results"),
        "llm_provider": "openai",
        "quick_think_llm": "mock-quick",
        "deep_think_llm": "mock-deep",
        "backend_url": None,
        "max_recur_limit": 100,
        "output_language": "Chinese",
        "data_vendors": {
            "core_stock_apis": "a_stock",
            "technical_indicators": "a_stock",
            "fundamental_data": "a_stock",
            "news_data": "a_stock",
            "signal_data": "a_stock",
        },
        "tool_vendors": {},
    }

    graph = EventDrivenAgentsGraph(config=config)

    assert graph.graph is not None
    assert graph.create_initial_state("长鑫存储 IPO", "2026-05-20")["event_report"] == ""


@pytest.mark.unit
def test_save_event_artifacts(tmp_path):
    final_state = {
        "seed_query": "长鑫存储 IPO",
        "trade_date": "2026-05-20",
        "block_report": "## 国产存储链",
        "selection_report": "| 代码 | 名称 |\n|---|---|\n| 688012 | 中微公司 |",
    }

    paths = save_event_artifacts(final_state, str(tmp_path), "长鑫存储 IPO", "2026-05-20")

    assert paths["state"].exists()
    assert paths["report"].exists()
    assert paths["block"].exists()
    assert "国产存储链" in paths["report"].read_text(encoding="utf-8")


@pytest.mark.unit
def test_extract_stock_candidates_from_keyword_pool_table():
    text = """
| 排名 | 代码 | 名称 | 涨跌幅 | 入池依据 |
|---:|---|---|---:|---|
| 1 | 688012 | 中微公司 | 2.3 | 半导体设备 成分股 |
| 2 | 300604 | 长川科技 | 1.1 | 半导体设备 成分股 |
"""

    candidates = extract_stock_candidates(text, source="半导体设备")

    assert [c.code for c in candidates] == ["688012", "300604"]
    assert "中微公司" in render_candidate_table(candidates)


@pytest.mark.unit
def test_extract_stock_candidates_from_code_name_same_cell():
    text = """
| 个股 | 关联强度 | 理由 |
|---|---|---|
| **002405 四维图新** | 强关联 | 高精地图与智驾数据 |
"""

    candidates = extract_stock_candidates(text, source="selection_report")

    assert [(c.code, c.name) for c in candidates] == [("002405", "四维图新")]


@pytest.mark.unit
def test_update_board_from_state_preserves_existing_board_name():
    board = LogicBoard(
        id="FSD-49d1c452",
        name="FSD入华",
        seed_query="FSD入华",
    )

    updated = update_board_from_state(
        board,
        {
            "block_report": "好的，收到上述所有报告。\n\n## 逻辑板块: LLM新名字",
            "selection_report": "| 个股 | 理由 |\n|---|---|\n| 002920 德赛西威 | 智驾域控 |",
        },
        "2026-05-20",
    )

    assert updated.id == "FSD-49d1c452"
    assert updated.name == "FSD入华"
    assert [(s.code, s.name) for s in updated.stocks] == [("002920", "德赛西威")]


@pytest.mark.unit
def test_load_logic_board_coerces_null_fields(tmp_path):
    root = tmp_path / "logic_boards"
    root.mkdir()
    (root / "dirty.json").write_text(
        '{"id":"dirty","name":null,"seed_query":null,"stocks":null,'
        '"last_trade_date":null,"tracking_days":null}',
        encoding="utf-8",
    )

    board = load_logic_board("dirty", str(tmp_path))

    assert board.stocks == []
    assert board.name == ""
    assert board.seed_query == ""
    assert board.tracking_days == 30


@pytest.mark.unit
def test_save_logic_board_backfills_build_reports(tmp_path):
    board = LogicBoard(
        id="board",
        name="长鑫存储上市",
        seed_query="长鑫存储上市 -> 国产存储",
        stocks=[StockCandidate("603986", "兆易创新", "默认板块")],
    )

    save_logic_board(board, str(tmp_path))
    loaded = load_logic_board("board", str(tmp_path))

    assert "## 长鑫存储上市" in loaded.block_report
    assert "| 603986 | 兆易创新 | 默认板块 |" in loaded.selection_report
