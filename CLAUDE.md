# fly_mario

Super Mario Bros (NES) played by the **real fruit fly escape circuit**, taken
from the Janelia FlyEM MaleCNS v1.0 connectome. A Goomba approaches, 311 real
looming-detector neurons fire, the Giant Fiber commits, the jump muscle
contracts, Mario jumps. Nothing is trained.

**Read `docs/SPEC_jump.md` before writing code.** It carries the verified neuron
counts, connection weights, RAM addresses and the design decisions already
settled; later features have their own `docs/SPEC_*.md`.

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

3. **Every hand-set scalar gets flagged and counted — no fixed budget.**
   Each one gets a typed, ranged home in `config/params.py` and a row in
   `docs/SCALARS.md` (generated from it, never written by hand). There
   are **77**: 55 invented (placed currents, mechanical hold durations),
   22 measured (simulated against the real weight matrix and picked by a
   sweep), **0 connectome-derived**. The connectome determines each
   circuit's weight matrix, never a scalar controlling how hard a circuit
   pushes on it. (This used to claim "exactly two", then "49", then "62"; none
   stayed true past the next prototype -- check `docs/SCALARS.md`'s own
   generated total, not this number, before relying on it for anything.)

4. **The circuit is recurrent, not feedforward.** Lateral connection within the
   detector populations is 3–9.5x their drive onto the Giant Fiber. Model it as
   a dynamical system; do not collapse it to a weighted sum.

5. **Keep the hemispheres separate.** Each detector drives exactly one Giant
   Fiber — the wiring is strictly lateralised.

6. **The shuffled-connectome control ships with the feature**, not afterwards.
   Same neurons, same degree distribution, same signs, edges rewired at random.
   Without it we cannot claim the fly's wiring is doing anything.

7. **Profile before proposing a GPU port — including when the proposal is
   yours.** Every real bottleneck so far has been I/O or a cached-value miss
   (a weights file, a font, reloaded when it didn't need to be), never
   arithmetic: run 026 expected the soma scatter to be the cost and found
   `_font()` reloading from disk every frame instead (see "Use the GPU"
   below). Measure the actual phases before reaching for CuPy.

8. **The fly controls; the code only perceives.** Computation may feed the
   fly stimuli (looming, gap, odour) but must never decide or force an
   action: no forced jumps, B holds, cooldown bypasses or long-jump
   selection. Controller modules (`bridge/controller_modules.py`) are
   `PerceptionModule`s that change what the circuit sees. Existing control
   rules that violate this are listed in `docs/CONTROL_AUDIT.md`, to be
   replaced by circuit or learned mechanisms.

## Every change ends with a video in `projects/<name>/runs/`

Not optional, and not only when asked. Any sprint that changes what the agent
does — a new gain, a new population, a new controller, a bug fix that alters
behaviour — finishes by recording a run and writing it to the project's
`runs/` folder (telemetry goes in `projects/<name>/telemetry/`; there is no
top-level `runs/` any more, and it is gitignored).

```
projects/<name>/runs/NNN_<short-slug>.mp4      e.g. projects/legacy/runs/004_shuffle_n20.mp4
```

Three-digit counter, never reuse a number, never overwrite an earlier run. The
point is a visual history we can scrub back through: when a later change makes
things worse, the previous video is the evidence of what "better" looked like.

Use `render.brain_panel.render_run(telemetry_df, frames_dir, "projects/<name>/runs/NNN_slug.mp4")`.
That composites the live-brain panel beside the emulator frames. The panel is
141,781 real soma positions from `somaLocation`, projected x (left-right)
against z (brain → nerve cord) — LC4 and LPLC2 light up in the optic lobes,
TTMn down in VNC segment T2, because that is where those cells actually are.

Alongside each video write `projects/<name>/runs/NNN_<slug>.md`: two or three lines saying what
changed, what the numbers were, and whether it got better or worse. When a run
compares controllers, record one video per controller with the same counter and
a suffix (`004a_real.mp4`, `004b_shuffled.mp4`, `004c_theta.mp4`).

**Then append an entry to `docs/RUNS.md`** — the project's running log, and the
first thing anyone reads. Always the same four fields, in this order:

```
## NNN — short name (`projects/<name>/runs/NNN_slug.mp4`)

**Setup.** What the circuit was, what changed from last time, the scalars.
**What happened.** The numbers. Survival, jumps, what it did on screen.
**What we learned.** The finding, including when the finding is "this failed
and here is why."
```

Append only. **Never edit an earlier entry to make it look better** — not even
the runs that were wrong, especially not those. Run 001 shipped a video of a
saturated circuit that looked convincing; that entry is why Diagnostic 4 exists.
A log that records only successes is a log that teaches nothing.

If a change produces no watchable behaviour — a pure analysis sprint — say so
and skip the video rather than recording a frozen screen.

**Video is ephemeral. Telemetry CSVs and the `.md`/`RUNS.md` notes are the
durable artifacts.** `.mp4`/`.png` are gitignored on purpose: every finding
in `docs/RUNS.md` is argued from a CSV number, never a frame, and a lost
video is cheap to re-render from its git-tracked CSV. Do not add git-lfs
for this alone; if a video must outlive one machine (a demo, a review),
decide then, against that need.

## Use the GPU

The machine has an NVIDIA GPU and it has been idle for this whole project.
Consider it for every new compute-heavy step. But port on evidence, not reflex:
measured on this workload, a naive port makes things **slower**.

**Where the GPU wins — use it:**

- The full 166,700-neuron network (8.4M synapses): ~9.6 ms/step on CPU, roughly
  an order of magnitude better on GPU. If we scale past the 1,255-neuron
  subgraph, port it.
- Anything batching hundreds of independent simulations as dense tensors.

**Struck: "per-neuron rendering in `render/brain_panel.py` is genuinely
GPU-shaped."** It wasn't (run 026). One `panel()` call was **8.4ms** against
a **16.7ms** real-time budget; the 141,781-point soma scatter was only
**2.6ms** of it. `_font()` reloading TTF files every frame cost **2.7ms**;
caching it brought `panel()` to **5.1ms** median with no GPU.

**Where it loses — don't:**

- The current 1,255-neuron step loop. One sparse matvec is **0.039 ms** on a
  single CPU core; a CUDA kernel launch is ~5–10 µs and a step needs ~6 ops, so
  the GPU floor is ~0.03–0.06 ms *before any arithmetic*. You would pay launch
  overhead to match what the CPU already does.
- Anything sequential in time. `h(t+1)` depends on `h(t)`, so the 30,000 steps
  in a Diagnostic-4 call cannot be batched across time. GPUs win on throughput;
  this is latency-bound.
- `nes-py`. It is a CPU emulator, sequential within a run, and sets a hard floor
  on any battery no matter how fast the network gets.

**The rule:** if a step is under ~1 ms on CPU *and* sequential, the GPU loses.
Benchmark both before committing a port, and put the numbers in the commit.

**Do these first — they beat a GPU port on this workload:**

1. **Flush denormals**, `h[h < 1e-30] = 0.0` after each update. Measured on
   the jump circuit (`scripts/denormal_probe.py`): **~3.2× under a realistic
   bursty trace, ~4.7× under sustained silence**, not the 84× once claimed
   (that number has no supporting code or RUNS.md entry). The jump circuit
   still doesn't flush: adding it re-baselines every golden and makes runs
   001-026 non-reproducible, so it needs its own dedicated sprint.
2. **Multiprocess across networks/runs** (~8× on this box). The 21 sweep
   networks and the 27 battery runs are fully independent. Keep
   `OMP_NUM_THREADS=1` per worker.
3. **Batch the gain grid as columns.** `g` is a scalar outside the matvec, so
   all 14 gains share one `W @ H` with H of shape (n, 14) instead of 14 separate
   matvecs. Measured 2.0×.

## Style

Python. Small, readable modules over one large file. Assert the verified
connectome numbers at load time and fail loudly if the data changed underneath
us. Comment the biology, not the syntax — a reader should learn why LPLC2
exists, not what a for loop does.

## Scope

Scope is set per sprint by the relevant `docs/SPEC_*.md`. Build only what
that spec covers.

## Testing (Arun, 2026-09-26)

Keep test runs proportional to the change. The full suites take many minutes.

- **Tool-only changes** (anything under `tool/`): run only the affected `tool/tests` files.
- **Changes outside `tool/`** (simulation, circuits, config, bridge, mario): run the full `tests/`, including the goldens.
- **Full `tool/tests`:** only when Arun asks, or once before a release.
