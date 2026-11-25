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


# Every tool the live Robinhood server exposed on 2026-11-25 that must NOT run.
BLOCKED_REAL = [
    "add_legend_indicator", "add_option_to_watchlist", "add_to_watchlist", "cancel_advanced_order",
    "cancel_crypto_order", "cancel_equity_order", "cancel_option_exercise", "cancel_option_order",
    "create_alert", "create_scan", "create_watchlist", "decline_trade_approval", "delete_alert",
    "exercise_option", "follow_watchlist", "get_alert_log", "get_alerts", "get_bank_accounts",
    "get_banking_transactions", "get_credit_card_account", "get_credit_transactions",
    "get_crypto_account_onboarding_info", "get_crypto_orders", "get_crypto_positions", "get_crypto_quotes",
    "get_currency_pairs", "get_legend_charts", "get_legend_indicator_catalog", "get_legend_indicators",
    "get_legend_layouts", "get_limited_margin_upgrade_info", "get_option_chains", "get_option_historicals",
    "get_option_instruments", "get_option_level_upgrade_info", "get_option_orders", "get_option_positions",
    "get_option_quotes", "get_option_watchlist", "mark_alerts_read", "place_advanced_order",
    "place_crypto_order", "place_equity_order", "place_option_order", "preview_crypto_order",
    "remove_from_watchlist", "remove_legend_indicator", "remove_option_from_watchlist",
    "review_advanced_order", "review_equity_order", "review_option_order", "set_legend_chart_settings",
    "unfollow_watchlist", "update_alert", "update_legend_indicator", "update_scan_config",
    "update_scan_filters", "update_watchlist", "some_tool_added_later",
]


@pytest.mark.parametrize("tool", BLOCKED_REAL)
def test_real_tools_blocked(cfg, tool):
    assert classify(P + tool, cfg) in ("order", "blocked")
    assert decide({"tool_name": P + tool, "tool_input": {}}, cfg)[0] == BLOCK


@pytest.mark.parametrize("tool", ["place_equity_order", "place_advanced_order", "review_equity_order",
                                  "decline_trade_approval", "exercise_option"])
def test_order_tools_get_paper_hint(cfg, tool):
    assert classify(P + tool, cfg) == "order"


def test_allowlist_is_only_reads(cfg):
    assert "get_equity_quotes" in cfg.allowed_tools
    for name in cfg.allowed_tools:
        assert name not in BLOCKED_REAL
        assert not any(w in name for w in ("place", "cancel", "bank", "credit", "option", "crypto",
                                           "create", "update", "add", "remove", "follow", "exercise"))
        assert classify(P + name, cfg) == "read"


def test_non_robinhood_tools_pass(cfg):
    assert classify("Bash", cfg) == "other"


@pytest.mark.parametrize("tool,code", [
    ("get_equity_quotes", ALLOW), ("place_equity_order", BLOCK), ("cancel_equity_order", BLOCK), ("mystery", BLOCK)])
def test_decide(cfg, tool, code):
    assert decide({"tool_name": P + tool, "tool_input": {}}, cfg)[0] == code


def test_hook_process_blocks_orders_and_fails_closed():
    def run(stdin):
        return subprocess.run([sys.executable, "-m", "tradeagent.hook_guard"], input=stdin,
                              capture_output=True, text=True, cwd=ROOT)
    blocked = run(json.dumps({"tool_name": P + "place_equity_order", "tool_input": {"symbol": "AAPL"}}))
    assert blocked.returncode == 2 and "BLOCKED" in blocked.stderr
    assert run(json.dumps({"tool_name": P + "get_equity_quotes", "tool_input": {}})).returncode == 0
    assert run("not json").returncode == 2


@pytest.mark.parametrize("server", ["claude_ai_Robinhood", "claude_ai_Robinhood_Trading", "robinhood"])
def test_cloud_connector_names_are_guarded(cfg, server):
    assert classify(f"mcp__{server}__place_equity_order", cfg) == "order"
    assert classify(f"mcp__{server}__get_bank_accounts", cfg) == "blocked"
    assert classify(f"mcp__{server}__get_equity_quotes", cfg) == "read"


def test_other_mcp_servers_untouched(cfg):
    assert classify("mcp__github__create_pull_request", cfg) == "other"
