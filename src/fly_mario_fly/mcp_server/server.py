"""The MCP server: wires the tools in service.py to the MCP SDK. Run it with  python -m fly_mario_fly.mcp_server  (stdio)."""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from fly_mario_fly.mcp_server import service

INSTRUCTIONS = """fly_mario_fly: a fruit-fly connectome (MaleCNS v1.0, real wiring = TEAL) plays Super Mario Bros through senses we invented (ORANGE).
Start with list_rules. Do: let the fly make every decision; read game memory to work out what it senses; invent cues; add dials.
Don't: edit the wiring, fire neurons directly, or let our code decide an action. The wiring is untouched; a few dials are evolved.
Every write is validated and refused, with the reason, if it would break a rule. Tools never edit weights and cannot fire neurons."""


def build_server() -> MCPServer:
    mcp = MCPServer("fly_mario_fly", instructions=INSTRUCTIONS)

    @mcp.tool()
    def list_rules() -> dict:
        """The project's rules (do's and don'ts), the teal/orange colour rule, and what no tool can do."""
        return service.list_rules()

    @mcp.tool()
    def list_plugins(kind: str = "") -> dict:
        """Plug-ins with their origin (teal = real wiring, orange = invented). kind: senses, actions, objects, characters,
        shapes, scenes, mechanisms; empty = all."""
        return service.list_plugins(kind or None)

    @mcp.tool()
    def explain_plugin(kind: str, name: str) -> dict:
        """Everything about one plug-in: its declaration (what is real, what is invented, the route and cell types), dials, source file."""
        return service.explain_plugin(kind, name)

    @mcp.tool()
    def list_flies() -> dict:
        """The fly configs (YAML files) that can be run or edited."""
        return service.list_flies()

    @mcp.tool()
    def create_fly(name: str, copy_from: str = "blank", dry_run: bool = False) -> dict:
        """Create a new fly config as a copy of an existing one (never overwrites)."""
        return service.create_fly(name, copy_from, dry_run)

    @mcp.tool()
    def add_sense(name: str, label: str, effect: str, cue: str, route: str, drives: list[str], gain: float, colour: str = "green",
                  range_px: float = 96.0, split_by_side: bool = False, wiring: str = "", what: str = "", dry_run: bool = False) -> dict:
        """Add a sense: an invented cue (angular_size | proximity | constant) driving INPUT neurons of a real circuit. route = a
        mechanism name (see list_plugins mechanisms); drives = its input groups. Refused if it would drive a motor or descending
        neuron, or leave its route. Use dry_run to check without writing."""
        return service.add_sense(name, label, effect, cue, route, drives, gain, colour, range_px, split_by_side, wiring, what, dry_run)

    @mcp.tool()
    def add_cue(fly: str, sense: str, objects: list[str] | None = None, save_as: str = "", dry_run: bool = False) -> dict:
        """Attach a sense (a cue) to object types in a fly config. Use save_as to leave the original fly untouched."""
        return service.add_cue(fly, sense, objects, save_as, dry_run)

    @mcp.tool()
    def add_character(name: str, label: str, note: str, type_bytes: list[int], size: list[int], live_states: list[int] | None = None,
                      what: str = "", dry_run: bool = False) -> dict:
        """Add a creature found in the enemy slots by its RAM type byte(s) and box size (orange: it only reads game memory)."""
        return service.add_character(name, label, note, type_bytes, size, live_states, what, dry_run)

    @mcp.tool()
    def add_object(name: str, label: str, note: str, tile_ids: list[int], what: str = "", dry_run: bool = False) -> dict:
        """Add solid terrain made of metatile ids standing on the ground, like a pipe (orange: it only reads game memory)."""
        return service.add_object(name, label, note, tile_ids, what, dry_run)

    @mcp.tool()
    def set_dial(fly: str, key: str, value: float, save_as: str = "", dry_run: bool = False) -> dict:
        """Set one dial (how strong a cue or readout is) of a fly, within its range. Only dials; never weights or neurons.
        Use save_as to leave the original fly untouched."""
        return service.set_dial(fly, key, value, save_as, dry_run)

    @mcp.tool()
    def run_fly(fly: str, level: str = "1-1", seed: int = 0, noop: int = 0, sigma: float = 0.0, max_frames: int = 6000,
                video: bool = False) -> dict:
        """Play one episode headlessly: outcome, furthest x, frames, a reproducible hash, and the teal/orange labels of the senses
        used. video=true also renders an mp4 and returns its path (slow). Needs the MaleCNS brain cache; never downloads."""
        return service.run_fly(fly, level, seed, noop, sigma, max_frames, video)

    return mcp
