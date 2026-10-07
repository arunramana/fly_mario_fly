# SPEC: redesign phase 6c part 2 -- why multiprocessing was backwards

## Measured (E1 real arm, seeds 9500-9519, max 600 frames, idle machine, 16 logical CPUs, L2 9.5 MB, L3 24 MB)
Single process: 0.83 ms/network step (10 steps/frame). Per episode: network load+W build 0.11 s, degree shuffle 0.10 s,
Brain() 0.016 s, scene 0.39 s, against 8-13 s of simulation (cProfile: csr_matvec 38%, RNG normal 14%, emulator 13%).
So rebuild is ~3% of an episode, not the bottleneck. W = 612,566 nnz = 7.4 MB; peak RSS 159 MB/worker (not memory-limited).
Matvec micro-benchmark, N processes at once: private W 0.48 -> 0.86 ms at 8 (1.8x slower); shared W 0.47 -> 0.60 ms (1.26x);
a 400x400 cache-resident control stays at 0.006-0.007 ms (so not clocks, E-cores or thread oversubscription).
Thread env: BLAS/MKL/OpenMP caps were set inside the job (after numpy loaded); the sparse matvec is single-threaded anyway.

## Verdict
Memory/cache contention on W (not rebuild, not oversubscription): N private copies of a 7.4 MB matrix exceed the shared L3.
Duplication is the cause in the specific sense that shared pages are one copy in L3.

## Change
- new `brain/workers.py`: `WorkerPool` (parent loads network once; real network and requested shuffled variants live in
  `multiprocessing.shared_memory`; CSR built over the views without copy; thread caps exported before spawn).
- `brain/builder.py`: `install_shared` hook; `load_or_build` / `BuiltNetwork.shuffled` return shared networks inside a worker
  only. Serial path untouched. Shuffled variants not listed fall back to a private build (correct, just slower).
- `e1, baseline, e2a, goal_eval, dose_response, evaluation`: `mp.Pool` replaced by `WorkerPool`; CLI flags unchanged.
- `scripts/bench_workers.py`: the timing table. `tests/conftest.py`: fast/slow markers. CLAUDE.md corrected.
- No numerics change: same arrays, same seeds; `tests/test_workers.py` checks serial == parallel for real, degree and class arms.
