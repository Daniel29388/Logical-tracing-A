from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from hashlib import sha1
from pathlib import Path
from typing import Any

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.event_driven.stock_pool import (
    StockCandidate,
    extract_stock_candidates,
    merge_stock_candidates,
    render_candidate_table,
)


@dataclass
class LogicBoard:
    id: str
    name: str
    seed_query: str
    stocks: list[StockCandidate] = field(default_factory=list)
    source_event: str = ""
    tracking_days: int = 30
    last_trade_date: str = ""
    block_report: str = ""
    selection_report: str = ""
    tracker_report: str = ""
    technical_report: str = ""
    updated_at: str = ""


def boards_root(results_dir: str | None = None) -> Path:
    root = Path(results_dir or DEFAULT_CONFIG["results_dir"]) / "logic_boards"
    root.mkdir(parents=True, exist_ok=True)
    return root


def board_path(board_id: str, results_dir: str | None = None) -> Path:
    return boards_root(results_dir) / f"{board_id}.json"


def _safe_slug(text: str, max_len: int = 56) -> str:
    normalized = re.sub(r"\s+", "_", text.strip())
    safe_name = "".join(
        ch if ch.isascii() and (ch.isalnum() or ch in "._-") else "_"
        for ch in normalized
    ).strip("._-")
    digest = sha1(text.encode("utf-8")).hexdigest()[:8]
    prefix = (safe_name[: max_len - 9].strip("._-") or "board")
    return f"{prefix}-{digest}"


def board_id_from_name(name: str) -> str:
    return _safe_slug(name, max_len=56)


def _candidate_to_dict(item: StockCandidate) -> dict[str, str]:
    return asdict(item)


def _candidate_from_dict(raw: dict[str, Any]) -> StockCandidate:
    return StockCandidate(
        code=str(raw.get("code", "")).strip(),
        name=str(raw.get("name", "")).strip(),
        source=str(raw.get("source", "")).strip(),
    )


def _coerce_text(value: Any) -> str:
    return "" if value is None else str(value)


def _normalize_board_payload(raw: dict[str, Any]) -> dict[str, Any]:
    stocks = raw.get("stocks") or []
    raw["stocks"] = [
        _candidate_from_dict(item)
        for item in stocks
        if isinstance(item, dict)
    ]
    for key in (
        "name",
        "seed_query",
        "source_event",
        "last_trade_date",
        "block_report",
        "selection_report",
        "tracker_report",
        "technical_report",
        "updated_at",
    ):
        raw[key] = _coerce_text(raw.get(key, ""))
    raw["tracking_days"] = int(raw.get("tracking_days") or 30)
    return raw


def save_logic_board(board: LogicBoard, results_dir: str | None = None) -> Path:
    ensure_board_build_reports(board)
    path = board_path(board.id, results_dir)
    path.write_text(
        json.dumps(
            {
                **asdict(board),
                "stocks": [_candidate_to_dict(item) for item in board.stocks],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def load_logic_board(board_id: str, results_dir: str | None = None) -> LogicBoard:
    raw = json.loads(board_path(board_id, results_dir).read_text(encoding="utf-8"))
    return ensure_board_build_reports(LogicBoard(**_normalize_board_payload(raw)))


def list_logic_boards(results_dir: str | None = None) -> list[LogicBoard]:
    boards: list[LogicBoard] = []
    for path in sorted(boards_root(results_dir).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            boards.append(ensure_board_build_reports(LogicBoard(**_normalize_board_payload(raw))))
        except Exception:
            continue
    return boards


def build_board_from_state(
    final_state: dict[str, Any],
    seed_query: str,
    trade_date: str,
    board_id: str | None = None,
    board_name: str | None = None,
) -> LogicBoard:
    block_report = str(final_state.get("block_report", ""))
    selection_report = str(final_state.get("selection_report", ""))
    target_report = str(final_state.get("target_report", ""))

    stocks = merge_stock_candidates(
        extract_stock_candidates(selection_report, "selection_report"),
        extract_stock_candidates(block_report, "block_report"),
        extract_stock_candidates(target_report, "target_report"),
    )
    name = board_name or infer_board_name(block_report, seed_query)
    return LogicBoard(
        id=board_id or board_id_from_name(name),
        name=name,
        seed_query=seed_query,
        stocks=stocks,
        source_event=seed_query,
        tracking_days=30,
        last_trade_date=trade_date,
        block_report=block_report,
        selection_report=selection_report,
        tracker_report=str(final_state.get("tracker_report", "")),
        technical_report=str(final_state.get("technical_report", "")),
        updated_at=date.today().isoformat(),
    )


def update_board_from_state(board: LogicBoard, final_state: dict[str, Any], trade_date: str) -> LogicBoard:
    """Update an existing board in place without letting LLM output rename it."""
    built = build_board_from_state(
        final_state,
        board.seed_query,
        trade_date,
        board_id=board.id,
        board_name=board.name,
    )
    board.stocks = built.stocks
    board.last_trade_date = trade_date
    board.block_report = built.block_report
    board.selection_report = built.selection_report
    board.tracker_report = built.tracker_report
    board.technical_report = built.technical_report
    board.updated_at = built.updated_at
    return ensure_board_build_reports(board)


def ensure_board_build_reports(board: LogicBoard) -> LogicBoard:
    """Guarantee that every persisted stock pool has a readable build rationale."""
    if not board.stocks:
        return board
    if not board.block_report.strip():
        board.block_report = _default_block_report(board)
    if not board.selection_report.strip():
        board.selection_report = _default_selection_report(board)
    return board


def _default_block_report(board: LogicBoard) -> str:
    seed = board.source_event or board.seed_query or board.name
    return "\n".join(
        [
            f"## {board.name}",
            "",
            f"- 核心触发: {seed}",
            f"- 股票池规模: {len(board.stocks)} 只",
            f"- 跟踪周期: 近 {board.tracking_days} 个交易日",
            "- 建池方式: 根据事件关键词、产业链环节、概念映射、地域/股权关联和市场热度整理股票池。",
            "- 每日更新字段: 事件进展、新闻强度、涨跌幅、资金流、龙虎榜、扩散/退潮信号和技术趋势。",
            "",
            "### 股票池",
            "",
            render_candidate_table(board.stocks),
        ]
    )


def _default_selection_report(board: LogicBoard) -> str:
    lines = [
        "| 代码 | 名称 | 入池来源 | 跟踪定位 |",
        "|---|---|---|---|",
    ]
    for item in board.stocks:
        source = item.source or "股票池"
        role = "默认观察"
        if "核心" in source:
            role = "核心观察"
        elif "弹性" in source:
            role = "弹性观察"
        elif "剔除" in source:
            role = "剔除观察"
        lines.append(f"| {item.code} | {item.name or '-'} | {source} | {role} |")
    return "\n".join(lines)


def infer_board_name(*texts: str) -> str:
    for text in texts:
        for prefix in ("**逻辑板块**:", "逻辑板块:", "板块名称:", "**板块名称**:"):
            if prefix in text:
                line = text.split(prefix, 1)[1].splitlines()[0].strip(" *#：:")
                if line:
                    return line[:40]
        for line in text.splitlines():
            stripped = line.strip(" #*")
            if stripped and ("板块" in stripped or "链" in stripped):
                return stripped[:40]
    fallback = next((t for t in texts if t.strip()), "自定义逻辑板块")
    return fallback.strip().splitlines()[0][:40]


def migrate_event_boards(results_dir: str | None = None) -> list[LogicBoard]:
    root = Path(results_dir or DEFAULT_CONFIG["results_dir"])
    migrated: list[LogicBoard] = []
    for state_path in (root / "event_driven").rglob("event_driven_state_*.json"):
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
            board = build_board_from_state(
                raw,
                str(raw.get("seed_query", state_path.parent.name)),
                str(raw.get("trade_date", "")),
            )
            save_logic_board(board, str(root))
            migrated.append(board)
        except Exception:
            continue
    return migrated


def ensure_default_boards(results_dir: str | None = None) -> list[LogicBoard]:
    boards = list_logic_boards(results_dir)
    if boards:
        _repair_default_board(boards, results_dir)
        return boards

    migrated = migrate_event_boards(results_dir)
    if migrated:
        return list_logic_boards(results_dir)

    board = _default_changxin_board()
    save_logic_board(board, results_dir)
    return [board]


def _default_changxin_board() -> LogicBoard:
    name = "长鑫存储上市"
    return LogicBoard(
        id=board_id_from_name(name),
        name=name,
        seed_query="长鑫存储上市 -> 国产存储/合肥国资/半导体设备",
        source_event="长鑫存储上市",
        stocks=[
            StockCandidate("603986", "兆易创新", "默认板块"),
            StockCandidate("601133", "柏诚股份", "默认板块"),
            StockCandidate("603061", "金海通", "默认板块"),
            StockCandidate("688449", "联芸科技", "默认板块"),
            StockCandidate("000417", "合百集团", "默认板块"),
            StockCandidate("000859", "国风新材", "默认板块"),
            StockCandidate("603324", "盛剑科技", "默认板块"),
            StockCandidate("002654", "万润科技", "默认板块"),
            StockCandidate("603005", "晶方科技", "默认板块"),
            StockCandidate("002158", "汉钟精机", "默认板块"),
            StockCandidate("603938", "三孚股份", "默认板块"),
            StockCandidate("301322", "绿通科技", "默认板块"),
        ],
        tracking_days=30,
        last_trade_date="",
        updated_at=date.today().isoformat(),
    )


def _repair_default_board(boards: list[LogicBoard], results_dir: str | None = None) -> None:
    default = _default_changxin_board()
    for board in boards:
        if board.id == default.id and not board.stocks:
            board.stocks = default.stocks
            board.seed_query = board.seed_query or default.seed_query
            board.source_event = board.source_event or default.source_event
            save_logic_board(board, results_dir)
            return
