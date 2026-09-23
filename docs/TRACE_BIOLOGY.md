# Eligibility trace — what the biology actually supports

Literature check run before phase 6, so that `tau` is chosen from evidence
rather than tuned against a null result. **Conclusion: the trace mechanism we
were about to build cannot span the gap we were about to ask it to span — and
the fix is to change where reward is delivered, not to lengthen the trace.**

---

## Two mechanisms, two timescales

The fly has *two different* things that get called an eligibility trace, and
they operate an order of magnitude apart.

### 1. The synaptic window — ~1–2 s, gone by 6 s

Handler et al. (2019, *Cell*) measured KC→MBON plasticity directly while varying
the interval between Kenyon cell activation and dopaminergic neuron activation:

- Bidirectional modulation over a **narrow window, roughly 1–2 s wide** around
  coincidence.
- Significant plasticity at ISIs of **−1.2 s, 0 s and +0.5 s**.
- Order determines sign: forward vs backward pairing produce depression vs
  potentiation — the same synapse, opposite outcomes.
- **Extending to 6 s produced minimal plasticity.**

This is the eligibility trace proper: the synaptic tag that dopamine acts on.

### 2. The behavioural bridge — up to ~25 s

Olfactory *trace* conditioning (Galili et al., 2011, *J. Neurosci.*) separated
odour offset from shock onset by a real gap:

| gap | learning |
|---|---|
| 5 s | significant (p < 0.001) |
| 10 s | significant (p < 0.001) |
| 15 s | significant (p < 0.001) |
| 20 s | significant (p = 0.03) |
| 25 s | significant (p = 0.03) |
| **30 s** | **not significant (p = 0.46)** |

Flies bridge gaps far longer than the synaptic window allows. **That gap is
carried by something else** — a sustained stimulus representation (persistent KC
activity and slower cellular traces), not by a longer synaptic tag. The tag
still closes in ~1–2 s; what changes is that the *stimulus* is still present in
the circuit when dopamine arrives.

---

## Mapping onto Mario

SMB runs at 60 fps. From 025's cascade measurement: commitment at frame ~148,
death at frame 406 in one run and 689 in another.

- decision → consequence: **258 to 541 frames = ~4.3 to ~9 seconds**

Against the two mechanisms:

| mechanism | window | spans a 4–9 s gap? |
|---|---|---|
| KC→MBON synaptic tag | 1–2 s, negligible by 6 s | **no** |
| sustained-representation bridge | up to ~25 s | yes |

**A synaptic eligibility trace structurally cannot carry episode-end reward
back to the decision that caused it.** Setting `tau ≈ 5 s` to make it reach
would be inventing a fly synapse that does not exist — scaffolding of exactly
the kind this project has spent 27 sprints trying not to accumulate.

---

## The design consequence

**Deliver reward at the event, not at the end of the episode.**

This is what the animal actually experiences. A fly never receives "you died
nine seconds later." It receives sugar on the proboscis or a shock to the legs,
*now*. Reinforcement in every one of these paradigms is proximal; the long
intervals in trace conditioning are between the **cue** and the reinforcer, not
between a behaviour and a delayed outcome.

Mario supplies proximal events directly:

- mushroom collected → appetitive, immediate (PAM)
- took damage / shrank → aversive, immediate (PPL1)
- enemy stomped → appetitive, immediate
- `?` block hit → appetitive, immediate

Every one of these lands inside the 1–2 s window, so `tau` in the range
**60–120 frames** is both biologically correct and sufficient. No invented
constant, no stretching.

### What this retires

025's cascade sensitivity — one frame of difference producing 283 frames of
divergence — was alarming **only under episode-end credit assignment**. With
event-proximal reward, the trace never has to attribute a death to a decision
nine seconds earlier, so the cascade stops being a credit-assignment problem. It
remains interesting as a statement about the system's chaos, but it does not
constrain the learning design.

### A separation that was being blurred

`Fitness` and `DopamineSignal` are not the same object and must not be wired
together:

- **`Fitness`** — episode-level, weighting points, distance and time. For
  *evaluation*: judging runs, and later driving scalar search (CMA-ES over the
  49 parameters). Never touches synapses.
- **`DopamineSignal`** — event-level, immediate, compartment-specific (PAM
  reward vs PPL1 punishment). The only thing the mushroom body sees.

Connecting episode fitness to dopamine would reintroduce exactly the delayed-
credit problem the biology says the mechanism cannot solve.

---

## What to build in phase 6

1. `EligibilityTrace` with `tau` in the range **60–120 frames**, bounded in
   `SCALARS.md` at that range with this document as the provenance — **measured,
   not invented**, which would be the first such scalar in the project.
2. Event detection from RAM: mushroom collected, damage taken, enemy stomped,
   `?` block hit. These are already decodable.
3. `DopamineSignal` routing events to PAM (appetitive) vs PPL1 (aversive)
   compartments.
4. Sign check: forward vs backward pairing produce *opposite* plasticity in the
   real animal. Verify the implementation reproduces that, since it is a strong
   and cheap test that the rule is the fly's rule and not a generic delta rule.

**Open and unresolved:** whether the two discriminable classes on 1-1 (mushroom
appetitive, enemy aversive) are encountered often enough within one episode for
any learning to be measurable. Count the events per episode before building —
if a run contains two rewarded events, there is nothing to learn from regardless
of how correct the mechanism is.

---

## Sources

- Handler et al. (2019). *Distinct Dopamine Receptor Pathways Underlie the
  Temporal Sensitivity of Associative Learning.* Cell 178(1): 60–75.
  https://pubmed.ncbi.nlm.nih.gov/31230716/
- Galili et al. (2011). *Olfactory Trace Conditioning in Drosophila.*
  J. Neurosci. 31(20): 7240. https://www.jneurosci.org/content/31/20/7240
