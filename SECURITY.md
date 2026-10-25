# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private reporting: the repository's **Security → Report a vulnerability** page. If that is unavailable, contact the maintainer through the address on their GitHub profile. We aim to acknowledge within a week.

## Scope and things to know

- This is a research tool for running on your own machine. The API (`python -m fly_mario_fly.api`) binds to `127.0.0.1` and has **no authentication**; do not expose it to a network or the internet.
- The API reads and writes under `$FLY_MARIO_FLY_DATA` (runs, videos, uploaded fly YAMLs). Treat that folder as trusted local state.
- Fly configs (`configs/flies/*.yaml`) and saved runs are loaded as data; please report any way a crafted file could run code or write outside the data folder.
- The project downloads public MaleCNS files over HTTPS from Google Cloud Storage. It stores no credentials and needs none; if you find one committed, report it.

## Supported versions

Only the latest `main`.
