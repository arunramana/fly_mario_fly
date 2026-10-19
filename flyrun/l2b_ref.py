"""L2b: button-identity reference. python -m flyrun.l2b_ref <tag> [1-1|1-2]  -> runs/L2b_ref_<level>_<tag>.csv (arm A, noop 0, sigma 0; the S3e / L2 arm A episode)."""
import os
import sys

os.environ["FLYRUN_LEVEL"] = sys.argv[2] if len(sys.argv) > 2 else "1-1"
from pathlib import Path

from . import c1_run as C

ROOT = Path(__file__).resolve().parent


def main():
    tag, lv = sys.argv[1], os.environ["FLYRUN_LEVEL"]
    s, df = C.episode("A", dict(noop_start=0, seed=0, sigma=0.0))
    C.trace_cols(df).to_csv(ROOT / "runs" / f"L2b_ref_{lv}_{tag}.csv", index=False, lineterminator="\n")
    print(lv, tag, "max_x", s["max_x"], "flag", s["flag_get"], s["end_reason"], s["cause"], "frames", s["frames"])


if __name__ == "__main__":
    main()
