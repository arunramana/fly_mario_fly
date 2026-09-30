# What this file does, in plain English:
# Turns a normal project configuration into the "honest fly" one. When bio_strict is on it
# switches off everything that hands the fly an answer (the jump and pit currents, hand-coded
# control rules), sets biologically scaled firing limits and refractory periods, and makes the
# jump muscle respond only to a sudden rise in activity. Nothing else changes.
"""config/bio_strict.py -- docs/SPEC_bio_strict.md phases 2-3: `effective(config)` is what FullPolicy runs."""

from __future__ import annotations

import dataclasses

from config.params import (ControlRules, Dnp01RefractoryParams, Dnp02RefractoryParams, PagePerceptionParams)


def effective(config):
    """`config` itself when bio_strict is off; otherwise a copy with the strict settings applied. Raises if the project
    has no MotorDirect module: without one a button could only be pressed by the hand-coded hold/cooldown counters."""
    if not config.bio_strict:
        return config
    bio = config.bio
    if config.modules.motor_direct is None:
        raise ValueError("bio_strict needs the motor_direct module (buttons may only come from the muscle model)")
    m = config.modules
    modules = dataclasses.replace(
        m,
        page_perception=PagePerceptionParams(),                      # page-corrected distance is always on
        gap_ahead=None,                                                # pits are unperceived: no connectome route
        wall_ahead=(dataclasses.replace(m.wall_ahead, takeoff_gain=0.0) if m.wall_ahead is not None else None),
        dnp01_refractory=Dnp01RefractoryParams(refractory_steps=bio.refractory_steps),
        dnp02_refractory=Dnp02RefractoryParams(refractory_steps=bio.refractory_steps),
        motor_direct=dataclasses.replace(m.motor_direct, adapt_frames=bio.adapt_frames, buttons=False),
    )
    return dataclasses.replace(
        config,
        network=dataclasses.replace(config.network, clip=bio.clip_hz),
        jump=dataclasses.replace(config.jump, spike_amp=bio.spike_amp_hz),
        takeoff=dataclasses.replace(config.takeoff, gap_gain=0.0),       # no current onto DNp01 from the tile map
        rules=ControlRules(**{f.name: False for f in dataclasses.fields(ControlRules)}),
        scenario=dataclasses.replace(config.scenario, graded_pit_response=False),
        modules=modules,
    )
