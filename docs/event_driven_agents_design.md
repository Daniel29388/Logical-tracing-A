# 事件驱动多 Agent 精简设计

本文档把 `simonlin1212/TradingAgents-astock` 的可复用能力拆出来，并按你的逻辑图重组为一条更轻、更适合题材/事件跟踪的多 Agent 协作链。

## 我们从原项目保留什么

原项目最有价值的部分不是后面的多空辩论，而是已经落地的 A 股工具层和 LangGraph/LLM 底座：

| 模块 | 保留方式 | 原因 |
|------|----------|------|
| `tradingagents.llm_clients` | 继续复用 | 已支持 OpenAI 兼容、Anthropic、Google、Azure 等供应商 |
| `tradingagents.default_config` | 继续复用 | 已有模型、缓存、结果目录、A 股数据源配置 |
| `tradingagents.dataflows.a_stock` | 继续复用 | 已接入 mootdx、东财、新浪、同花顺、财联社等 A 股数据 |
| `tradingagents.agents.utils.*_tools` | 继续复用 | 工具已经包装成 LangChain tool，可被新 Agent 直接调用 |
| `structured.py` | 继续复用 | 决策 Agent 可以稳定输出结构化结果，并回退到自由文本 |
| Market / Hot Money / News 思路 | 部分复用 | 技术面、资金面、新闻面逻辑适合成为新链路里的子 Agent |

## 我们删掉什么

原项目的默认链路是：

`7 Analyst -> Bull/Bear 辩论 -> Research Manager -> Trader -> 三方风险辩论 -> Portfolio Manager`

你的目标不是“针对单票做完整投研辩论”，而是“从未来可能发酵的事件中发现逻辑、找标的、组板块、持续跟踪、排序决策”。因此第一版新链路会删掉：

- Bull/Bear 投资辩论
- Research Manager
- Trader
- Aggressive / Conservative / Neutral 风险辩论
- Portfolio Manager

这些角色以后仍可作为可选插件接回，但不放进主流程。

## 新协作链路

```text
新闻事件 Agent
  -> 逻辑提炼 Agent
  -> 标的发现 Agent
  -> 选股理由 Agent
  -> 逻辑板块 Agent
  -> 逻辑追踪 Agent
  -> 技术面 Analyst
  -> 资金情绪 Analyst
  -> 决策 Agent
```

## Agent 职责与输入输出

| Agent | 职责 | 主要输入 | 主要输出 |
|------|------|----------|----------|
| 新闻事件 Agent | 从新闻、公告、政策、市场传闻里提取“未来可能发酵的事件” | 财联社/东财快讯、强势股题材、用户给定关键词 | 事件清单、触发源、可能发酵窗口 |
| 逻辑提炼 Agent | 把新闻转成可跟踪逻辑链 | 事件清单 | `事件 -> 产业链/供需/政策/资金 -> 受益环节` |
| 标的发现 Agent | 根据关键词、产业链、地域、股权、概念板块找相关 A 股标的 | 逻辑链、强势股题材 | 候选标的池、关联路径、确定性等级 |
| 选股理由 Agent | 给每个标的生成关联理由，区分强关联、弱关联、蹭概念 | 候选标的池、概念板块、新闻 | 每只票的入选/剔除理由 |
| 逻辑板块 Agent | 把标的组合成自定义板块 | 选股理由 | 板块名称、核心事件、跟踪周期、核心/弹性/观察分层 |
| 逻辑追踪 Agent | 每天更新事件进展、新闻强度、涨跌幅、资金流、龙虎榜、扩散情况 | 自定义板块、候选标的 | 每日追踪快照、扩散/退潮信号 |
| 技术面 Analyst | 看趋势、均线、量价、突破、回踩 | 候选标的 | 技术评分、买点/止损/失效位 |
| 资金情绪 Analyst | 看主力资金、龙虎榜、涨停、板块联动、新闻热度 | 候选标的 | 资金情绪评分、游资/机构/散户特征 |
| 决策 Agent | 给出买入优先级 | 全部报告 | 核心票、弹性票、观察票、剔除票 |

## 第一版状态字段

新链路使用独立状态，不污染原 `AgentState`：

| 字段 | 含义 |
|------|------|
| `seed_query` | 用户输入的主题、事件、传闻或观察方向 |
| `trade_date` | 当前分析日期 |
| `event_report` | 新闻事件 Agent 输出 |
| `logic_report` | 逻辑提炼 Agent 输出 |
| `target_report` | 标的发现 Agent 输出 |
| `selection_report` | 选股理由 Agent 输出 |
| `block_report` | 逻辑板块 Agent 输出 |
| `tracker_report` | 逻辑追踪 Agent 输出 |
| `technical_report` | 技术面 Analyst 输出 |
| `capital_report` | 资金情绪 Analyst 输出 |
| `decision_report` | 决策 Agent 输出 |

## 当前工具覆盖与缺口

已可直接复用：

- 新闻/宏观：`get_global_news`, `get_news`
- 热点题材：`get_hot_stocks`
- 关键词/概念反查股票池：`get_stocks_by_keyword`
- 概念板块：`get_concept_blocks`
- 个股行情：`get_stock_data`, `get_indicators`
- 资金面：`get_fund_flow`, `get_northbound_flow`
- 龙虎榜：`get_dragon_tiger_board`
- 解禁风险：`get_lockup_expiry`
- 基本面：`get_fundamentals`, `get_profit_forecast`

第一阶段缺口：

- 公告全文搜索：现有 `get_news` 更偏个股新闻，不是公告数据库
- 市场传闻可信度分层：需要来源权重与重复出现次数
- 自定义板块持久化：需要把逻辑板块保存为可每日更新的对象

## 第一版落地策略

第一版先新增独立包 `tradingagents.event_driven`：

- 不改原 `TradingAgentsGraph`
- 复用原配置、LLM、工具
- 用 LangGraph 串起 9 个新节点
- 每个节点先产出 Markdown 报告
- 决策节点使用结构化输出，保证最终优先级稳定

后续再接：

- CLI 命令：`tradingagents event`
- Web 页面：事件板块追踪视图
- 每日自动追踪：保存逻辑板块，定时刷新资金/新闻/技术状态

## 当前代码入口

已经新增最小可导入入口：

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.event_driven import EventDrivenAgentsGraph

config = DEFAULT_CONFIG.copy()
config["output_language"] = "Chinese"

graph = EventDrivenAgentsGraph(config=config)
state, decision = graph.run(
    seed_query="长鑫存储 IPO -> 国产存储/合肥国资/半导体设备",
    trade_date="2026-05-20",
)
print(decision)
```

示例文件：`examples/run_event_driven.py`

也可以直接走 CLI：

```powershell
python -m cli.main event `
  --seed "长鑫存储 IPO -> 国产存储/合肥国资/半导体设备" `
  --date 2026-05-20 `
  --provider openai `
  --quick-model gpt-5.4-mini `
  --deep-model gpt-5.4
```

运行后会在 `results_dir/event_driven/<seed-slug>/` 下保存：

- `event_driven_state_<date>.json`：完整状态
- `event_driven_report_<date>.md`：完整 Markdown 报告
- `logic_block.json`：可复用的自定义逻辑板块档案

## 关键词反查股票池工具

已新增 `get_stocks_by_keyword(keyword, curr_date="", top_n=50, max_blocks=8)`。

第一版查询逻辑：

1. 从东方财富 push2 拉取地域、行业、概念板块列表。
2. 用关键词匹配板块名或 `BKxxxx` 板块代码。
3. 对匹配到的板块展开成分股，并返回涨跌幅、换手率、PE、主力净流入、所属行业等字段。
4. 如果没有匹配板块，降级从同花顺强势股题材归因里筛选包含关键词的线索。

典型调用：

```python
from tradingagents.agents.utils.signal_data_tools import get_stocks_by_keyword

print(get_stocks_by_keyword.invoke({
    "keyword": "存储芯片 半导体设备 合肥国资",
    "curr_date": "2026-05-20",
    "top_n": 30,
}))
```
