# The MCP server

An [MCP](https://modelcontextprotocol.io) server lets an AI client (Claude Desktop, Claude Code, or any other MCP client) work on this project
safely: explore the rules and plug-ins, add new senses, cues, creatures and objects, set dials, and run a fly headlessly.

**Every write is validated and refused, with the reason, if it would break a rule** (see [the rules](../src/fly_mario_fly/rules/catalogue.py);
`python -m fly_mario_fly.rules list`). No tool can edit the connectome weights or fire neurons: there is no such tool, and no parameter that could.
New plug-ins are made from **fixed recipes** with validated names and numbers; the client never supplies code.

> Colour rule: **teal** = real wiring read off the MaleCNS connectome, **orange** = invented by us. Every answer carries the label.
> The wiring is untouched; a few dials are evolved.

## Install and run

From a checkout (the server writes plug-in files into it, so install it editable):

```bash
pip install -r requirements.txt && pip install -e . --no-deps      # the pinned install already includes the MCP SDK
#   or: pip install -e ".[mcp]"
python -m fly_mario_fly.mcp_server                                  # stdio; also installed as the command `fly-mario-fly-mcp`
```

Running a fly needs the MaleCNS brain cache (`$FLY_MARIO_FLY_DATA`, see the README). Without it every tool except `run_fly` works, and
`run_fly` says what is missing. The server **never downloads** the data by itself.

## Connect a client

**Claude Code**

```bash
claude mcp add fly-mario-fly -- /path/to/.venv/bin/python -m fly_mario_fly.mcp_server
```

**Claude Desktop** (and most other clients): add to the client's MCP config, using the Python from the environment where you installed the project:

```json
{
  "mcpServers": {
    "fly-mario-fly": {
      "command": "/path/to/.venv/bin/python",
      "args": ["-m", "fly_mario_fly.mcp_server"],
      "env": { "FLY_MARIO_FLY_DATA": "/path/to/fly_mario_fly_data" }
    }
  }
}
```

On Windows use `C:\\path\\to\\.venv\\Scripts\\python.exe`. Set `FLY_MARIO_FLY_FLIES_DIR` to keep the flies the tools write somewhere other than `configs/flies/`.

## Tools

| tool | what it does | writes |
|---|---|---|
| `list_rules` | the do's and don'ts, the colour rule, and what no tool can do | no |
| `list_plugins(kind?)` | senses, actions, objects, characters, shapes, scenes, mechanisms, each labelled teal or orange | no |
| `explain_plugin(kind, name)` | its declaration: what is real, what is invented, the route and cell types, its dials, its source file | no |
| `list_flies` | the fly configs available | no |
| `create_fly(name, copy_from)` | a new fly config (a YAML copy; never overwrites) | `configs/flies/<name>.yaml` |
| `add_sense(...)` | a new sense: an invented cue (`angular_size`, `proximity` or `constant`) driving input neurons of a real circuit | `senses/<name>.py` |
| `add_cue(fly, sense, objects)` | attach a sense to object types in a fly | the fly's YAML |
| `add_character(...)` | a creature found in the enemy slots by RAM type byte(s) and box size | `mario/objects/<name>.py` |
| `add_object(...)` | solid terrain made of metatile ids standing on the ground | `mario/objects/<name>.py` |
| `set_dial(fly, key, value)` | one dial of a fly, inside its range | the fly's YAML |
| `run_fly(fly, level, seed, ...)` | play one episode headlessly: outcome, furthest x, frames, a reproducible hash, optional mp4 | `$FLY_MARIO_FLY_DATA/runs` (and videos) |

`add_*`, `create_fly` and `set_dial` take `dry_run=true` (check, write nothing).

**Committed flies are protected.** `set_dial` and `add_cue` edit a fly in place only if this server created it (`create_fly`). Every other fly, including all the
reference flies in `configs/flies/` such as `champion_e1s`, is refused with "pass `save_as`"; with `save_as` the edit goes to a new copy and the original is never touched.

### What gets refused (and why)

- a sense that drives a **motor or descending neuron** (e.g. `DNp01`, `TTMn`), or any group that is not an input group of the circuit it rides: *"cannot be driven"*;
- a route that is not a real mechanism, or cites cell types the circuit does not use;
- a dial that does not exist: *"only dials can be set (never weights or neurons)"*; a value outside its range;
- an in-place edit of a fly this server did not create (use `save_as`); a name that already exists, an existing file (nothing is ever overwritten), a fly name that is a path;
- a creature whose RAM type byte already belongs to another, terrain whose tile ids are already named in the game facts;
- text with line breaks, and numbers that are out of range, not finite, or not numbers.

Before a file is written it must pass the compliance validator (`python -m fly_mario_fly.rules validate`), the static scans, and a smoke test
(a sense is called on hand-made frames and must stay inside its declared groups; a creature or terrain is run against the real emulator).

### Example

> *"Add a sweet smell for pipes on the left and right antennae, then attach it to a new fly."*

```text
add_sense(name="pipe_smell", label="Pipe smell", effect="Pipes smell faintly of metal.", cue="angular_size",
          route="attraction", drives=["ORN_L", "ORN_R"], gain=80, split_by_side=true)
create_fly(name="pipe_fan", copy_from="looming_only")          # a copy the server may then edit in place
add_cue(fly="pipe_fan", sense="pipe_smell", objects=["pipe"])
run_fly(fly="pipe_fan", seed=101, noop=3)
```

The first call answers `colour: orange` for the sense and `colour: teal` for the route it rides (`ORN -> relays -> DNa01/02`). A request such as
`add_sense(..., route="escape", drives=["DNp01"])` comes back `ok: false` with the rule and the reason, and nothing is written.

## Safety model

- **No code from the client.** Plug-in files are generated from a template with validated literals embedded using `repr()`; no client text reaches a docstring or comment.
- **Names are identifiers**, never paths. Files are created with exclusive-create: an existing file is never replaced.
- **The weights are read-only** inside the brain (see `src/fly_mario_fly/rules/`); the server has no way to reach them.
- The server runs with the permissions of the user who starts it and writes into the checkout and the flies folder. Run it only for clients you trust, and review what it
  wrote (`git diff`) before committing. It is a local stdio server and opens no network port.
