"""MCP server for fly_mario_fly: lets an AI client (Claude and others) explore the rules and plug-ins, add new senses, cues,
creatures and objects, set dials, and run a fly headlessly. Every write goes through the compliance validator
(fly_mario_fly.rules) and is refused, with the reason, if it would break a rule.

    python -m fly_mario_fly.mcp_server            # stdio

service.py has the tool logic as plain functions (no MCP dependency); server.py wires them to the MCP SDK.
"""
