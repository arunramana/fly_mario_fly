"""The MCP server itself: the tool list, that no tool can touch weights or neurons, and a real stdio round trip."""
import asyncio
import json
import sys

import pytest

pytest.importorskip("mcp")

from mcp.client import Client                          # noqa: E402
from mcp.client.stdio import StdioServerParameters     # noqa: E402

from fly_mario_fly.mcp_server.server import build_server   # noqa: E402

EXPECTED = {"list_rules", "list_plugins", "explain_plugin", "list_flies", "create_fly", "add_sense", "add_cue", "add_character",
            "add_object", "set_dial", "run_fly"}
FORBIDDEN_WORDS = ("weight", "neuron", "rate", "activation", "inject", "fire", "button", "action", "code", "python", "script", "path", "file")


def call(client, name, args=None):
    r = asyncio.run(client.call_tool(name, args or {}))
    return json.loads(r.content[0].text)


def test_the_tool_list_is_exactly_the_documented_one():
    tools = asyncio.run(_tools())
    assert {t.name for t in tools} == EXPECTED


async def _tools():
    async with Client(build_server()) as c:
        return (await c.list_tools()).tools


def test_no_tool_has_a_parameter_that_could_edit_weights_or_fire_neurons():
    for t in asyncio.run(_tools()):
        for p in t.input_schema.get("properties", {}):
            assert not any(w in p.lower() for w in FORBIDDEN_WORDS), (t.name, p)
        assert not any(w in t.name for w in ("weight", "neuron", "fire", "inject", "press", "act_"))


async def _session():
    async with Client(build_server()) as c:
        rules = json.loads((await c.call_tool("list_rules", {})).content[0].text)
        bad = json.loads((await c.call_tool("add_sense", dict(name="evil", label="Evil", effect="Fires the giant fibre directly.",
                                                              cue="constant", route="escape", drives=["DNp01"], gain=1.0,
                                                              dry_run=True))).content[0].text)
        weights = json.loads((await c.call_tool("set_dial", dict(fly="looming_only", key="W", value=1.0, save_as="probe", dry_run=True))).content[0].text)
        return rules, bad, weights


def test_a_client_gets_rules_and_refusals_with_reasons_through_the_protocol():
    rules, bad, weights = asyncio.run(_session())
    assert rules["colour_rule"].startswith("teal")
    assert bad["ok"] is False and bad["nothing_written"] and any(r["rule"] == "R-SENSE-ROUTE" for r in bad["refused"])
    assert weights["ok"] is False and "never weights" in weights["refused"][0]["message"]


async def _stdio():
    params = StdioServerParameters(command=sys.executable, args=["-W", "ignore", "-m", "fly_mario_fly.mcp_server"])
    async with Client(params) as c:
        return json.loads((await c.call_tool("list_plugins", {"kind": "mechanisms"})).content[0].text)


def test_the_server_runs_as_a_stdio_process():
    out = asyncio.run(_stdio())
    assert {p["name"] for p in out["plugins"]} == {"escape", "walking", "hearing", "attraction", "aversion"}
