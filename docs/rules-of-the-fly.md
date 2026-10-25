# Rules of the fly

The project is only honest if it is clear what is the fly's and what is ours. These rules are enforced by code, not just by good intentions.

> **The wiring is untouched; a few dials are evolved.** Never say "nothing is trained": say what is invented.

**Colour rule.** **Teal** = real wiring read off the MaleCNS connectome. **Orange** = invented by us. Everything in the UI, in `python -m fly_mario_fly.rules list`, and in the MCP answers carries one of the two.

## Do

1. **The fly makes every decision.** A button is pressed only because real motor or descending neurons are active.
2. **Read the game's memory** to work out what the fly senses.
3. **Invent cues** the fly can react to (a visual angle, a smell level...). A cue is orange; the route it rides is teal.
4. **Add dials** that set how strong each sense and cue is. Dials are the only thing evolution may tune.

## Don't

1. **Edit the fly's wiring.** No neuroevolution: the connectome weights are read-only.
2. **Fire the fly's neurons directly.** Senses may only drive the *input* neurons of a declared circuit.
3. **Let our code decide an action for the fly.**

## How each rule is enforced

| rule | validator (`python -m fly_mario_fly.rules validate`) | at run time |
|---|---|---|
| every plug-in declares its origin (`R-DECLARED`, `R-ORIGIN-KIND`) | a `DECLARATION` next to every `PLUGIN`; only mechanisms are teal, everything that reads the game or decides is orange | |
| a teal item cites the real route (`R-FLY-ROUTE`) | the mechanism exists and the cell types it cites belong to it | |
| senses drive only declared input groups (`R-SENSE-ROUTE`) | the groups are input groups of the circuit the sense feeds; a sense that drives nothing declares what it modulates | the runner stops a sense that writes any other group |
| actions decide only from their own motor/descending neurons (`R-ACTION-SOURCE`) | declared groups = `source_groups` and are outputs of the circuit; declared buttons; game facts it also uses (`airborne`) are declared and explained | an action sees only its declared groups (`GuardedRates`) and may touch only its declared buttons |
| dials are honest (`R-DIALS`) | every dial is `invented`; evolvable only on senses, actions and shapes; keys are unique | |
| weights are read-only (`R-NO-WEIGHT-WRITES`) | nothing writes `.W`/`._Ws` except `Brain.__init__` | `brain.W` is a read-only copy with a fingerprint re-checked at the end of every run |
| no direct firing (`R-NO-DIRECT-DRIVE`) | `.drive()` / `.advance(h, I)` only in `fly/` and `runner/`; senses and actions never import the brain | `Brain.drive` accepts only input groups; `Brain.advance` rejects input on any other neuron |

The guards stop mistakes and make the rule visible; they are not a sandbox against code that goes out of its way to defeat them. Review decides the rest.

## Declaring a plug-in

Every plug-in file ends with a declaration (`from fly_mario_fly.rules import Route, declare`):

```python
DECLARATION = declare(
    "sense", "invented",
    "Invented cue: the angle theta a nearby object would subtend, fed to the real looming detectors; the wiring from there to the jump is real.",
    route=Route("escape", ("LC4", "LPLC2"), "LC4/LPLC2 -> DNp01 (Giant Fiber) -> TTMn (jump muscle)"),
    drives=("LC4_L", "LC4_R", "LPLC2_L", "LPLC2_R"))
```

| field | for | meaning |
|---|---|---|
| `kind` | all | `sense`, `action`, `object`, `character` (a creature), `shape`, `scene`, `mechanism` |
| `origin` | all | `"fly"` (teal; only mechanisms) or `"invented"` (orange) |
| `what` | all | one plain sentence: what is real here, what is invented |
| `route` | senses, actions, mechanisms | `Route(mechanism, cell_types, wiring)`: the real circuit and cell types it rides |
| `drives` | senses | the input groups it may write |
| `modulates` | senses that drive nothing | the modifiers it raises for another sense |
| `reads_groups`, `buttons`, `game_reads` | actions | the groups it may read, the buttons it may press, any game fact it also uses (each justified in `what`) |

## Things we decided

- Dials may be sense strengths, action thresholds and shape geometry; today's champion evolves eight of them. All are orange.
- `jump` also reads `airborne`: A is pressed only on the ground and released for a frame after landing, because the NES needs the release before it accepts a new jump. A mechanical constraint, declared as such.
- Mechanisms are teal even though *which* extra neurons each adds (for example the relays) follows a rule of ours; the wiring between them is the data's.

Add a rule or change one in `src/fly_mario_fly/rules/` (the catalogue, validator and guards live there); each rule needs a test that breaks it on purpose.
