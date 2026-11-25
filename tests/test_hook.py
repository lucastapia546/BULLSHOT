import json
import subprocess
import sys
from pathlib import Path

import pytest

from tradeagent.config import load_config
from tradeagent.hook_guard import ALLOW, BLOCK, classify, decide

ROOT = Path(__file__).resolve().parent.parent
P = "mcp__robinhood-trading__"


@pytest.fixture
def cfg():
    return load_config()


@pytest.mark.parametrize("tool,kind", [
    ("get_quote", "read"), ("get_positions", "read"), ("list_orders", "read"),
    ("get_order_history", "read"), ("get_account", "read"), ("search_instruments", "read"),
    ("place_order", "order"), ("submit_equity_order", "order"), ("buy_stock", "order"),
    ("cancel_order", "forbidden"), ("modify_order", "forbidden"), ("transfer_funds", "forbidden"),
    ("place_option_order", "forbidden"), ("update_agent_settings", "forbidden"),
    ("do_something_new", "unknown"),
])
def test_classify(cfg, tool, kind):
    assert classify(P + tool, cfg) == kind


def test_non_robinhood_tools_pass(cfg):
    assert classify("Bash", cfg) == "other"


@pytest.mark.parametrize("tool,code", [
    ("get_quote", ALLOW), ("place_order", BLOCK), ("cancel_order", BLOCK), ("mystery", BLOCK)])
def test_decide(cfg, tool, code):
    assert decide({"tool_name": P + tool, "tool_input": {}}, cfg)[0] == code


def test_hook_process_blocks_orders_and_fails_closed():
    def run(stdin):
        return subprocess.run([sys.executable, "-m", "tradeagent.hook_guard"], input=stdin,
                              capture_output=True, text=True, cwd=ROOT)
    blocked = run(json.dumps({"tool_name": P + "place_order", "tool_input": {"symbol": "AAPL"}}))
    assert blocked.returncode == 2 and "BLOCKED" in blocked.stderr
    assert run(json.dumps({"tool_name": P + "get_quote", "tool_input": {}})).returncode == 0
    assert run("not json").returncode == 2
