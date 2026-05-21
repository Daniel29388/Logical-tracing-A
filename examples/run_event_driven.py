from dotenv import load_dotenv

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.event_driven import EventDrivenAgentsGraph


load_dotenv()

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "deepseek"
config["quick_think_llm"] = "deepseek-chat"
config["deep_think_llm"] = "deepseek-chat"
config["output_language"] = "Chinese"


if __name__ == "__main__":
    graph = EventDrivenAgentsGraph(debug=False, config=config)
    _, report = graph.run(
        seed_query="长鑫存储上市 -> 国产存储/合肥国资/半导体设备",
        trade_date="2026-05-20",
    )
    print(report)
