from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_CODE_RE = re.compile(r"(?<!\d)(?P<code>\d{6})(?!\d)")
_PIPE_ROW_RE = re.compile(r"^\s*\|(?P<body>.+)\|\s*$", re.MULTILINE)
_NAME_RE = re.compile(r"[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9*ST\-（）()]{1,24}")


@dataclass(frozen=True)
class StockCandidate:
    code: str
    name: str
    source: str = ""


def _clean_cell(value: str) -> str:
    value = value.replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", value).strip()


def _looks_like_name(value: str) -> bool:
    if not value:
        return False
    if value in {"代码", "名称", "股票", "优先级", "排名", "---"}:
        return False
    if set(value.replace(":", "").replace("-", "")) <= {"-"}:
        return False
    return bool(_NAME_RE.search(value))


def _infer_name_from_cells(cells: list[str], code_idx: int) -> str:
    current = _clean_cell(cells[code_idx])
    current_without_code = _CODE_RE.sub("", current).strip(" -_/：:()（）")
    if _looks_like_name(current_without_code):
        return current_without_code

    preferred = []
    for offset in (1, -1, 2, -2):
        idx = code_idx + offset
        if 0 <= idx < len(cells):
            preferred.append(cells[idx])
    preferred.extend(cells)

    for cell in preferred:
        text = _clean_cell(cell)
        if _CODE_RE.fullmatch(text):
            continue
        if _looks_like_name(text):
            return text
    return ""


def extract_stock_candidates(text: str, source: str = "") -> list[StockCandidate]:
    """Extract A-share codes and names from markdown reports.

    The event agents may output different table layouts, so this parser accepts
    any markdown row containing a 6-digit code and infers the nearest stock name.
    """
    candidates: list[StockCandidate] = []
    seen: set[str] = set()

    for row in _PIPE_ROW_RE.finditer(text or ""):
        cells = [_clean_cell(c) for c in row.group("body").split("|")]
        if not cells or all(set(c) <= {"-", ":"} for c in cells if c):
            continue
        for idx, cell in enumerate(cells):
            match = _CODE_RE.search(cell)
            if not match:
                continue
            code = match.group("code")
            if code in seen:
                continue
            seen.add(code)
            candidates.append(
                StockCandidate(
                    code=code,
                    name=_infer_name_from_cells(cells, idx),
                    source=source,
                )
            )

    for match in _CODE_RE.finditer(text or ""):
        code = match.group("code")
        if code in seen:
            continue
        start = max(0, match.start() - 24)
        end = min(len(text), match.end() + 24)
        window = text[start:end]
        names = [m.group(0) for m in _NAME_RE.finditer(window) if not _CODE_RE.fullmatch(m.group(0))]
        seen.add(code)
        candidates.append(StockCandidate(code=code, name=names[-1] if names else "", source=source))

    return candidates


def merge_stock_candidates(*groups: Iterable[StockCandidate]) -> list[StockCandidate]:
    merged: list[StockCandidate] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item.code in seen:
                continue
            seen.add(item.code)
            merged.append(item)
    return merged


def render_candidate_table(candidates: Iterable[StockCandidate]) -> str:
    rows = list(candidates)
    if not rows:
        return "未从自动反查结果中提取到 6 位 A 股代码。"
    lines = [
        "| 代码 | 名称 | 来源 |",
        "|---|---|---|",
    ]
    for item in rows:
        lines.append(f"| {item.code} | {item.name or '-'} | {item.source or '-'} |")
    return "\n".join(lines)
