# Logic Board A-Stock Agents

一个面向 A 股事件驱动研究的本地多 Agent 看板。项目基于 TradingAgents-Astock 改造，保留可复用的数据工具和 Agent 能力，精简为“事件逻辑 -> 股票池 -> 逻辑板块 -> 30 个交易日追踪 -> 技术面分析”的工作流。

> 本项目仅用于学习研究和技术演示，不构成任何投资建议。

## 核心能力

- 事件驱动建池：从新闻、公告、政策、市场传闻中抽取可能发酵的事件。
- 逻辑提炼：把事件转成可追踪的产业链或交易逻辑。
- 关键词/概念反查：根据关键词、行业、地域、概念板块反查 A 股股票池。
- 逻辑板块看板：保存自定义板块，例如“长鑫存储上市”，可反复刷新。
- 30 日追踪：对板块内个股拉取近 30 个交易日行情、资金、龙虎榜等信息。
- 技术面分析：对板块个股做趋势、均线、量价、突破、回踩等分析。
- 通达信优先：本地默认优先使用 `mootdx` 通达信行情，失败时回退东方财富/新浪 HTTP 数据。

## 快速启动

推荐使用 Windows 一键启动脚本：

```bat
start_web.bat
```

脚本会：

- 自动设置 `PYTHONPATH`。
- 自动创建本地结果和缓存目录。
- 检查并安装前端/数据依赖。
- 默认使用清华 PyPI 镜像安装依赖。
- 默认优先使用通达信服务器 `110.41.147.114:7709`。
- 打开 Streamlit 前端：`http://localhost:8501`。

## 配置密钥

复制 `.env.example` 为 `.env`，填入你要使用的模型服务密钥：

```env
DEEPSEEK_API_KEY=your_key_here
```

`.env` 已被 `.gitignore` 忽略，不要把真实密钥提交到 GitHub。

## 通达信连接

默认配置：

```env
TRADINGAGENTS_USE_TDX_FIRST=1
TRADINGAGENTS_TDX_SERVER=110.41.147.114:7709
TRADINGAGENTS_TDX_TIMEOUT=5
TRADINGAGENTS_TDX_SOCKET_TIMEOUT=1.2
TRADINGAGENTS_TDX_MAX_SERVERS=12
```

诊断通达信服务器：

```bat
C:\Users\DFG\.conda\envs\py310\python.exe scripts\check_tdx.py --limit 8 --symbol 002405 --timeout 3 --socket-timeout 1
```

如果默认服务器失效，可以在 `.env` 中覆盖：

```env
TRADINGAGENTS_TDX_SERVER=新的ip:7709
```

## 前端使用

1. 启动 `start_web.bat`。
2. 在左侧选择已有逻辑板块，例如“长鑫存储上市”。
3. 点击“刷新板块看板”。
4. 查看四个结果页：
   - 股票池
   - 30 日追踪
   - 技术面
   - 建池逻辑
5. 也可以在左侧新建逻辑板块，系统会先建池，再刷新追踪和技术面。

## 命令行示例

```bat
python -m cli.main event --seed "长鑫存储 IPO -> 国产存储/合肥国资/半导体设备" --date 2026-05-20 --provider deepseek --quick-model deepseek-chat --deep-model deepseek-chat
```

## 项目结构

```text
tradingagents/
  agents/event_driven/      事件驱动 Agent 提示词与通用阶段 Agent
  event_driven/             逻辑板块状态、图编排、股票池解析、工具预取
  dataflows/                A 股数据工具，含通达信/东方财富/新浪/同花顺
web/
  app.py                    Streamlit 前端入口
  runner.py                 前端任务运行器
  components/               看板组件
scripts/
  check_tdx.py              通达信连接诊断
docs/
  event_driven_agents_design.md
tests/
```

## 本地上传 GitHub

在整理后的项目目录执行：

```bat
git status
git remote add origin https://github.com/你的用户名/你的仓库名.git
git branch -M main
git push -u origin main
```

## 验证

```bat
python -m compileall tradingagents web cli scripts
python -m pytest tests\test_event_driven_agents.py tests\test_keyword_stock_pool.py -q
start_web.bat --check
```

## 许可证

本项目保留原始项目的 Apache-2.0 许可证声明。详见 `LICENSE`、`NOTICE` 和相关上游说明文件。
