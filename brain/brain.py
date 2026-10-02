# What this file does, in plain English:
# The fly brain as the game sees it: one network, one neuron model. The only way
# to put activity into it is to hand it a stimulus for sensory-tier neurons, and
# anything addressed to another neuron is refused. Each game frame it runs ten
# network steps and reports how active each output group is. Every result it
# produces carries a stamp: how the network was built, which calibration file,
# and which mechanisms were attached.
"""brain/brain.py -- docs/SPEC_brain_core.md section 4.

The guard rail (REDESIGN_PLAN 3.6): `_current` is private and written only by `apply`/`stimulate`, which check every
id against the manifest's sensory tier. There is no other method that adds current to a neuron. Membrane noise
(`Calibration.noise_sigma`) is the neurons' own intrinsic fluctuation, not an input, and is the same for the shuffled
twin. Reading (`Readout`) never changes the state.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from brain.builder import BuiltNetwork
from brain.calibration import Calibration
from brain.manifest import OUTPUT, SENSORY, Manifest
from brain.mechanisms import Mechanism, Stimulus
from fly.network.dynamics import NoiseConfig
from fly.network.integrator import Integrator
from fly.network.network import Network


class StimulusError(ValueError):
    """Raised when a stimulus names a neuron that is not in the manifest's sensory tier."""


@dataclass
class Readout:
    """One frame of output activity (mean over the frame's substeps, Hz). `rates[(population, side)]`."""
    rates: dict[tuple[str, str], float]
    gf_spiked: bool
    gf_membrane: float
    frame: int = 0

    def pooled(self, population: str) -> float:
        return float(np.mean([v for (p, _), v in self.rates.items() if p == population]))

    def side(self, population: str, side: str) -> float:
        return self.rates[(population, side)]


class Brain:
    def __init__(self, network: BuiltNetwork, calibration: Calibration, manifest: Manifest | None = None,
                 seed: int = 0, calibration_hash: str | None = None):
        real_hash = network.build_hash() if network.twin_of is None else network.twin_of["real_hash"]
        if calibration.network_hash != real_hash:
            raise ValueError(f"calibration was derived on network {calibration.network_hash}, this is {real_hash}: "
                             "re-run brain.calibrate")
        self.network, self.cal = network, calibration
        self.calibration_hash = calibration_hash or Calibration.file_hash()
        self.manifest = manifest or Manifest()
        self.mechanisms: list[Mechanism] = []
        self._sensory = np.sort(np.concatenate(
            [network.ids[network.pops[n]] for n in self.manifest.names(SENSORY)]))
        integ = Integrator(alpha=calibration.alpha, clip=calibration.clip_hz, spike_idx=network.pops["GF"],
                           spike_threshold=calibration.gf_threshold, spike_amp=calibration.spike_amp_hz)
        integ.refractory_steps = calibration.refractory_steps
        self._net = Network(network.W, integ, g=calibration.g)
        self._out = {}
        for name in self.manifest.names(OUTPUT):
            idx = network.pops[name]
            for s in ("L", "R"):
                self._out[(name, s)] = idx[network.side[idx] == s]
        self.reset(seed)

    # ---- stimulus API: the only way in ------------------------------------------------------------------------
    @property
    def sensory_ids(self) -> np.ndarray:
        return self._sensory

    def attach(self, mechanism: Mechanism) -> None:
        unknown = [p for p in mechanism.populations if p not in self.manifest.names(SENSORY)]
        if unknown:
            raise StimulusError(f"{mechanism.name}: {unknown} are not sensory-tier populations")
        self.mechanisms.append(mechanism)

    def apply(self, stimulus: Stimulus) -> None:
        self.stimulate(stimulus.body_ids, stimulus.values)

    def stimulate(self, body_ids, values) -> None:
        """Add drive for the next frame to sensory-tier neurons. Any other id raises and nothing is added."""
        body_ids = np.asarray(body_ids, dtype=np.int64)
        values = np.broadcast_to(np.asarray(values, dtype=np.float64), body_ids.shape)
        ok = np.isin(body_ids, self._sensory)
        if not ok.all():
            raise StimulusError(f"{int((~ok).sum())} of {len(body_ids)} ids are not in the manifest's sensory tier")
        np.add.at(self._current, self.network.local(body_ids), values)

    # ---- dynamics ----------------------------------------------------------------------------------------------
    def reset(self, seed: int = 0) -> None:
        """Rest state (all zero) and a fresh noise stream."""
        net = self._net
        net.h[:] = 0.0
        integ = net.integrator
        integ.mem[:] = 0.0
        integ._refractory_left[:] = 0
        integ.just_spiked = np.zeros(len(integ.spike_idx), dtype=bool)
        self._current = np.zeros(self.network.n_neurons)
        self._noise = NoiseConfig(self.cal.noise_sigma, np.random.default_rng(seed))
        self._frame = 0

    def step_frame(self) -> Readout:
        """Hold the stimulus for `substeps` network steps, clear it, and read the outputs."""
        acc = {k: 0.0 for k in self._out}
        spiked, mem = False, 0.0
        for _ in range(self.cal.substeps):
            h = self._net.step(self._current, noise=self._noise)
            for k, idx in self._out.items():
                acc[k] += h[idx].mean()
            spiked |= bool(self._net.just_spiked.any())
            mem = max(mem, float(self._net.integrator.mem.max()))
        self._net.flush_denormals()
        self._current = np.zeros(self.network.n_neurons)
        self._frame += 1
        return Readout({k: v / self.cal.substeps for k, v in acc.items()}, spiked, mem, self._frame)

    # ---- the record --------------------------------------------------------------------------------------------
    def stamp(self) -> dict:
        """Attached to every result: build rule, calibration hash, mechanism list (and the twin's provenance)."""
        return {"build_rule": self.network.rule, "build_hash": self.network.build_hash(),
                "neurons": self.network.n_neurons, "edges": self.network.n_edges,
                **self.network.edge_report(),
                "calibration_hash": self.calibration_hash, "mechanisms": [m.name for m in self.mechanisms],
                "shuffled": self.network.twin_of}
