"""The brain panel of the lite video: the real somata of the neurons the fly runs on, glowing with their group's activity, and the
index of groups with a bar each. The full tool draws the same picture at 1080p with PIL fonts; this one is made at about 0.4 of
that size with numpy and OpenCV only, from a small file in the bundle (`panels/<brain>.npz`), so the server needs no MaleCNS data.

    export(dest, specs)     (bundle builder, needs the data) write one npz per brain
    Panel.load(path)        (the server) the panel of one brain; .draw(rates, height) -> an RGB picture
Brightness of a group = its rate against the largest rate it has had so far in this run (never below FLOOR).
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

PANEL_W = 276                       # px; the full tool's content column (688 px incl. margin) at about 0.4
FLOOR = 0.02                        # a rate of ~1e-3 must not look lit (the full tool uses the same floor)
ROW_H = 13
GREY, DIM, WHITE = (150, 150, 146), (95, 95, 92), (235, 235, 235)


def _ascii(s: str) -> str:
    return s.encode("ascii", "replace").decode().replace("?", "-")


def export(dest: Path, specs: list) -> list:
    """Write panels/<brain>.npz for each mechanism set in `specs` (deduplicated by brain name). Returns the names."""
    from fly_mario_fly.render.data import BrainData
    from fly_mario_fly.render.draw import BrainPanel, COL_W, COL_X, TEXT_Y
    from fly_mario_fly.runner import brain_display_for, brainstore

    x0, x1 = COL_X - 24, COL_X + COL_W + 24
    f = PANEL_W / (x1 - x0)
    cloud_h = int(round(TEXT_Y * f))
    out, names = Path(dest) / "panels", []
    out.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        name = brainstore.spec_key(spec)
        if name in names:
            continue
        bd = brain_display_for(spec)
        disp = bd.display
        data = BrainData(all_xyz=bd.all_xyz, xyz={g: d.xyz for g, d in bd.groups.items()}, colours={g: d.rgb for g, d in bd.groups.items()},
                         other_xyz=bd.other_xyz, other_colour=tuple(int(bd.other_colour[i:i + 2], 16) for i in (1, 3, 5)),
                         index=[(r["label"], r["role"], list(r["groups"])) for r in disp["index"]], counts={g: d.count for g, d in bd.groups.items()},
                         big=frozenset(disp["big"]), n_neurons=bd.n_neurons)
        panel = BrainPanel(data)
        bg = cv2.resize(panel._bg_u8[:TEXT_Y, x0:x1], (PANEL_W, cloud_h), interpolation=cv2.INTER_AREA).astype(np.float32)
        bg = np.clip(bg * 2.5, 0, 255).astype(np.uint8)                      # averaging a sparse cloud down dims it: bring it back
        groups = [g for g in data.xyz if len(panel.px[g])]
        pts, grp = [], []
        for i, g in enumerate(groups):
            p = np.round((panel.px[g] - [x0, 0]) * f).astype(np.int16)
            pts.append(p)
            grp.append(np.full(len(p), i, np.int16))
        other = np.round((panel.other - [x0, 0]) * f).astype(np.int16) if len(panel.other) else np.zeros((0, 2), np.int16)
        rows = [(_ascii(lab), _ascii(role), [g for g in gs if g in groups]) for lab, role, gs in data.index]
        rows = [r for r in rows if r[2]]
        np.savez_compressed(
            out / f"{name}.npz", bg=bg, pts=np.concatenate(pts) if pts else np.zeros((0, 2), np.int16), grp=np.concatenate(grp) if grp else np.zeros(0, np.int16),
            groups=np.array(groups), colours=np.array([data.colours[g] for g in groups], np.uint8), counts=np.array([data.counts.get(g, 1) for g in groups]),
            big=np.array([g in data.big for g in groups]), other=other, other_col=np.array(data.other_colour, np.uint8),
            rows=np.array(json.dumps(rows)), n_neurons=np.array(data.n_neurons))
        names.append(name)
    return names


class Panel:
    def __init__(self, z):
        self.bg = z["bg"]
        self.groups = [str(g) for g in z["groups"]]
        self.colours = z["colours"].astype(np.float32)
        self.n_neurons = int(z["n_neurons"])
        self.rows = [(lab, role, [self.groups.index(g) for g in gs]) for lab, role, gs in json.loads(str(z["rows"]))]
        self.counts = z["counts"].astype(np.float32)
        h, w = self.bg.shape[:2]
        pts, grp = z["pts"].astype(np.int32), z["grp"].astype(np.int32)
        # every circuit neuron is a 2 x 2 block (a one-pixel point is invisible at this size)
        extra = [(pts + d, grp) for d in ((1, 0), (0, 1), (1, 1))] if len(pts) else []
        self.pts = np.concatenate([pts] + [e[0] for e in extra]) if len(pts) else pts
        self.grp = np.concatenate([grp] + [e[1] for e in extra]) if len(pts) else grp
        keep = (self.pts[:, 0] >= 0) & (self.pts[:, 0] < w) & (self.pts[:, 1] >= 0) & (self.pts[:, 1] < h) if len(pts) else np.zeros(0, bool)
        self.pts, self.grp = self.pts[keep], self.grp[keep]
        self.base = np.zeros((h, w, 3), np.float32)                            # the relays: faint, constant
        other = z["other"].astype(np.int32)
        if len(other):
            other = other[(other[:, 0] >= 0) & (other[:, 0] < w) & (other[:, 1] >= 0) & (other[:, 1] < h)]
            self.base[other[:, 1], other[:, 0]] = z["other_col"].astype(np.float32) * 0.28
        self.top = np.zeros(len(self.groups), np.float32) + FLOOR               # the largest rate each group has had
        self.bgf = self.bg.astype(np.float32)

    @classmethod
    def load(cls, path) -> "Panel":
        with np.load(path, allow_pickle=False) as z:
            return cls(z)

    def levels(self, rates: dict) -> np.ndarray:
        """Brightness 0..1 per group this frame (and remember each group's largest rate)."""
        r = np.array([rates.get(g, 0.0) for g in self.groups], np.float32)
        self.top = np.maximum(self.top, r)
        return np.clip(r / self.top, 0, 1)

    def draw(self, rates: dict, height: int) -> np.ndarray:
        lv = self.levels(rates)
        h, w = self.bg.shape[:2]
        bright = 0.28 + 0.72 * lv ** 0.7
        layer = self.base.copy()
        if len(self.pts):
            layer[self.pts[:, 1], self.pts[:, 0]] = self.colours[self.grp] * bright[self.grp, None]
        glow = np.clip(self.bgf + layer + cv2.GaussianBlur(layer, (0, 0), 1.6) * 2.0, 0, 255).astype(np.uint8)
        out = np.zeros((height, w, 3), np.uint8)
        out[:h] = glow
        y = h + 14
        cv2.putText(out, "LIVE BRAIN", (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 1, cv2.LINE_AA)
        cv2.putText(out, f"{self.n_neurons} neurons, real somas", (6, y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.32, GREY, 1, cv2.LINE_AA)
        cv2.putText(out, "brightness = activity", (6, y + 27), cv2.FONT_HERSHEY_SIMPLEX, 0.32, DIM, 1, cv2.LINE_AA)
        y += 44
        for label, role, idx in self.rows:
            if y + ROW_H > height:
                break
            n = self.counts[idx]
            a = float(np.dot(lv[idx], n) / n.sum())
            col = tuple(int(c) for c in self.colours[idx[0]])
            cv2.circle(out, (9, y - 3), 3, col, -1, cv2.LINE_AA)
            cv2.putText(out, label, (17, y), cv2.FONT_HERSHEY_SIMPLEX, 0.32, WHITE, 1, cv2.LINE_AA)
            cv2.putText(out, role[:14], (62, y), cv2.FONT_HERSHEY_SIMPLEX, 0.30, GREY, 1, cv2.LINE_AA)
            cv2.rectangle(out, (w - 66, y - 7), (w - 6, y - 1), (52, 52, 50), 1)
            if a > 0.01:
                cv2.rectangle(out, (w - 66, y - 7), (w - 66 + int(60 * a), y - 1), col, -1)
            y += ROW_H
        return out
