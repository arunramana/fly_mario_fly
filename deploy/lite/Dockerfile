# The lite server image. Build from the repo root, after making the bundle on a machine that has the data:
#   python -m fly_mario_fly.lite.bundle deploy/lite/bundle            (see docs/lite.md)
#   docker build -f deploy/lite/Dockerfile -t fly-mario-fly-lite .
#   docker run -p 8080:8080 -e FMF_LITE_CORS=https://<you>.github.io fly-mario-fly-lite
FROM python:3.12-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY deploy/lite/requirements.txt deploy/lite/requirements.txt
RUN python -m venv /venv && /venv/bin/pip install --no-cache-dir -r deploy/lite/requirements.txt
COPY pyproject.toml README.md LICENSE ./
COPY src src
RUN /venv/bin/pip install --no-cache-dir --no-deps .

FROM python:3.12-slim
COPY --from=build /venv /venv
COPY deploy/lite/bundle /app/bundle
ENV PATH=/venv/bin:$PATH FMF_LITE_BUNDLE=/app/bundle FMF_LITE_CACHE=/data/cache FMF_LITE_TRUST_PROXY=1 PYTHONUNBUFFERED=1
RUN useradd -m app && mkdir -p /data/cache && chown app /data/cache
USER app
EXPOSE 8080
CMD ["python", "-m", "fly_mario_fly.lite", "--host", "0.0.0.0", "--port", "8080"]
