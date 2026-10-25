"""python -m fly_mario_fly.rules validate | list"""
import argparse
import sys

from fly_mario_fly.rules.catalogue import RULES


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fly_mario_fly.rules")
    ap.add_argument("cmd", choices=["validate", "list"])
    a = ap.parse_args(argv)
    if a.cmd == "list":
        for r in RULES:
            print(f"{r.id:3s} {r.kind:7s} {r.text}\n    enforced by: {r.enforced_by}")
        return 0
    from fly_mario_fly.rules.validate import validate_all
    bad = validate_all()
    for v in bad:
        print(v, file=sys.stderr)
    print(f"{len(bad)} rule violation(s)" if bad else "all plug-ins comply with the rules")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
