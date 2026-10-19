"""AV1 step 5 diagnosis: where the back-up presses happen on 1-1 (E1 genome, sour + headroom on). python -m flyrun.av1_backups -> runs/AV1_11_backups.csv"""
import json
import sys

import pandas as pd

from . import av1_run as R


def main():
    rows = []
    for noop, seed, sg in ((3, 101, 0.0), (33, 105, 0.05), (11, 107, 0.05)):
        ep = dict(noop_start=noop, seed=seed, sigma=sg)
        s, df, _ = R.episode("W_steer_jo_orn_sour.npy", 1, 1, ep)
        R.trace(df).to_csv(R.ROOT / "runs" / f"AV1_11_both_{noop}_{sg}_trace.csv", index=False, lineterminator="\n")
        b = df.backup.fillna(0).astype(int)
        start = (b == 1) & (b.shift(1, fill_value=0) == 0)
        for i in df.index[start]:
            j = i
            while j + 1 < len(df) and b[j + 1] == 1:
                j += 1
            r = df.loc[i]
            rows.append(dict(noop=noop, sigma=sg, frame=int(r.frame), x=int(r.x), frames=j - i + 1, air=int(r.air), sour_theta_deg=round(float(__import__('numpy').degrees(r.sour_theta)), 1), mdn=round(float(r.mdn), 3),
                             loom=str(r.threat_kind), theta_deg=round(float(__import__('numpy').degrees(r.theta)), 1), headroom=r.get("headroom_factor"), enemy_slots=r.get("enemy_slots", "")))
        print(noop, sg, s["end_reason"], s["cause"], s["max_x"], flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(R.ROOT / "runs" / "AV1_11_backups.csv", index=False, lineterminator="\n")
    pd.set_option("display.width", 250)
    print(out.to_string())


if __name__ == "__main__":
    main()
