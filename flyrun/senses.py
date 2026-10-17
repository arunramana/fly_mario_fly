"""RAM -> looming and homing input (nb 08/09/13/15/19): Goomba, pipe face, pit.

All three threats feed the SAME detectors (LC4 <- |dtheta|, LPLC2 <- theta) through one channel:
the source with the largest theta wins the frame (logged as stim_src).

Pixels never reach the fly: a Goomba walking toward Mario does not grow on the NES
screen, so theta is synthesised from RAM distance (Mario's-eye view).
"""
from dataclasses import dataclass

import numpy as np


def theta_of(d, w):
    if d is None:
        return 0.0
    return float(2.0 * np.arctan(w / (2.0 * max(float(d), 1.0))))


@dataclass
class Loom:
    theta: float = 0.0
    dtheta: float = 0.0
    tau: float = np.nan   # geometric time-to-contact d / v_rel in frames (diagnostic only)
    src: str = "none"     # which threat won: goomba / pipe / pit / none
    dist: float = None    # distance (px) of that threat
    theta_noisy: float = None   # theta times the noise factor LPLC2 received (what a no-brain rule reads)


class Senses:
    """STIM_COMBINE="max": one threat channel, the largest-theta object wins (part 2).
    STIM_COMBINE="sum": every visible object adds its own theta and |dtheta| to the same
    LPLC2 / LC4 inputs, since all of them expand on the retina at once."""

    def __init__(self, knobs, masks, K, rng=None):
        self.k, self.m, self.K = knobs, masks, K
        self.rng = rng   # None = no sensor noise
        self.prev_d, self.prev_theta, self.prev_src = None, 0.0, "none"   # max mode
        self.prev = {}                                                      # sum mode: key -> (theta, dist)

    def _objects(self, mx, goombas, enemy_input, face, pit):
        """-> {key: (src, theta, dist)} for every object currently visible."""
        objs = {}
        if enemy_input:
            for slot, d in goombas:
                objs[("goomba", slot)] = ("goomba", theta_of(d, self.k.W_ENEMY), d)
        if self.k.PIPE_SENSE and face is not None:
            objs[("pipe", face.x)] = ("pipe", theta_of(face.x - mx, face.h), face.x - mx)   # nb 13
        if self.k.PIT_SENSE and pit is not None and pit.x - mx > 0:
            # INVENTED loom (nb 15): a pit has no face, so pretend its width subtends an angle
            objs[("pit", pit.x)] = ("pit", self.k.PIT_GAIN * theta_of(pit.x - mx, pit.w), pit.x - mx)
        return objs

    def look(self, mx, goombas, enemy_input=True, face=None, pit=None):
        """-> (input vector I, Loom). goombas: [(slot, d)] from env.threats_ahead."""
        objs = self._objects(mx, goombas, enemy_input, face, pit)
        if self.k.STIM_COMBINE == "sum":
            th = sum(o[1] for o in objs.values())
            dth_abs = sum(abs(o[1] - self.prev.get(k, (0.0, None))[0]) for k, o in objs.items())
            top = max(objs.items(), key=lambda kv: kv[1][1]) if objs else None
            src = top[1][0] if top else "none"
            dist = top[1][2] if top else None
            pd_ = self.prev.get(top[0], (0.0, None))[1] if top else None
            v_rel = np.nan if (pd_ is None or dist is None) else float(pd_ - dist)
            self.prev = {k: (o[1], o[2]) for k, o in objs.items()}
            dth_signed = dth_abs
        else:
            cands = {o[0]: (o[1], o[2]) for k, o in sorted(objs.items(), key=lambda kv: -kv[1][2])}
            # nearest goomba only in max mode: later (nearer) entries overwrite earlier ones
            src = max(cands, key=lambda s_: cands[s_][0]) if cands else "none"
            th, dist = cands[src] if cands else (0.0, None)
            dth_signed = th - self.prev_theta
            dth_abs = abs(dth_signed)
            v_rel = np.nan if (self.prev_d is None or dist is None or src != self.prev_src)                 else float(self.prev_d - dist)
            self.prev_d, self.prev_theta, self.prev_src = dist, th, src
        tau = dist / v_rel if (dist is not None and np.isfinite(v_rel) and v_rel > 0.05) else np.nan

        I = np.zeros(self.K)
        sig = self.k.SENSOR_NOISE if self.rng is not None else 0.0
        th_factor = 1.0
        for name, val in (("LC4_R", dth_abs), ("LPLC2_R", th)):
            idx = self.m[name]
            n = int(idx.sum()) if self.k.NOISE_MODE == "neuron" else 1
            noise = 1.0 + sig * self.rng.standard_normal(n) if sig > 0 else 1.0
            if name == "LPLC2_R":
                th_factor = float(np.mean(noise))
            I[idx] = val * noise   # LC4 reads how fast the angle grows, LPLC2 how big it looks
        I[self.m["LC10a_R"]] = self.k.HOME_R   # homing landmark cue
        return I, Loom(th, dth_signed, tau, src, dist, th * th_factor)
