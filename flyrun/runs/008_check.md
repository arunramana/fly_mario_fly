# Part 7 check  (commit 8f41622562, config 289b3d51cb29, W 5c57f81f5b1d, python 3.12.6, pip-freeze ba762955ba14)

## 1. Config validation

| check                                     | result |
|-------------------------------------------|--------|
| yaml validates                            | PASS   |
| W sha256 matches the file                 | PASS   |
| HOLDOUT == Part 6b (episodes4.HOLDOUT)    | PASS   |
| knob ranges == Part 6b (genome.FLY)       | PASS   |
| fitness constants == knobs.py             | PASS   |
| every restart has an explicit CMA seed    | PASS   |
| warm_r3: u == evo6/real gen.csv restart 3 | PASS   |
| warm_r3: yaml decode == genome.decode     | PASS   |

## 2. Part 6b HOLDOUT reproduction

| restart | mean_max_x | expected | flags | expected | max_x list identical | result |
|---------|------------|----------|-------|----------|----------------------|--------|
| warm_r3 | 1405.1     | 1405.1   | 1     | 1        | True                 | PASS   |

## 3. Constraints on HOLDOUT, per episode (silence is one run per genome)

**warm_r3**  genome {'G': 0.7110222543106262, 'TTMN_THRESH': 0.2953262065484157, 'A_HOLD': 18, 'COOLDOWN': 2, 'HOME_R': 1.684046284930957, 'PIT_GAIN': 1.3598899302684715}  silence A_frac = 0.000  -> all constraints on every episode: PASS

| noop | seed | sigma | max_x | end         | silence | first A at threat | blind<=8 |
|------|------|-------|-------|-------------|---------|-------------------|----------|
| 3    | 101  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 11   | 102  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 25   | 103  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 33   | 104  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 41   | 105  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 3    | 101  | 0.05  | 3161  | flag        | ok      | ok (24px)         | ok (8)   |
| 11   | 102  | 0.05  | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (5)   |
| 25   | 103  | 0.05  | 1221  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 33   | 104  | 0.05  | 1129  | pit         | ok      | ok (26px)         | ok (6)   |
| 41   | 105  | 0.05  | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (5)   |

## 4. TRAIN timing (r3 genome, 6 TRAIN episodes + 1 silence run)

wall for one evaluation on 12 workers: 28.6s;  per-job seconds: 26.5, 15.0, 15.1, 15.1, 14.5, 15.1, 3.4
TRAIN: mean_max_x 1415, flags 0/6, all constraints ok: True

One generation = 16 genomes x 7 jobs = 1677 worker-s (job speed measured with up to 12 concurrent workers). Estimates assume perfect packing:

| stage                                | generations | wall @12 workers | wall @8 workers |
|--------------------------------------|-------------|------------------|-----------------|
| 7d short                             | 30          | 70 min           | 105 min         |
| 7e full (upper bound, no early stop) | 320         | 12.4 h           | 18.6 h          |

7e cap 3 h: binds

**check: PASS** (constraint failures on r3/r2 are information, not check failures)
