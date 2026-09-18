# fly_mario

Super Mario Bros (NES) played by the **real fruit fly escape circuit**, taken
from the Janelia FlyEM MaleCNS v1.0 connectome. A Goomba approaches, 311 real
looming-detector neurons fire, the Giant Fiber commits, the jump muscle
contracts, Mario jumps. Nothing is trained.

**Read `SPEC_jump.md` before writing code.** It carries the verified neuron
counts, connection weights, RAM addresses and the design decisions already
settled. Work only on what that spec scopes.

## Repo context

This repo sits inside `fly_brain/`, which holds the connectome data and the
analysis tooling. Reference it via `../`; never copy the data in, never commit it.

- `../data/malecns_v1.0/` — the downloaded feather files (1 GB; gitignored)
- `../data/derived/` — cached aggregates
- `../mcns.py` — streaming loader and aggregator, reuse it
- `../escape_circuit.py` — the extraction that produced the escape subgraph

## Invariants

These are settled. If you think one is wrong, say so rather than quietly
working around it.

1. **Read RAM, not pixels.** The NES view is third-person side-scrolling. A
   Goomba walking toward Mario does not expand on screen, so there is no
   looming stimulus in the raw frame. Feeding pixels to LC4/LPLC2 gives them an
   optomotor signal, not a threat, and the premise collapses. Synthesise
   Mario's-eye view from RAM: `theta = 2*arctan(w / (2*|d|))`.

2. **Never load the weights file whole.** 152M rows, 3.6 GB uncompressed.
   Stream it in Arrow record batches — `mcns.py` already does this.

3. **Exactly two hand-set scalars**: the global gain `g` and the TTMn press
   threshold. Everything else comes from the connectome. If a third constant
   appears, flag it in the README.

4. **The circuit is recurrent, not feedforward.** Lateral connection within the
   detector populations is 3–9.5x their drive onto the Giant Fiber. Model it as
   a dynamical system; do not collapse it to a weighted sum.

5. **Keep the hemispheres separate.** Each detector drives exactly one Giant
   Fiber — the wiring is strictly lateralised.

6. **The shuffled-connectome control ships with the feature**, not afterwards.
   Same neurons, same degree distribution, same signs, edges rewired at random.
   Without it we cannot claim the fly's wiring is doing anything.

## Style

Python. Small, readable modules over one large file. Assert the verified
connectome numbers at load time and fail loudly if the data changed underneath
us. Comment the biology, not the syntax — a reader should learn why LPLC2
exists, not what a for loop does.

## Out of scope for now

Steering, terrain, learning, the live brain overlay, training of any kind.
Those are later steps and have their own specs. Build the jump.
