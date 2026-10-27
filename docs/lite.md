# The lite server

A small server that does one thing: **settings in, a run, one short video out.** There are no downloads, no evolution, no saved
moments and no saving of flies, and the Fly tab offers the `blank` fly only. It is for a public page where people can see what the
tool does without installing anything. The full tool is unchanged.

```
browser (GitHub Pages)  ->  POST /runs  ->  lite server  ->  worker process: the same runner.Run as the full tool
                            GET /runs/id    queue + cache      -> every 4th frame -> mp4 (15 fps, H.264)
                            GET /videos/id.mp4  (immutable: a CDN can serve repeats)
```

The run is the full tool's run, frame for frame: the same buttons and the same run hash (a test checks this). Only the picture is
lighter: 15 fps instead of 60 and 788 x 504: the brain panel (the fly's real neurons at their somas, glowing with their group's activity, and the index of groups with a bar each), the game at x2 with the sense boxes, and a strip of the buttons held. The panel is drawn from `panels/*.npz` in the bundle (about 0.3 MB), so the server still needs no data; brightness is a group's rate against the largest rate it has had so far in the run.

## Run it on your machine

```bash
export FLY_MARIO_FLY_DATA=/path/to/data                       # once, on a machine that has the data and the brains built
python -m fly_mario_fly.lite.bundle ./bundle                  # ~40 MB: the brains, pictures and the page's static answers
unset FLY_MARIO_FLY_DATA                                      # the server needs no data
FMF_LITE_BUNDLE=./bundle python -m fly_mario_fly.lite --port 8080
cd web && VITE_API_URL=http://127.0.0.1:8080 npm run dev:lite
```

`--levels 1-1,1-2` (default) chooses which levels the bundle and server offer. Icons come from the full tool's icon maker: if one is
missing the builder says so and the page shows a plain square.

## What it limits (and why)

| Setting (`FMF_LITE_*`) | Default | Why |
| --- | --- | --- |
| `BUNDLE` | `bundle` | the folder `lite.bundle` wrote |
| `CACHE` | `cache` | where finished videos are kept |
| `CACHE_MB` | 300 | the cache never grows past this; the least recently used video goes first |
| `WORKERS` | 1 | runs at the same time; each uses one CPU core for about 12 s |
| `QUEUE` | 12 | runs waiting or running; more is refused with 503 |
| `RATE` | 6 | new runs per client per minute (429); cached runs are free |
| `MAX_FRAMES` | 3600 | game frames per run (one minute of play) |
| `STRIDE` | 4 | every 4th frame is drawn: 15 fps |
| `CRF` | 30 | video quality: higher is smaller |
| `BUDGET_S` | 90 | a run that takes longer is stopped and reported as failed |
| `KEEP_BRAINS` | 2 | brains held in memory (each is 3-7 MB on disk) |
| `LEVELS` | `1-1,1-2` | levels offered |
| `CORS` | localhost:5173 | comma-separated page origins allowed to call it (put your GitHub Pages origin here) |
| `TRUST_PROXY` | 0 | `1` behind Fly.io / Cloud Run: take the client address from `X-Forwarded-For` |

Requests are cut down to a canonical form before anything is cached: names sorted, sliders rounded to three decimals, noise off, a
fixed seed (101) and three idle frames at the start. Two people who set the same fly and scene get **the same run and the same
cached video**, which is what keeps a busy day cheap. A scene that needs a different game (a saved moment, another start) is refused.

## What it costs to run (measured, one 1-1 flag run of 2348 frames)

| | |
| --- | --- |
| time | about 12-14 s on one core (the plain run without video: 10 s) |
| memory | the server about 90 MB, the worker about 110 MB: fits a 512 MB machine |
| video | about 1.3 MB for 39 s of play |
| cached answer | a few milliseconds |
| bundle on disk | about 40 MB |

`tests/test_lite_perf.py` keeps these honest with budgets about three times looser (scale them on a slow machine with
`FMF_PERF_SLACK=2`): the run time, the peak memory of a worker with no data folder, the video size, the cost of the video over the
plain run, the cache byte limit, and the time of a cached answer. `tests/test_lite_*.py` also check the settings, cache, queue,
rate limit and every endpoint with a fake engine, so they run without the data.

## Deploy

- **The page:** `cd web && VITE_API_URL=https://<your-server> npm run build:lite`, then publish `web/dist` (for a GitHub Pages
  project site set `VITE_BASE=/<repo>/` first). The lite page keeps its route after a `#`, so Pages needs no rewrite rules.
- **The server:** `deploy/lite/Dockerfile` (build from the repo root, with the bundle at `deploy/lite/bundle`). Any host that runs a
  container works: one 512 MB machine with a small volume for the cache. Set `FMF_LITE_CORS` to the page's origin.
- **Videos:** the video route is cache-friendly (`immutable`, one year). Put a CDN (Cloudflare) in front of the server and repeats
  never reach it.

The Nintendo sprites and level data in the bundle are the same ones the repository already carries; see the README note on licensing.
