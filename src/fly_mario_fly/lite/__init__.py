"""The lite server: settings -> one run -> one small mp4. No downloads, no evolution, no saved moments, no data folder.

    config    limits and paths (env vars)         settings   a request -> its canonical form -> a cache key
    cache     mp4s on disk, bounded by bytes      jobs       a bounded queue, one run per key, per-client rate limit
    engine    one run -> frames -> mp4            drawing    a frame: game picture, sense boxes, neuron strip
    encode    the ffmpeg writer                   bundle     the files the server ships (brains, icons, thumbnails, registry)
    app       the HTTP API                        __main__   python -m fly_mario_fly.lite

The run is the same `runner.Run` as the full tool's: same decisions, same hash. Only the picture is lighter.
"""
VERSION = "1"        # bump when a change would make an old cached video wrong (it is part of every cache key)
